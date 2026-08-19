# Supported JSON Schema

The library intentionally implements the subset that maps cleanly to editable
Django forms. It is not a general-purpose JSON Schema validator; Django fields
remain the validation engine.

## Types

| JSON Schema | Django representation |
| --- | --- |
| `object` | nested fieldset and child fields |
| `array` | repeatable child form nodes |
| `string` | `CharField` |
| `integer` | `IntegerField` |
| `number` | `DecimalField` |
| `boolean` | `BooleanField` |
| `null` | `JSONField` |

When `type` is absent from a scalar `const` or `default`, it is inferred.

## String formats

| Format | Django field/widget |
| --- | --- |
| `date` | `DateField` with a date input |
| `time` | `TimeField` with a time input |
| `date-time` | `DateTimeField` with a datetime-local input |
| `email` | `EmailField` |
| `uri`, `url` | `URLField` |
| `uuid` | `UUIDField` |
| `color` | `CharField` with an HTML color input |

Register any domain format that is not built in. Unknown formats fall back to
the factory for their base JSON type.

## Constraints

Supported scalar and collection keywords include:

- `required` on objects, plus the historical leaf-level boolean form;
- `minLength`, `maxLength`, and `pattern` for strings;
- `minimum`, `maximum`, and `multipleOf` for numbers;
- `minItems`, `maxItems`, and `uniqueItems` for arrays;
- `enum` and the extended `choices` form;
- `const` for fixed hidden values;
- `default` with explicit persistence policy;
- `readOnly`/`readonly`;
- local `$ref` values beginning with `#/`.

`choices` can carry labels:

```python
{
    "type": "string",
    "choices": [
        {"value": "draft", "label": "Draft"},
        {"value": "published", "title": "Published"},
    ],
}
```

## `oneOf`

Each branch becomes a selectable form section. Prefer a discriminator whose
value is fixed with `const` or a one-item `enum`:

```python
{
    "oneOf": [
        {
            "title": "External link",
            "properties": {
                "kind": {"const": "external"},
                "url": {"type": "string", "format": "uri"},
            },
            "required": ["url"],
        },
        {
            "title": "Internal page",
            "properties": {
                "kind": {"const": "internal"},
                "page_id": {"type": "integer"},
            },
            "required": ["page_id"],
        },
    ]
}
```

The shared `kind` discriminator is inferred. OpenAPI-style
`discriminator: {"propertyName": "kind"}` and mappings to local `$ref`
branches are also supported.

Changing the selector updates the visible branch immediately. The server still
rebuilds and validates only the selected branch on submission.

## Extensions understood by the renderer

The package recognizes several intentionally non-standard presentation keys:

- `title`, `description`, `help_text`, or `helpText`;
- `widget`: name registered in the form registry;
- `attrs`: HTML attributes merged onto the widget;
- `choices`: labeled alternative to `enum`.

For behavior that should not live in portable JSON Schema, prefer
[per-path overrides](customization.md).

## Not currently implemented

Full boolean schema composition (`allOf`, `anyOf`, `not`), remote references,
conditional `if`/`then`/`else`, property-name constraints, and arbitrary
`additionalProperties` editing are not built in. Consumer validators can still
enforce those rules after the Django fields are cleaned.
