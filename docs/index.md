# django-native-jsonform

`django-native-jsonform` turns a JSON Schema into a tree of ordinary Django
fields and widgets. On submit, it validates every leaf through Django and
reconstructs a Python value ready for `models.JSONField`.

It is designed for JSON configuration that is structurally rich but must still
behave like the rest of a Django application:

- server-side validation and normal `form.errors`;
- ModelForm and Django admin support;
- current-user, permission, and object-aware schemas;
- custom application widgets and model-backed fields;
- nested objects, arrays, and conditional `oneOf` sections;
- sparse data where a displayed default is not necessarily stored;
- project-owned templates and styling.

## Why “native”?

The browser receives progressive enhancement for adding/removing array items,
toggling optional values, and changing `oneOf` branches. It does **not** become
the source of truth. The generated leaves are Django `Field` instances and all
submitted values are parsed and validated again on the server.

This also means an existing Django widget—an autocomplete, rich text editor,
media picker, model selector, or custom date control—can be reused instead of
being recreated inside a separate JavaScript form framework.

## A small example

```python
from django_native_jsonform import JSONSchemaFormField, JSONSchemaModelForm


class CampaignForm(JSONSchemaModelForm):
    settings = JSONSchemaFormField(
        schema={
            "type": "object",
            "properties": {
                "headline": {"type": "string", "maxLength": 120},
                "starts_on": {"type": "string", "format": "date"},
                "enabled": {"type": "boolean", "default": True},
            },
            "required": ["headline"],
        }
    )

    class Meta:
        model = Campaign
        fields = "__all__"
```

Continue with [installation](installation.md) or the
[quick start](quick-start.md). To connect a project-specific integration, see
[building extensions](extensions.md).

!!! note "Alpha API"
    The code has production origins, but the standalone package starts at
    `0.1.0`. Public API compatibility is guaranteed only after `1.0`.
