"""Automatic presence regressions; not executed during implementation."""

from tests.test_validation import make_form


def test_optional_controls_are_opt_in():
    schema = {"type": "object", "properties": {"text": {"type": "string"}}}
    assert "Use/remove" not in make_form(schema).as_p()
    assert "Use/remove" in make_form(schema, presence_mode="explicit").as_p()


def test_empty_optional_values_omit_but_required_strings_remain():
    schema = {
        "type": "object",
        "properties": {"optional": {"type": "string"}, "required": {"type": "string"}},
        "required": ["required"],
    }
    form = make_form(
        schema,
        initial={"optional": "old"},
        data={
            "value-optional": "",
            "value-required": "",
        },
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == {"required": ""}


def test_zero_false_and_existing_empty_values_survive():
    schema = {
        "type": "object",
        "properties": {
            "n": {"type": "integer"},
            "b": {"type": "boolean"},
            "s": {"type": "string"},
        },
    }
    initial = {"n": 0, "b": False, "s": ""}
    form = make_form(schema, initial=initial, data={"value-n": "0", "value-s": ""})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == initial


def test_empty_optional_section_with_required_children_is_omitted():
    schema = {
        "type": "object",
        "properties": {
            "section": {
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string", "minLength": 1}},
            }
        },
    }
    form = make_form(schema, initial={}, data={"value-section__text": ""})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == {}


def test_required_schema_constraints_still_reject_blank():
    schema = {
        "type": "object",
        "required": ["text"],
        "properties": {"text": {"type": "string", "minLength": 1}},
    }
    assert not make_form(schema, data={"value-text": ""}).is_valid()
