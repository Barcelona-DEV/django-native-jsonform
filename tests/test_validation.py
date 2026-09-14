"""Draft 2020-12 regressions. Added without running tests at user request."""

from copy import deepcopy

import pytest
from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError

from django_native_jsonform import (
    JSONSchemaFormField,
    JSONSchemaFormMixin,
    JSONSchemaValidator,
    normalize_schema,
)
from django_native_jsonform.binding import MISSING


@pytest.mark.parametrize(
    "schema,valid,invalid",
    [
        ({"type": "integer"}, 1.0, True),
        ({"type": ["null", "integer"]}, None, "1"),
        ({"type": ["number", "integer"]}, 1, "1"),
        ({"const": True}, True, 1),
        ({"enum": [False, {"a": 1}]}, {"a": 1}, 0),
        ({"minimum": 2}, 2, 1),
        ({"maximum": 2}, 2, 3),
        ({"exclusiveMinimum": 2}, 3, 2),
        ({"exclusiveMaximum": 2}, 1, 2),
        ({"multipleOf": 0.1}, 0.3, 0.31),
        ({"minLength": 2}, "ab", "a"),
        ({"maxLength": 2}, "ab", "abc"),
        ({"pattern": "ab"}, "xaby", "ac"),
        ({"minItems": 1}, [0], []),
        ({"maxItems": 0}, [], [0]),
        ({"uniqueItems": True}, [True, 1], [1, 1.0]),
        ({"uniqueItems": True}, [{"x": 1}, {"x": 2}], [{"x": 1}, {"x": 1}]),
        ({"contains": {"type": "integer"}}, ["x", 1], ["x"]),
        (
            {"contains": {"type": "integer"}, "minContains": 0, "maxContains": 1},
            [],
            [1, 2],
        ),
        ({"prefixItems": [{"type": "string"}], "items": False}, ["x"], ["x", 1]),
        ({"prefixItems": [True], "unevaluatedItems": False}, [None], [None, 1]),
        ({"minProperties": 1}, {"a": 1}, {}),
        ({"maxProperties": 0}, {}, {"a": 1}),
        ({"required": ["a"]}, {"a": ""}, {}),
        ({"properties": {"a": False}}, {}, {"a": 1}),
        (
            {"properties": {"a": True}, "additionalProperties": False},
            {"a": 1},
            {"b": 1},
        ),
        ({"patternProperties": {"^x": {"type": "integer"}}}, {"x1": 1}, {"x1": "a"}),
        ({"propertyNames": {"pattern": "^[a-z]+$"}}, {"abc": 1}, {"A": 1}),
        ({"dependentRequired": {"a": ["b"]}}, {"a": 1, "b": 2}, {"a": 1}),
        ({"dependentSchemas": {"a": {"required": ["b"]}}}, {}, {"a": 1}),
        ({"allOf": [{"minimum": 1}, {"maximum": 3}]}, 2, 4),
        ({"anyOf": [{"type": "string"}, {"type": "number"}]}, 1, None),
        ({"oneOf": [{"type": "number"}, {"type": "integer"}]}, 1.5, 1),
        ({"not": {"type": "null"}}, 0, None),
        (
            {
                "if": {"type": "string"},
                "then": {"minLength": 2},
                "else": {"minimum": 2},
            },
            "ab",
            1,
        ),
        (
            {"allOf": [{"properties": {"a": True}}], "unevaluatedProperties": False},
            {"a": 1},
            {"b": 1},
        ),
        (
            {"$defs": {"n": {"type": "integer"}}, "$ref": "#/$defs/n", "minimum": 2},
            2,
            1,
        ),
        (
            {
                "$defs": {"n": {"$anchor": "number", "type": "integer"}},
                "$ref": "#number",
            },
            1,
            "1",
        ),
    ],
)
def test_document_constraints(schema, valid, invalid):
    validator = JSONSchemaValidator(schema)
    assert validator.issues(valid) == []
    assert validator.issues(invalid)


