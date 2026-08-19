# django-native-jsonform

[![PyPI](https://img.shields.io/pypi/v/django-native-jsonform.svg)](https://pypi.org/project/django-native-jsonform/)
[![Python](https://img.shields.io/pypi/pyversions/django-native-jsonform.svg)](https://pypi.org/project/django-native-jsonform/)
[![Django](https://img.shields.io/badge/Django-4.2%20%7C%205.x-0C4B33)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Build nested, server-validated JSON editors from JSON Schema using ordinary
Django `Field`, `Widget`, `Form`, and `ModelForm` primitives.

`django-native-jsonform` is intended for applications that store configurable
data in `models.JSONField` but still want Django's validation, permissions,
widgets, templates, admin integration, and extension points.

## Highlights

- Objects, arrays, nested arrays, choices, local `$ref`, and discriminated
  `oneOf` branches.
- Native Django fields and server-side validation—no client-only JSON editor.
- Dynamic schemas with access to the current request, user, object, and form.
- Exact-path, `*`, and `**` overrides for fields, widgets, attributes,
  serializers, defaults, permissions, and templates.
- Cloneable registries for project-specific JSON formats and widgets.
- Sparse JSON preservation: displayed defaults do not have to be persisted.
- Unknown-key preservation for forward-compatible and permission-aware forms.
- Template-driven rendering and small progressive-enhancement JavaScript.

## Installation

```bash
python -m pip install django-native-jsonform
```

```python
INSTALLED_APPS = [
    # ...
    "django_native_jsonform",
]
```

## Quick start

```python
from django import forms

from django_native_jsonform import JSONSchemaFormField, JSONSchemaModelForm

from .models import Product


PRODUCT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "title": "Title"},
        "price": {"type": "number", "minimum": 0},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["title"],
}


class ProductForm(JSONSchemaModelForm):
    metadata = JSONSchemaFormField(schema=PRODUCT_SCHEMA, required=False)

    class Meta:
        model = Product
        fields = "__all__"
```

For Django admin, add `JSONSchemaAdminMixin` so callable schemas and factories
receive the current request context:

```python
from django.contrib import admin
from django_native_jsonform import JSONSchemaAdminMixin


@admin.register(Product)
class ProductAdmin(JSONSchemaAdminMixin, admin.ModelAdmin):
    form = ProductForm
```

## Customize a project-specific format

```python
from django import forms
from django_native_jsonform import FieldFactoryContext, default_registry

registry = default_registry.clone()


@registry.register_field("string", format="media-asset")
def media_asset_field(context: FieldFactoryContext) -> forms.Field:
    return MediaAssetField(
        user=context.form_context.user,
        schema=context.schema,
        required=context.required,
    )


class ProductForm(JSONSchemaModelForm):
    metadata = JSONSchemaFormField(schema=PRODUCT_SCHEMA, registry=registry)
```

The package does not depend on a particular rich text editor, media library,
autocomplete implementation, or design system. Those are registered by each
consumer.

## Documentation

The complete wiki lives in [`docs/`](docs/index.md) and is published at
[barcelona-dev.github.io/django-native-jsonform](https://barcelona-dev.github.io/django-native-jsonform/).

Start with the [quick start](docs/quick-start.md), then see
[customization](docs/customization.md) and
[building extensions](docs/extensions.md).

## Status

The API is currently alpha. It was extracted from a production Django
application, but semantic-versioning compatibility begins with `1.0`.

## License

MIT
