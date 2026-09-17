import pytest
from django import forms

from django_native_jsonform import JSONSchemaFormField, JSONSchemaFormMixin


def make_form(schema, initial, data=None):
    class Example(JSONSchemaFormMixin, forms.Form):
        value = JSONSchemaFormField(schema=schema, required=False)

    return Example(initial={"value": initial}, data=data)


@pytest.mark.parametrize("depth", [0, 1, 4])
@pytest.mark.parametrize("outer_type", [False, True])
def test_union_defaults_recurse_through_objects_arrays_and_refs(depth, outer_type):
    union = {
        "default": {"type": "ai"},
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "type": {"const": "ai"},
                    "limit": {"type": ["number", "null"], "minimum": 0},
                },
                "required": ["type"],
            },
            {
                "type": "object",
                "properties": {
                    "type": {"const": "manual"},
                    "label": {"type": "string"},
                },
                "required": ["type"],
            },
        ],
    }
    if outer_type:
        union["type"] = "object"
    schema = {"type": "array", "items": {"$ref": "#/$defs/importer"}}
    initial = [{"type": "ai", "limit": None, "extension": {"keep": 7}}]
    for _ in range(depth):
        schema = {"type": "object", "properties": {"child": schema}}
        initial = {"child": initial}
    schema["$defs"] = {"importer": union}
    form = make_form(schema, initial)
    binding = form.fields["value"].widget.build_binding(initial=initial, prefix="value")

    def walk(node):
        yield node
        for child in [*node.children, *node.branches, *node.items]:
            yield from walk(child)

    nodes = list(walk(binding.root))
    unions = [node for node in nodes if node.kind == "union" and node.active]
    assert len(unions) == 1
    assert unions[0].discriminator == "type"
    limit = next(node for node in nodes if node.path[-1:] == ("limit",) and node.active)
    assert limit.kind == "leaf"
    assert isinstance(binding.fields[limit.field_key].widget, forms.NumberInput)
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
    bound = make_form(schema, initial, data=data)
    assert bound.is_valid(), bound.errors
    assert bound.cleaned_data["value"] == initial


@pytest.mark.parametrize(
    "value, valid", [("", True), ("0", True), ("2.5", True), ("-1", False)]
)
def test_nullable_numeric_document_validation(value, valid):
    schema = {
        "type": "object",
        "properties": {
            "limit": {"type": ["number", "null"], "minimum": 0},
        },
    }
    form = make_form(schema, {"limit": None}, {"value-limit": value})
    assert form.is_valid() is valid
    if valid:
        assert form.cleaned_data["value"]["limit"] == (float(value) if value else None)
