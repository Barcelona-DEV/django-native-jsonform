# Quick start

Assume the model stores arbitrary product configuration:

```python
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=200)
    configuration = models.JSONField(default=dict, blank=True)
```

Define a schema on the form, not on the model field:

```python
from django_native_jsonform import JSONSchemaFormField, JSONSchemaModelForm

from .models import Product


PRODUCT_SCHEMA = {
    "type": "object",
    "title": "Configuration",
    "properties": {
        "description": {
            "type": "string",
            "title": "Description",
            "widget": "textarea",
        },
        "price": {
            "type": "number",
            "minimum": 0,
        },
        "labels": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
        },
    },
    "required": ["price"],
}


class ProductForm(JSONSchemaModelForm):
    configuration = JSONSchemaFormField(
        schema=PRODUCT_SCHEMA,
        required=False,
    )

    class Meta:
        model = Product
        fields = "__all__"
```

Use it like any ModelForm:

```python
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
        json_form_context={
            "request": request,
            "user": request.user,
            "obj": product,
        },
    )
    if form.is_valid():
        form.save()
        return redirect("product-detail", pk=product.pk)
    return render(request, "products/edit.html", {"form": form})
```

The template does not require a special renderer:

```django
<form method="post" enctype="multipart/form-data">
  {% csrf_token %}
  {{ form.media }}
  {{ form.as_div }}
  <button type="submit">Save</button>
</form>
```

`JSONSchemaModelForm` already includes the context/preservation mixin. When a
project must inherit from another custom ModelForm, use
`JSONSchemaModelFormMixin` before that class instead.

```python
class ProductForm(JSONSchemaModelFormMixin, ExistingProductForm):
    configuration = JSONSchemaFormField(schema=PRODUCT_SCHEMA)
```

The mixin seeds the generated binding with the original JSON. Without it,
unknown values or schema branches hidden by permissions cannot be preserved
reliably.
