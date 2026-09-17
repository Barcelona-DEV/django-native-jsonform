"""Exercise supported schema controls through rendered forms and real submissions."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError

from django_native_jsonform import (
    JSONSchemaAdminMixin,
    JSONSchemaFormField,
    JSONSchemaFormMixin,
    JSONSchemaValidator,
)
from django_native_jsonform.binding import (
    MISSING,
    JSONFormSubmission,
    path_matches,
    serialize_json_value,
)


def roundtrip(schema, initial, **options):
    class Example(JSONSchemaFormMixin, forms.Form):
        value = JSONSchemaFormField(schema=schema, **options)

    form = Example(initial={"value": initial})
    assert str(form["value"])
    binding = form.fields["value"].widget.build_binding(initial=initial, prefix="value")
    data = {}
    for key, field in binding.fields.items():
        if field.disabled:
            continue
        bound = binding.form[key]
        value = bound.value()
        if isinstance(field.widget, forms.CheckboxInput):
            if value:
                data[bound.html_name] = "on"
        else:
            data[bound.html_name] = "" if value is None else str(value)
    result = Example(data=data, initial={"value": initial})
    assert result.is_valid(), result.errors
    assert result.cleaned_data["value"] == initial
    assert not result.has_changed()
    return result


@pytest.mark.parametrize(
    "schema,value",
    [
        ({"type": "string", "format": "date"}, "2026-09-17"),
        ({"type": "string", "format": "time"}, "12:30:00"),
        ({"type": "string", "format": "date-time"}, "2026-09-17T12:30:00+00:00"),
        ({"type": "string", "format": "uri"}, "https://example.com/path"),
        ({"type": "string", "format": "email"}, "user@example.com"),
        ({"type": "string", "format": "uuid"}, "6bf256e0-146e-4586-8f5c-ec5bbda560dd"),
        ({"type": "boolean"}, False),
        ({"type": "number"}, 2.5),
        ({"type": "integer"}, 2),
        ({"type": "string", "choices": [{"value": "a", "title": "A"}, "b"]}, "a"),
        ({"type": "integer", "enum": [0, 1]}, 0),
        ({"enum": [None, "x"]}, None),
        ({"type": "object"}, {"custom": 2}),
        ({"type": "array"}, [1, "x"]),
        ({"const": "fixed"}, "fixed"),
        ({"type": ["string", "integer"]}, 3),
        ({"anyOf": [{"type": "integer"}, {"type": "string"}]}, "text"),
        ({"oneOf": [{"type": "boolean"}, {"type": "number"}]}, False),
        (
            {"allOf": [{"type": "object", "properties": {"x": {"type": "integer"}}}]},
            {"x": 1},
        ),
    ],
)
def test_native_control_roundtrips(schema, value):
    roundtrip(schema, value)


@pytest.mark.parametrize("value", [False, True, 0, 2, 1.5, "text", [], {}, None])
def test_union_branches_preserve_json_types(value):
    roundtrip(
        {
            "oneOf": [
                {"type": "boolean"},
                {"type": "integer"},
                {"type": "number", "not": {"type": "integer"}},
                {"type": "string"},
                {"type": "array"},
                {"type": "object"},
                {"type": "null"},
            ]
        },
        value,
    )


@pytest.mark.parametrize(
    "widget", [forms.Textarea, forms.Textarea(), lambda context: forms.Textarea()]
)
@pytest.mark.parametrize(
    "field", [forms.CharField, forms.CharField(), lambda context: forms.CharField()]
)
def test_override_factories_keep_the_document(widget, field):
    roundtrip(
        {"type": "string"},
        "example",
        overrides={
            "$": {
                "field": field,
                "widget": widget,
                "label": "Custom",
                "help_text": "Help",
                "attrs": {"data-test": "custom"},
            }
        },
    )


def test_context_schema_and_resolver_are_used():
    calls = []

    def resolver(context):
        calls.append(context.path)
        return forms.CharField(required=False)

    roundtrip(lambda: {"type": "string"}, "example", field_resolver=resolver)
    assert calls


def test_optional_disabled_and_direct_fields():
    field = JSONSchemaFormField(schema={"type": "integer"}, required=False)
    assert field.clean(MISSING) is None
    assert field.clean(2) == 2
    with pytest.raises(ValidationError):
        JSONSchemaFormField(schema={"type": "integer"}).clean(MISSING)
    assert not JSONSchemaFormField(schema=True, disabled=True).has_changed(1, 2)
    roundtrip(
        {"type": "object", "properties": {"x": {"type": "string", "readOnly": True}}},
        {"x": "kept"},
    )


@pytest.mark.parametrize(
    "pattern,path,expected",
    [
        ("$", (), True),
        ("$", ("x",), False),
        ("**.value", ("a", "b", "value"), True),
        ("a.*.value", ("a", 0, "value"), True),
        ("a.*.value", ("b", 0, "value"), False),
        ("**.value", ("a", "b"), False),
    ],
)
def test_path_overrides_match_only_their_intended_fields(pattern, path, expected):
    assert path_matches(pattern, path) is expected


def test_decimal_serialization_preserves_numeric_type():
    assert serialize_json_value(Decimal("2")) == 2
    assert serialize_json_value(Decimal("2.5")) == 2.5


@pytest.mark.parametrize(
    "schema",
    [
        {"properties": {1: {}}},
        {"oneOf": {}},
        {"choices": 1},
        {"type": "invalid"},
    ],
)
def test_malformed_schema_is_rejected_before_rendering(schema):
    with pytest.raises(ImproperlyConfigured):
        JSONSchemaValidator(schema)


@pytest.mark.parametrize(
    "form_base",
    [forms.ModelForm, type("Native", (JSONSchemaFormMixin, forms.ModelForm), {})],
)
def test_admin_injects_request_context_for_both_form_types(form_base):
    class Parent:
        def get_form(self, request, obj=None, **kwargs):
            return form_base

    class Admin(JSONSchemaAdminMixin, Parent):
        pass

    request = SimpleNamespace(user=object())
    obj = object()
    form_class = Admin().get_form(request, obj)
    assert issubclass(form_class, JSONSchemaFormMixin)
    assert form_class.json_form_context.obj is obj
    assert form_class.json_form_context.user is request.user


@pytest.mark.parametrize(
    "options",
    [
        {"default_policy": "invalid"},
        {"presence_mode": "invalid"},
        {"max_array_items": 0},
        {"max_depth": 0},
        {"max_nodes": 0},
        {"overrides": {"$": {"presence_mode": "invalid"}}},
    ],
)
def test_invalid_editor_options_fail_early(options):
    with pytest.raises(ValueError):
        JSONSchemaFormField(schema={"type": "string"}, **options).widget.build_binding(
            initial="", prefix="x"
        )


def test_editor_node_budget_is_enforced():
    with pytest.raises(ImproperlyConfigured, match="max_nodes"):
        JSONSchemaFormField(
            schema={"type": "object", "properties": {"x": {"type": "string"}}},
            max_nodes=1,
        ).widget.build_binding(initial={}, prefix="x")


@pytest.mark.parametrize(
    "schema,value",
    [
        ({"type": "object", "additionalProperties": {"type": "integer"}}, {"x": 1}),
        ({"type": "object", "additionalProperties": True}, {"x": 1}),
        ({"type": "object", "properties": {"a__b": {"type": "integer"}}}, {"a__b": 1}),
        ({"type": "array", "items": True}, [1]),
        ({"type": "array", "items": False}, []),
        ({"oneOf": [False, {"type": "integer"}]}, 1),
        ({"type": ["number", "integer"]}, 2),
        ({"enum": [{"x": 1}, [2]]}, {"x": 1}),
        ({"enum": [1, "1"]}, 1),
        ({"default": {"x": 1}}, {"x": 1}),
        ({"default": True}, True),
        ({"default": 2}, 2),
        ({"default": 2.5}, 2.5),
        ({"type": "number", "multipleOf": 1}, 2),
        ({"properties": {"x": {"type": "string"}}}, {"x": "a"}),
        (
            {
                "type": "object",
                "properties": {"x": {"$id": "urn:child", "type": "string"}},
            },
            {"x": "a"},
        ),
        ({"$defs": {"x": True}, "$ref": "#/$defs/x"}, 1),
        (
            {
                "$defs": {"x": {"type": "integer"}},
                "$ref": "#/$defs/x",
                "type": "integer",
            },
            1,
        ),
    ],
)
def test_raw_fallbacks_preserve_schema_semantics(schema, value):
    roundtrip(schema, value)


@pytest.mark.parametrize(
    "selector",
    [forms.ChoiceField, forms.ChoiceField(), lambda context: forms.ChoiceField()],
)
def test_custom_union_selectors(selector):
    roundtrip(
        {"oneOf": [{"type": "string"}, {"type": "integer"}]},
        "text",
        overrides={"$": {"selector_field": selector}},
    )


@pytest.mark.parametrize("selector", ["invalid", forms.CharField])
def test_invalid_union_selectors_are_rejected(selector):
    with pytest.raises(TypeError):
        roundtrip(
            {"oneOf": [{"type": "string"}, {"type": "integer"}]},
            "text",
            overrides={"$": {"selector_field": selector}},
        )


@pytest.mark.parametrize("discriminator", ["kind", {"propertyName": "kind"}])
def test_declared_discriminator_roundtrips(discriminator):
    roundtrip(
        {
            "discriminator": discriminator,
            "properties": {"kind": {"title": "Kind"}},
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "kind": {"enum": ["a"], "title": "First"},
                        "x": {"type": "string"},
                    },
                },
                {
                    "type": "object",
                    "properties": {"kind": {"const": "b"}, "y": {"type": "integer"}},
                },
            ],
        },
        {"kind": "a", "x": "text"},
    )


def test_registry_missing_factories_are_actionable():
    from django_native_jsonform.registry import FieldFactoryContext, JSONFormRegistry

    registry = JSONFormRegistry()
    with pytest.raises(ValueError, match="No Django field"):
        registry.create_field(FieldFactoryContext((), {"type": "string"}, True, False))
    with pytest.raises(ValueError, match="No Django widget"):
        registry.create_widget("missing", schema={})


def test_unbound_and_invalid_binding_cannot_expose_cleaned_data():
    widget = JSONSchemaFormField(schema={"type": "integer"}).widget
    binding = widget.build_binding(initial=1, prefix="x")
    assert not binding.is_valid()
    assert binding.bound_field(None) is None
    with pytest.raises(ValueError, match="invalid"):
        binding.cleaned_value()
    submission = JSONFormSubmission(
        data={"x-__root_value__": "bad"}, files={}, prefix="x"
    )
    assert widget.render("x", submission)
    assert not widget.binding.is_valid()
    assert JSONSchemaFormField(schema={"type": "integer"}).has_changed(1, submission)


def test_form_context_supports_objects_and_callables():
    class Example(JSONSchemaFormMixin, forms.Form):
        regular = forms.CharField(required=False)
        value = JSONSchemaFormField(schema={"type": "string"})

    context = SimpleNamespace()
    form = Example(json_form_context=context)
    assert context.form is form
    assert not context.user.is_superuser
    supplied = Example(json_form_context=lambda form, name: {"name": name})
    assert supplied.fields["value"].widget.context.name == "value"


def test_application_validators_attach_document_and_field_errors():
    from django_native_jsonform import JSONFormValidationError

    def reject(value):
        raise JSONFormValidationError("Rejected", errors={"/x": ["Rejected"]})

    class Example(JSONSchemaFormMixin, forms.Form):
        value = JSONSchemaFormField(
            schema={"type": "object", "properties": {"x": {"type": "string"}}},
            validators=[reject],
        )

    form = Example(data={"value-x": "text"})
    assert not form.is_valid()
    assert "Rejected" in str(form.errors)
    assert "Rejected" in str(form["value"])
