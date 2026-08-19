# Building extensions

An extension connects a domain-specific Django field or widget to a portable
schema marker. Extensions stay in the consuming project or a separate reusable
Django application; the core package does not need to know their models.

## Clone the default registry

Create a registry module in the consumer:

```python
# catalog/json_forms.py
from django_native_jsonform import default_registry

catalog_registry = default_registry.clone()
```

Cloning avoids surprising unrelated forms. Reuse that registry wherever the
same domain vocabulary should apply.

## Register a field for a custom format

Factories receive `FieldFactoryContext`:

```python
from django import forms
from django_native_jsonform import FieldFactoryContext

from .fields import MediaAssetField
from .json_forms import catalog_registry


@catalog_registry.register_field("string", format="media-asset")
def media_asset_field(context: FieldFactoryContext) -> forms.Field:
    user = getattr(context.form_context, "user", None)
    return MediaAssetField(
        user=user,
        schema=context.schema,
        label=context.schema.get("title", "Asset"),
        help_text=context.schema.get("description", ""),
        required=context.required,
        disabled=context.disabled,
    )
```

The schema can now use:

```python
{
    "type": "string",
    "format": "media-asset",
    "title": "Hero image",
    "accept": ["image/png", "image/jpeg"],
}
```

`context` exposes:

- `path`: tuple such as `("sections", 0, "image")`;
- `schema`: the leaf schema, including custom extension keywords;
- `required` and `disabled`;
- `form_context`: request/user/object context supplied by the form.

Use `serialize`/`deserialize` overrides if the Django field's Python value is
not directly JSON-compatible.

## Register a named widget

A widget factory receives `WidgetFactoryContext`:

```python
from django_native_jsonform import WidgetFactoryContext


@catalog_registry.register_widget("markdown")
def markdown_widget(context: WidgetFactoryContext):
    return MarkdownWidget(
        attrs={
            "data-upload-url": context.schema.get("uploadUrl", ""),
            "data-path": ".".join(map(str, context.path)),
        }
    )
```

Select it from the schema:

```python
{
    "type": "string",
    "widget": "markdown",
}
```

or from a path override, which keeps UI hints out of a shared schema:

```python
overrides = {"article.body": {"widget": "markdown"}}
```

## Use the extension

```python
class ProductForm(JSONSchemaModelForm):
    configuration = JSONSchemaFormField(
        schema=PRODUCT_SCHEMA,
        registry=catalog_registry,
    )
```

## Example: a media library picker

The picker is an ordinary project field and widget:

```python
class MediaPathField(forms.CharField):
    def __init__(self, *, user=None, schema=None, **kwargs):
        self.user = user
        self.schema = schema or {}
        kwargs.setdefault(
            "widget",
            MediaLibraryWidget(
                accept=self.schema.get("accept", ["image/*"]),
                user=user,
            ),
        )
        super().__init__(**kwargs)


media_registry = default_registry.clone()


@media_registry.register_field("string", format="file-url")
@media_registry.register_field("string", format="data-url")
def media_path_field(context):
    return MediaPathField(
        user=getattr(context.form_context, "user", None),
        schema=context.schema,
        required=context.required,
        disabled=context.disabled,
        label=context.schema.get("title"),
    )
```

The widget may open an admin popup, upload a new object, use autocomplete, or
return a stable URL/path. That implementation remains fully owned by the
consumer.

## Register globally or locally?

Prefer a cloned registry passed explicitly to fields. Mutating
`default_registry` is useful when an installed extension defines a universally
understood format, but it changes every form created afterward and import order
then matters.

For a reusable extension package, expose a function instead:

```python
def install_media_fields(registry):
    registry.register_field("string", media_path_field, format="file-url")
    return registry
```

Consumers decide which registry receives the integration.

## Field resolver versus registry

Use a registry when a schema type/format has stable meaning. Use
`field_resolver` when selection depends on arbitrary runtime metadata or
application models. Use per-path overrides when the decision belongs to one
form.

## Custom templates and design systems

An extension may ship Django templates/static files and return widgets with a
`Media` class. A design-system integration can also provide a preconfigured
renderer and templates dictionary without modifying core behavior.
