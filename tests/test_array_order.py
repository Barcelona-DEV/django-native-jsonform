from django import forms

from django_native_jsonform import JSONSchemaFormField, JSONSchemaFormMixin


class OrderedForm(JSONSchemaFormMixin, forms.Form):
    value = JSONSchemaFormField(
        schema={
            "type": "array",
            "items": {"type": "object", "properties": {"title": {"type": "string"}}},
        }
    )


def test_order_moves_whole_objects_and_preserves_unknown_children():
    initial = [
        {"title": "A", "unknown": {"id": 1}},
        {"title": "B", "unknown": {"id": 2}},
    ]
    data = {
        "value-__jsonform_count____root_value__": "2",
        "value-0__title": "A",
        "value-1__title": "B",
        "value-__jsonform_order__0": "1",
        "value-__jsonform_order__1": "0",
    }
    form = OrderedForm(initial={"value": initial}, data=data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == list(reversed(initial))
    html = str(form["value"])
    assert 'data-jsonform-move="up"' in html
    assert 'data-jsonform-move="down"' in html
    assert html.index('value="B"') < html.index('value="A"')


def test_older_submissions_without_order_keep_existing_order():
    form = OrderedForm(
        initial={"value": [{"title": "A"}, {"title": "B"}]},
        data={"value-0__title": "A", "value-1__title": "B"},
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == [{"title": "A"}, {"title": "B"}]


def test_reorder_skips_deleted_items():
    form = OrderedForm(
        initial={"value": [{"title": "A"}, {"title": "B"}, {"title": "C"}]},
        data={
            "value-__jsonform_order__0": "2",
            "value-__jsonform_order__1": "1",
            "value-__jsonform_order__2": "0",
            "value-__jsonform_delete__1": "True",
        },
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == [{"title": "C"}, {"title": "A"}]


def test_readonly_array_does_not_accept_reordering():
    class ReadonlyForm(JSONSchemaFormMixin, forms.Form):
        value = JSONSchemaFormField(
            schema={"type": "array", "readOnly": True, "items": {"type": "string"}}
        )

    form = ReadonlyForm(
        initial={"value": ["A", "B"]},
        data={"value-__jsonform_order__0": "1", "value-__jsonform_order__1": "0"},
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value"] == ["A", "B"]
    assert "data-jsonform-move=" not in str(form["value"])


def test_nested_arrays_keep_independent_order():
    class NestedForm(JSONSchemaFormMixin, forms.Form):
        value = JSONSchemaFormField(
            schema={
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
            }
        )

    initial = {"value": [["A", "B"], ["C"]]}
    form = NestedForm(initial=initial)
    binding = form.fields["value"].widget.binding
    data = {
        binding.form[key].html_name: str(binding.form[key].value())
        for key, field in binding.fields.items()
        if not field.disabled
    }
    data.update(
        {
            "value-__jsonform_order__0": "1",
            "value-__jsonform_order__1": "0",
            "value-__jsonform_order__0__0": "1",
            "value-__jsonform_order__0__1": "0",
        }
    )
    bound = NestedForm(initial=initial, data=data)
    assert bound.is_valid(), bound.errors
    assert bound.cleaned_data["value"] == [["C"], ["B", "A"]]


def test_media_uses_versioned_assets_and_arrows_share_a_container():
    form = OrderedForm(initial={"value": [{"title": "A"}, {"title": "B"}]})
    assert "json_forms.0.5.1.js" in str(form.media)
    assert "json_forms.0.5.1.css" in str(form.media)
    assert 'class="jsonform-order-controls"' in str(form["value"])
