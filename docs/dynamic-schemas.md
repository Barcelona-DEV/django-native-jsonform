# Dynamic schemas and context

`schema` may be a dictionary or a callable. A callable with one parameter
receives the current form context; a zero-argument callable is also accepted.

```python
def configuration_schema(context):
    properties = {
        "title": {"type": "string"},
    }
    if context.user.has_perm("catalog.set_internal_code"):
        properties["internal_code"] = {"type": "string"}
    if context.obj and context.obj.pk:
        properties["slug"] = {"type": "string", "readOnly": True}
    return {
        "type": "object",
        "properties": properties,
        "required": ["title"],
    }
```

Pass a dictionary, namespace, or application object as `json_form_context`:

```python
form = ProductForm(
    request.POST or None,
    instance=product,
    json_form_context={
        "user": request.user,
        "request": request,
        "obj": product,
        "tenant": request.tenant,
    },
)
```

Dictionary context is converted into an attribute-accessible namespace and
receives `form`. When no context is provided, the mixin supplies:

- `obj`: the ModelForm instance when available;
- `form`: the current form;
- a non-privileged fallback `user`.

This fallback prevents schema callables from accidentally assuming an
anonymous operation has permissions.

## Preserve hidden values

Dynamic schemas often omit fields the current user cannot see. The ModelForm
mixin keeps the initial JSON as the binding's source so omitted or unknown keys
survive a valid submission. Marking a node `readonly` likewise returns its
initial value instead of trusting posted browser data.

Do not use a dynamic schema as the only authorization check for unrelated
model operations. Normal Django view/admin permissions still apply.
