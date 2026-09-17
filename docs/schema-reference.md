# Supported JSON Schema

Native Django fields edit the value; `jsonschema` independently validates the
reconstructed document against Draft 2020-12. Changing a widget, serializer or
template does not bypass schema constraints. Validation coverage and visual
editing are separate: complex subtrees use a Django `JSONField`/`Textarea`.

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
- `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, and `multipleOf`;
- `minItems`, `maxItems`, `uniqueItems`, `contains`, `minContains`, `maxContains`;
- `prefixItems`, `items`, `unevaluatedItems`;
- `minProperties`, `maxProperties`, `propertyNames`, `patternProperties`;
- `additionalProperties`, `unevaluatedProperties`, `dependentRequired`;
- `allOf`, `anyOf`, `oneOf`, `not`, `if`/`then`/`else`, `dependentSchemas`;
- boolean schemas and multiple `type` values, including explicit `null`;
- `enum` and the extended `choices` form;
- `const` for fixed hidden values;
- `default` with explicit persistence policy;
- `readOnly`/`readonly`;
- `$ref`, `$defs`, `$id`, `$anchor`, `$dynamicRef`, and `$dynamicAnchor`.

Array add/remove controls also enforce `minItems` and `maxItems`, including
`maxItems: 0`. Existing values are not silently truncated. `max_array_items`
is an editor resource budget, not a schema constraint: larger initial lists
use the JSON editor. Excessive submitted control counts are rejected.

`required` means a property must exist, not that it must be truthy. Missing,
`null`, empty containers, empty strings, zero and `false` are distinct. Use
`minLength: 1` to disallow empty strings. Whitespace is preserved. `uniqueItems`
uses JSON equality: `true` and `1` differ, but `1` and `1.0` are the same number.

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

Branch children are rendered recursively, including when the union declares
`type: object` or an object `default`. The same behavior applies inside object
properties, array items and local `$ref` targets. Defaults do not force a raw
JSON editor.

Nullable numeric fields (`type: ["number", "null"]` or
`type: ["integer", "null"]`) use one numeric input. Existing null values appear
blank; clearing an optional populated value omits it under automatic presence.
Minimum, maximum and document validation still apply. Schemas with no declared
properties remain free-form JSON: the renderer cannot infer missing field
definitions from a null value.

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

Changing the selector updates the visible branch immediately. The server
rebuilds the selected branch, then validates the resulting document against the
complete original schema, including the exact-one rule.

## Extensions understood by the renderer

The package recognizes several intentionally non-standard presentation keys:

- `title`, `description`, `help_text`, or `helpText`;
- `widget`: name registered in the form registry;
- `attrs`: HTML attributes merged onto the widget;
- `choices`: labeled alternative to `enum`.

For behavior that should not live in portable JSON Schema, prefer
[per-path overrides](customization.md).

## JSON editor fallback

`allOf`, `anyOf`, conditionals, `dependentSchemas`, dynamic property maps,
`propertyNames`, tuple arrays (`prefixItems`), boolean schemas, external/anchor
references, recursive boundaries and mixed number/integer type unions use a
native JSON editor. These conditions are validated, but do not automatically
show/hide individual generated fields when dependencies change.

Only the affected subtree uses JSON; siblings retain normal widgets. Replace
its `field`, `widget`, `serialize`, `deserialize` or `template` to integrate your
own editor. Force JSON using `overrides={"configuration": {"editor": "json"}}`.

`max_depth` (32), `max_nodes` (5000), and `max_array_items` (250) bound generated
controls. Depth/array boundaries use JSON editors; a total node overflow raises
a configuration error instead of constructing a partial form.

## Formats, content and dialects

The document validator treats `format` as an annotation by default. Enable
`validate_formats=True` or supply `format_checker` to assert supported formats.
Existing Django format fields (email, URL, date, etc.) still perform their own
validation/conversion. Override their fields when exact wire-format preservation
is needed. Unknown formats remain annotations unless registered with the checker.

`contentEncoding`, `contentMediaType` and `contentSchema` are annotations: the
library does not automatically decode uploads or validate decoded content.
`examples`, `deprecated` and `writeOnly` do not impose assertions or access
control. Application permissions must be implemented explicitly.

Absent `$schema` means Draft 2020-12. Other declared root dialects are rejected.
Older `definitions` pointers still resolve, but older validation keywords such
as `dependencies` and array-valued `items` must be migrated. Custom keywords
require application validators; this is not a custom metaschema engine.

No schema is fetched automatically from the network. Register resources with
`schema_resources`, or supply an application-controlled `referencing.Registry`
using `schema_registry`. See [validation](validation.md).

Semantics follow the official [validation vocabulary](https://json-schema.org/draft/2020-12/json-schema-validation)
and [core specification](https://json-schema.org/draft/2020-12/json-schema-core),
using [python-jsonschema](https://python-jsonschema.readthedocs.io/en/stable/validate/).
Regex handling inherits that validator's Python regular-expression behavior;
this package does not claim independent conformance certification.
