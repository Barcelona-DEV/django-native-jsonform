# Migrate from django-jsonform

This package places schema ownership on the Django form and leaves persistence
as a normal `models.JSONField`.

## Model

Before:

```python
from django_jsonform.models.fields import JSONField


class Product(models.Model):
    configuration = JSONField(schema=configuration_schema, default=dict)
```

After:

```python
from django.db import models


class Product(models.Model):
    configuration = models.JSONField(default=dict)
```

## Form

```python
from django_native_jsonform import JSONSchemaFormField, JSONSchemaModelForm


class ProductForm(JSONSchemaModelForm):
    configuration = JSONSchemaFormField(
        schema=configuration_schema,
        required=False,
    )

    class Meta:
        model = Product
        fields = "__all__"
```

Assign the form to `ModelAdmin` and add `JSONSchemaAdminMixin` when schemas or
custom factories use request context.

## Historical migrations

Existing Django migrations may import field classes from the old dependency.
Do not casually rewrite applied migrations. The application may need to retain
that dependency until migrations are squashed, even when no runtime form uses
it.

Changing the live model field class from a third-party JSONField to Django's
native JSONField often produces an `AlterField` state migration with no SQL
column change. Confirm with `sqlmigrate` in the consuming project.

## Schema differences

- Move widget decisions into `widget`, a registry, or `overrides`.
- Use `const`/single-value `enum` discriminators for predictable `oneOf`
  switching.
- Decide whether defaults should remain sparse (`preserve`) or be stored
  (`materialize`).
- Register application-specific formats such as file pickers; they are not
  assumed by the core package.
- Add `JSONSchemaFormMixin` when retaining a custom existing Form base.

## Rollout checklist

1. Add the package to `INSTALLED_APPS`.
2. Convert persistence fields to `models.JSONField` where appropriate.
3. Declare `JSONSchemaFormField` on each ModelForm.
4. Add context integration for admin/views.
5. Register project-specific fields and widgets.
6. Inspect schema defaults and unknown-key behavior.
7. Generate and inspect migrations.
8. Exercise add, edit, invalid submission, arrays, and every union branch.
