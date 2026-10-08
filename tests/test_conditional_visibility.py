from tests.test_validation import make_form


def test_visibility_only_adds_presentation_and_preserves_inapplicable_values():
    schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string"},
            "limit": {
                "type": "integer",
                "visible_when": {"field": "mode", "not_in": ["automatic"]},
                "visibility_warning": "Remove the incompatible limit.",
            },
        },
    }
    value = {"mode": "automatic", "limit": 5}
    form = make_form(schema, initial=value)
    assert "data-jsonform-visibility=" in form.as_p()
    assert "Remove the incompatible limit." in form.as_p()
    submitted = make_form(
        schema, initial=value, data={"value-mode": "automatic", "value-limit": "5"}
    )
    assert submitted.is_valid(), submitted.errors
    assert submitted.cleaned_data["value"] == value


def test_explicit_optional_sections_have_configurable_labels():
    schema = {
        "type": "object",
        "properties": {
            "filter": {
                "type": "object",
                "properties": {"term": {"type": "string"}},
            }
        },
    }
    options = {
        "overrides": {
            "filter": {
                "presence_mode": "explicit",
                "enable_label": "Use filter",
                "disable_label": "Remove filter",
            }
        }
    }
    form = make_form(schema, initial={}, **options)
    html = form.as_p()
    assert "data-jsonform-optional-section" in html
    assert 'data-enable-label="Use filter"' in html
    present = "value-__jsonform_present__filter"
    active = make_form(
        schema, initial={}, data={present: "True", "value-filter__term": "x"}, **options
    )
    assert active.is_valid(), active.errors
    assert active.cleaned_data["value"] == {"filter": {"term": "x"}}
    removed = make_form(
        schema, initial={"filter": {"term": "x"}}, data={present: "False"}, **options
    )
    assert removed.is_valid(), removed.errors
    assert removed.cleaned_data["value"] == {}


def test_plain_schemas_do_not_gain_visibility_wrappers():
    assert "data-jsonform-visibility" not in make_form({"type": "string"}).as_p()