def test_boolean_schemas_and_non_json_values():
    assert JSONSchemaValidator(True).issues(None) == []
    assert JSONSchemaValidator(False).issues(None)
    assert JSONSchemaValidator(True).issues(float("nan"))
    assert JSONSchemaValidator(True).issues(float("inf"))


def test_normalization_does_not_rewrite_json_values_or_input():
    schema = {
        "properties": {"x": {"required": True, "choices": [{"value": 1}]}},
        "const": {"required": True, "properties": {"x": False}},
        "default": {"required": False},
    }
    before = deepcopy(schema)
    normalized = normalize_schema(schema)
    assert schema == before
    assert normalized["const"] == schema["const"]
    assert normalized["default"] == schema["default"]
    assert normalized["required"] == ["x"]
    assert normalized["properties"]["x"]["enum"] == [1]


@pytest.mark.parametrize(
    "schema",
    [
        {"minItems": -1},
        {"properties": []},
        {"required": 1},
        {"items": []},
        {"$schema": "http://json-schema.org/draft-07/schema#"},
    ],
)
def test_invalid_schemas_are_configuration_errors(schema):
    with pytest.raises(ImproperlyConfigured):
        JSONSchemaValidator(schema)


def test_references_are_explicit_and_ref_siblings_intersect():
    validator = JSONSchemaValidator(
        {"$ref": "urn:example:number", "maximum": 3},
        schema_resources={"urn:example:number": {"type": "integer", "minimum": 2}},
    )
    assert validator.issues(2) == []
    assert validator.issues(1)
    assert validator.issues(4)
    with pytest.raises(ImproperlyConfigured):
        JSONSchemaValidator({"$ref": "https://example.invalid/schema"})(1)


def test_recursive_dynamic_reference():
    schema = {
        "$id": "urn:example:node",
        "$dynamicAnchor": "node",
        "type": "object",
        "properties": {"child": {"$dynamicRef": "#node"}},
    }
    validator = JSONSchemaValidator(schema)
    assert validator.issues({"child": {"child": {}}}) == []
    assert validator.issues({"child": 1})


def test_formats_opt_in_content_annotations_and_error_paths():
    schema = {"format": "email"}
    assert JSONSchemaValidator(schema).issues("invalid") == []
    assert JSONSchemaValidator(schema, validate_formats=True).issues("invalid")
    assert (
        JSONSchemaValidator(
            {"contentEncoding": "base64", "contentSchema": False}
        ).issues("not base64")
        == []
    )
    validator = JSONSchemaValidator(
        {"properties": {"a/b~c": False, "x": False}}, max_errors=1
    )
    issues = validator.issues({"a/b~c": 1, "x": 1})
    assert len(issues) == 1
    assert issues[0].pointer == "/a~1b~0c"


def make_form(schema, *, data=None, initial=MISSING, **options):
    class ExampleForm(JSONSchemaFormMixin, forms.Form):
        value = JSONSchemaFormField(schema=schema, **options)

    return ExampleForm(
        data=data, initial={} if initial is MISSING else {"value": initial}
    )


def test_boolean_property_and_null_have_json_editors():
    form = make_form(
        {"type": "object", "properties": {"a": True, "b": {"type": "null"}}},
        initial={"a": {"x": 1}, "b": None},
    )
    html = str(form["value"])
    assert 'name="value-a"' in html
    assert "data-jsonform-json-editor" in html


def test_custom_field_cannot_bypass_document_validation():
    form = make_form(
        {"type": "integer", "exclusiveMinimum": 5},
        data={"value-__root_value__": "5"},
        overrides={"$": {"field": forms.IntegerField()}},
    )
    assert not form.is_valid()
    assert "greater than" in str(form["value"])


def test_whitespace_and_required_empty_string():
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    for value in ("", "  text  "):
        form = make_form(schema, data={"value-text": value})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["value"] == {"text": value}


