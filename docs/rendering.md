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

In 0.2.0, keep `data-jsonform-required` on container nodes and
`data-jsonform-min-items`, `data-jsonform-max-items`, and
`data-jsonform-max-render-items` on arrays. Preserve direct-child presence,
count/deletion inputs and the items/prototype containers. Include
`binding.form.non_field_errors` in the root template so document-level and raw
editor errors remain visible. Read-only fields use
`data-jsonform-permanent-disabled`; do not use that marker for cloneable controls.

Custom fields and widgets bring their own `Media` assets in the usual Django
way. The composite widget aggregates the media from its generated child
widgets after the form mixin seeds the binding. The package deliberately does
not bundle jQuery, a CSS framework, or a specific admin theme.

## Array ordering

Editable array items include up/down buttons. Moving an item moves its complete
subtree, preserving control identities and unknown stored properties. Nested arrays
maintain independent order. Boundary buttons are disabled and read-only arrays
hide the controls. Older submissions without order metadata keep their original
order. Custom array-item templates should render `{{ order }}` alongside
`{{ delete }}` and preserve `data-jsonform-index="{{ index }}"` on the item.

Static CSS and JavaScript use versioned filenames. When changing either asset,
bump the filenames and widget media paths together so browser/CDN caches cannot
combine an older script with newer templates. Deployments must run collectstatic.

## Conditional visibility

A field schema may declare a presentation rule based on a sibling's value:

```python
{
    "type": "integer",
    "visible_when": {"field": "mode", "not_in": ["automatic"]},
    "visibility_warning": "Remove this value before using automatic mode.",
}
```

Use `in` or `not_in` with a list of string values. Rules are relative to the
field's parent object, including nested objects. Empty inapplicable controls are
hidden. Populated controls and errors remain visible, with the supplied warning.
Visibility never disables controls, changes presence markers, or removes stored
values. Apply business validation separately on the server.

## Collapsed optional sections

Opt in through field overrides without changing the JSON schema or document:

```python
overrides = {
    "filter": {
        "presence_mode": "explicit",
        "enable_label": "Use filter",
        "disable_label": "Remove filter",
    },
}
```

An absent optional object or union starts collapsed. Existing values start
expanded. The native use/remove control explicitly includes or omits the section
on submission; re-enabling before saving retains its current control values.
Required sections are not collapsed. Scalar optional fields keep their native
use/remove control. Schemas without these options retain their previous rendering.
The widget includes the JavaScript automatically through its media; deploy the
versioned static assets with `collectstatic`.
