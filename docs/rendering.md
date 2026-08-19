# Rendering and templates

Rendering is controlled by `JSONFormRenderer`. The default renderer maps node
types to templates inside the package:

| Key | Default template |
| --- | --- |
| `widget` | `django_native_jsonform/widget.html` |
| `leaf` | `django_native_jsonform/leaf.html` |
| `object` | `django_native_jsonform/object.html` |
| `array` | `django_native_jsonform/array.html` |
| `array_item` | `django_native_jsonform/array_item.html` |
| `union` | `django_native_jsonform/union.html` |

Replace templates for one composite field:

```python
configuration = JSONSchemaFormField(
    schema=SCHEMA,
    templates={
        "widget": "catalog/json/widget.html",
        "object": "catalog/json/object.html",
        "array_item": "catalog/json/variant.html",
    },
)
```

Replace only one path:

```python
configuration = JSONSchemaFormField(
    schema=SCHEMA,
    overrides={
        "variants": {"template": "catalog/json/variants.html"},
    },
)
```

## Custom renderer

Subclass `JSONFormRenderer` when templates alone are not enough:

```python
class DesignSystemRenderer(JSONFormRenderer):
    def render_node(self, binding, node):
        # Add metrics, change template selection, or build extra context.
        return super().render_node(binding, node)


configuration = JSONSchemaFormField(
    schema=SCHEMA,
    renderer=DesignSystemRenderer(),
)
```

## Front-end behavior

The included JavaScript handles:

- optional value/section presence;
- adding and removing array items;
- enabling only the active `oneOf` branch;
- switching discriminated branches without a server round trip.

Keep the `data-jsonform-*` attributes when replacing templates. They are the
stable connection between generated HTML and progressive enhancement.

Custom fields and widgets bring their own `Media` assets in the usual Django
way. The composite widget aggregates the media from its generated child
widgets after the form mixin seeds the binding. The package deliberately does
not bundle jQuery, a CSS framework, or a specific admin theme.
