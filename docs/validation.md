# Validation

Every generated scalar is a real Django field, cleaned through Django's normal
pipeline. The composite field then reconstructs the complete JSON document and
validates it independently with `jsonschema`'s Draft 2020-12 validator. Finally,
application validators run. Custom fields cannot bypass document constraints.

Errors include JSON Pointer locations (`/levels/0/points`), appear in the widget
summary and attach to the nearest editable child. Array locations account for
deleted rows. Invalid schemas/unresolved references raise `ImproperlyConfigured`
instead of being silently ignored. `max_errors=100` bounds collected errors.

## Resources and formats

```python
configuration = JSONSchemaFormField(
    schema={"$ref": "urn:example:configuration"},
    schema_resources={
        "urn:example:configuration": {
            "type": "object",
            "properties": {"contact": {"type": "string", "format": "email"}},
            "required": ["contact"],
            "additionalProperties": False,
        },
    },
    validate_formats=True,
)
```

Alternatively pass `schema_registry=referencing.Registry(...)` for explicitly
controlled resource retrieval. The default registry does not access the network.
`format_checker` accepts a `jsonschema.FormatChecker`, including custom checks.
Document format checks default to off; built-in Django format fields retain
their own validation. Content keywords do not decode files automatically.

For validation outside a form:

```python
from django_native_jsonform import JSONSchemaValidator

validator = JSONSchemaValidator(SCHEMA, validate_formats=True)
validator(value)  # Raises JSONFormValidationError on an invalid document.
issues = validator.issues(value)  # SchemaIssue path, pointer, keyword, message.
```

`normalize_schema` translates legacy `choices`, boolean leaf `required` and
`readonly` without mutating the original schema or data in `const`/`default`.

## Whole-value validators

Pass Django validators to `JSONSchemaFormField` as usual:

```python
def validate_configuration(value):
    if value.get("starts_on") and value.get("ends_on"):
        if value["starts_on"] > value["ends_on"]:
            raise ValidationError("The date range is invalid.")


configuration = JSONSchemaFormField(
    schema=SCHEMA,
    validators=[validate_configuration],
)
```

## Errors attached to a child path

Use `JSONFormValidationError` to put errors next to generated fields:

```python
from django_native_jsonform import JSONFormValidationError


def validate_configuration(value):
    errors = {}
    if value.get("path", "").endswith("/"):
        errors["path"] = "Path must not end with /."
    for index, level in enumerate(value.get("levels", [])):
        if level.get("points", 0) < 0:
            errors[f"levels.{index}.points"] = "Points cannot be negative."
    if errors:
        raise JSONFormValidationError(
            "Invalid configuration",
            errors=errors,
        )
```

Paths accept legacy dot notation or JSON Pointer (`/levels/0/points`). Use
JSON Pointer for property names containing dots or slashes. Array indices refer
to the reconstructed document, after deleted rows are removed. Errors attach to
the nearest active editable node and remain available in the widget summary.

## Custom Django fields

A registered field or an override may implement any normal Django validation:
validators, `to_python`, `validate`, and `run_validators`. Its cleaned value is
serialized into JSON through the built-in serializer or a path-specific
`serialize` callable.

The built-in serializer handles Django models/querysets, `Decimal`, date/time
objects, and UUIDs.