def test_absent_optional_invalid_values_are_ignored():
    schema = {
        "type": "object",
        "properties": {"number": {"type": "integer", "minimum": 5}},
    }
    form = make_form(
        schema,
        data={"value-number": "garbage", "value-__jsonform_present__number": "False"},
        initial={},
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == {}


def test_absent_optional_union_does_not_require_a_selector():
    schema = {
        "type": "object",
        "properties": {"v": {"oneOf": [{"type": "string"}, {"type": "integer"}]}},
    }
    form = make_form(schema, data={"value-__jsonform_present__v": "False"}, initial={})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == {}


def test_json_fallback_is_overridable_and_preserves_large_arrays():
    schema = {"type": "array", "items": {"type": "integer"}}
    initial = list(range(4))
    form = make_form(schema, initial=initial, max_array_items=2)
    binding = form.fields["value"].widget.binding
    assert binding.root.kind == "leaf"
    assert binding.field_initial[binding.root.field_key] == initial
    assert "data-jsonform-json-editor" in str(form["value"])
    form = make_form(
        {"allOf": [{"type": "object"}]},
        overrides={"$": {"widget": forms.Textarea(attrs={"class": "custom-json"})}},
    )
    assert "custom-json" in str(form["value"])


def test_zero_maximum_is_rendered_and_count_tampering_is_invalid():
    schema = {"type": "array", "items": {"type": "integer"}, "maxItems": 0}
    assert 'data-jsonform-max-items="0"' in str(make_form(schema, initial=[])["value"])
    form = make_form(
        schema,
        initial=[],
        max_array_items=2,
        data={"value-__jsonform_count____root_value__": "3"},
    )
    assert not form.is_valid()


def test_direct_values_use_schema_validation():
    field = JSONSchemaFormField(schema={"type": "array", "maxItems": 0})
    assert field.clean([]) == []
    with pytest.raises(ValidationError):
        field.clean([1])


def test_deleted_rows_report_serialized_error_coordinates():
    schema = {"type": "array", "items": {"type": "string", "pattern": "^ok$"}}
    form = make_form(
        schema,
        initial=["ok", "ok"],
        data={
            "value-__jsonform_count____root_value__": "2",
            "value-__jsonform_delete__0": "True",
            "value-1": "bad",
        },
    )
    assert not form.is_valid()
    binding = form.fields["value"].widget.binding
    assert "/0:" in str(binding.form.non_field_errors())
    assert binding.form["1"].errors
    assert not binding.form["0"].errors


def test_boolean_and_number_changes_are_distinguished_in_objects():
    schema = {"type": "object", "properties": {"x": True}}
    form = make_form(
        schema,
        initial={"x": True},
        data={
            "value-x": "1",
            "value-__jsonform_present__x": "True",
        },
    )
    assert form.has_changed()


def test_explicit_null_is_preserved_in_initial_binding():
    form = make_form({"type": "null"}, initial=None)
    assert form.fields["value"].widget.binding.root.exists
    assert form.fields["value"].widget.binding.root.initial is None


def test_field_initial_seeds_binding():
    class InitialForm(JSONSchemaFormMixin, forms.Form):
        value = JSONSchemaFormField(schema={"type": "array"}, initial=[1, 2])

    assert InitialForm().fields["value"].widget.binding.initial == [1, 2]


def test_complex_editor_preserves_json_and_validates_conditions():
    schema = {
        "type": "object",
        "if": {"properties": {"kind": {"const": "number"}}},
        "then": {"properties": {"value": {"type": "integer"}}},
        "else": {"properties": {"value": {"type": "string"}}},
    }
    form = make_form(
        schema, data={"value-__root_value__": '{"kind":"number","value":2}'}
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == {"kind": "number", "value": 2}
    invalid = make_form(
        schema, data={"value-__root_value__": '{"kind":"number","value":"two"}'}
    )
    assert not invalid.is_valid()


def test_reserved_property_names_use_lossless_editor():
    form = make_form(
        {"type": "object", "properties": {"a__b": True}}, initial={"a__b": 2}
    )
    assert form.fields["value"].widget.binding.root.kind == "leaf"


def test_optional_parent_removes_required_nested_list():
    schema = {
        "type": "object",
        "properties": {
            "section": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    }
                },
                "required": ["items"],
            }
        },
    }
    form = make_form(
        schema,
        initial={"section": {"items": ["a", "b"]}},
        data={
            "value-__jsonform_present__section": "False",
        },
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == {}
