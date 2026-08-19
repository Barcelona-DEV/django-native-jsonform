# Per-path customization

Pass `overrides` to customize one field without changing a shared schema.
Paths use dot notation:

- `billing.address.city` matches one exact leaf;
- `variants.*.price` matches every array item's price;
- `internal.**` matches the section and all descendants;
- `$` or an empty string matches the root.

```python
from django import forms
from django_native_jsonform import JSONSchemaFormField


configuration = JSONSchemaFormField(
    schema=PRODUCT_SCHEMA,
    overrides={
        "description": {
            "widget": forms.Textarea(attrs={"rows": 8}),
        },
        "variants.*.price": {
            "field": forms.DecimalField(max_digits=10, decimal_places=2),
            "attrs": {"class": "money"},
            "serialize": str,
        },
        "internal.**": {
            "readonly": True,
        },
    },
)
```

## Override keys

| Key | Purpose |
| --- | --- |
| `field` | Django field instance, class, or `BuildContext` factory |
| `widget` | registry name, widget instance/class, or factory |
| `attrs` | HTML attributes merged into the final widget |
| `label` | replace the generated label |
| `help_text` | replace schema help text |
| `required` | force presence behavior for this path |
| `readonly` | preserve the initial value and do not accept edits |
| `disabled` | render a disabled Django field |
| `serialize` | convert cleaned Django values to JSON-compatible values |
| `deserialize` | convert stored JSON before giving it to the widget |
| `default_policy` | `preserve` or `materialize` for this path |
| `template` | replace the node template |
| `selector_field` | custom choice field for a `oneOf` selector |
| `selector_label` | label for a `oneOf` selector |
| `selector_help_text` | help text for a `oneOf` selector |
| `selector_attrs` | widget attributes for a `oneOf` selector |

## Context-aware overrides

An override can be a callable. It receives `BuildContext`:

```python
def confidential_override(context):
    can_edit = context.form_context.user.has_perm("catalog.edit_confidential")
    return {
        "readonly": not can_edit,
        "help_text": "Restricted field" if not can_edit else "",
    }


configuration = JSONSchemaFormField(
    schema=PRODUCT_SCHEMA,
    overrides={"confidential.**": confidential_override},
)
```

`BuildContext` contains `path`, `schema`, `required`, `disabled`,
`form_context`, `initial`, `exists`, and the overrides accumulated so far.

## Field resolver

For cross-cutting runtime decisions, pass a resolver called for every leaf:

```python
def resolve_field(context):
    if context.schema.get("x-model") == "catalog.Category":
        return forms.ModelChoiceField(
            queryset=Category.objects.for_user(context.form_context.user)
        )
    return None


configuration = JSONSchemaFormField(
    schema=PRODUCT_SCHEMA,
    field_resolver=resolve_field,
)
```

Returning `None` delegates to choices and then to the registry.

## Sparse defaults

The default policy is `preserve`. A schema default is shown but is not written
until that value becomes present. This is useful when missing values mean
“inherit from a parent”.

Use `default_policy="materialize"` when every displayed default must be stored.
The policy can be set for the whole field or a matching path override.

Unknown object keys are preserved by default. Set `preserve_unknown=False`
only when the form owns the complete JSON shape and may intentionally remove
keys it does not render.
