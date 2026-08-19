# Django admin

`JSONSchemaAdminMixin` injects a per-request context into JSON schema fields.
Place it before `ModelAdmin` or another admin base class:

```python
from django.contrib import admin
from django_native_jsonform import JSONSchemaAdminMixin


@admin.register(Product)
class ProductAdmin(JSONSchemaAdminMixin, admin.ModelAdmin):
    form = ProductForm
```

The default context exposes:

- `context.user` — current admin user;
- `context.obj` — object being edited, or `None` on add;
- `context.request` — current `HttpRequest`;
- `context.form` — instantiated form, added by the form mixin.

Customize it when the application needs extra data:

```python
from types import SimpleNamespace


class ProductAdmin(JSONSchemaAdminMixin, admin.ModelAdmin):
    form = ProductForm

    def get_json_form_context(self, request, obj=None):
        return SimpleNamespace(
            request=request,
            user=request.user,
            obj=obj,
            tenant=request.tenant,
            features=request.tenant.features,
        )
```

The mixin creates a contextual form subclass per request. It does not mutate a
shared form class, so two concurrent admin requests cannot leak users or
objects into each other.

## Inlines

Inlines may use `JSONSchemaModelForm` directly. If they need parent-object
context, override the inline's `get_formset` or supply a custom formset that
passes `json_form_context` to each child form.

## Form media

The field automatically contributes its CSS and JavaScript through
`form.media`. Django admin includes form media automatically. Custom views must
render `{{ form.media }}` themselves.
