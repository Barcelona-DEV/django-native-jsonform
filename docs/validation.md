# Validation

Every generated scalar is a real Django field. Constraints such as length,
regular expressions, numeric bounds, choices, dates, URLs, email addresses,
UUIDs, and custom field validation use Django's normal `clean()` path.

The composite field additionally validates array sizes and uniqueness before
reconstructing the final Python object.

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

Paths use the same dot notation as overrides. Error messages for paths that do
not exist in the active schema remain available as non-field errors.

## Custom Django fields

A registered field or an override may implement any normal Django validation:
validators, `to_python`, `validate`, and `run_validators`. Its cleaned value is
serialized into JSON through the built-in serializer or a path-specific
`serialize` callable.

The built-in serializer handles Django models/querysets, `Decimal`, date/time
objects, and UUIDs.
