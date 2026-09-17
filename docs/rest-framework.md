# Django REST Framework and JSON:API

The optional adapter validates JSON attributes from the same schemas as the native
forms. You do not need to duplicate their properties as handwritten DRF fields.
Install the integration you use:

```bash
pip install 'django-native-jsonform[drf]'
# Includes DRF through the JSON:API dependency:
pip install 'django-native-jsonform[jsonapi]'
```

Import adapters from `django_native_jsonform.rest_framework`. The main package does
not import DRF or JSON:API, so installations used only for forms stay independent.

## Generate an object serializer

```python
from django_native_jsonform.rest_framework import serializer_from_schema

config_schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "short_title": {"type": "string"},
    },
    "required": ["title"],
    "additionalProperties": False,
}

ConfigSerializer = serializer_from_schema(
    config_schema,
    name="ConfigSerializer",
    json_api=True,
)

serializer = ConfigSerializer(
    data={"title": "Expert Crossword", "shortTitle": "Expert"}
)
serializer.is_valid(raise_exception=True)
# With JSON_API_FORMAT_FIELD_NAMES = "camelize":
# serializer.validated_data == {"title": "Expert Crossword", "short_title": "Expert"}
# serializer.data == {"title": "Expert Crossword", "shortTitle": "Expert"}
```

The factory returns a reusable DRF `BaseSerializer` subclass. `many=True` supports
lists of objects. For scalar or array document roots, use `JSONSchemaField` instead.
It is a schema-backed serializer, not a generator of individual DRF field objects:
browsable forms and OpenAPI field enumeration do not appear automatically.

## Attach a schema to a model JSONField

```python
from rest_framework import serializers
from django_native_jsonform.rest_framework import JSONSchemaField


class GameConfigurationSerializer(serializers.ModelSerializer):
    config = JSONSchemaField(schema=config_schema, json_api=True)
    config_by_dates = JSONSchemaField(
        schema={"type": "array", "items": config_schema},
        json_api=True,
        required=False,
    )

    class Meta:
        model = GameConfiguration  # Your application's model.
        fields = ["id", "config", "config_by_dates"]
```

The parent model serializer persists the validated JSON values normally. Standalone
generated serializers validate and represent data; implement `create()` / `update()`
in your application if you want to call their `save()` method directly.

## Input and output naming

Without `json_api=True`, keys match the schema exactly and no renaming takes place.
With it, the adapter recursively calls JSON:API's `undo_format_field_names()` on
input and `format_field_names()` on output. It honors
`JSON_API_FORMAT_FIELD_NAMES`, including `camelize`, `dasherize`, or no formatting.
Declare Python/storage keys in snake_case in the schema for this mode.

Conversion applies to every dictionary key, including arbitrary keys accepted by
`additionalProperties`, and dictionaries inside arrays. It does not change string
values, numbers, booleans or nulls. Use plain mode for dictionaries whose keys are
opaque identifiers that must retain their exact spelling. Colliding spellings are
rejected on both input and output instead of overwriting values. Input objects are
not mutated.

This conversion is performed by this adapter. Merely declaring a nested serializer
does not make Django or JSON:API's top-level parser recursively rename JSON keys.

## Validation and PATCH semantics

Validation reuses `JSONSchemaValidator`, including nested objects, arrays, nullable
values, required properties, enums, bounds, composition, conditionals and references.
Unknown properties follow `additionalProperties` / `unevaluatedProperties`; they
are not silently discarded. Values retain their JSON types: a numeric string does
not become a number. Output is also validated before formatting.

Defaults are annotations and are not inserted. JSON Schema `readOnly` / `writeOnly`
annotations do not implement API access policies: use DRF field-level options or
application logic for those policies. Business rules such as filling an empty title
from another field remain explicit application validators.

A supplied JSON attribute is a complete document, even on PATCH. The schema's
`required` rules still apply. The enclosing serializer's `partial=True` allows
omitting the entire attribute; it does not turn the JSON document into a recursive
merge patch. Applications requiring document merging must merge explicitly before
full schema validation.

Validation errors are mappings from JSON Pointers to DRF error messages, with the
schema keyword retained as the error code. For example, an invalid minimum inside
an array is reported at `/rows/0/min_score`. Error pointer keys use schema names.

## Dynamic schemas and references

Pass a callable accepting the DRF context dictionary to select a schema at runtime:

```python
ConfigSerializer = serializer_from_schema(
    lambda context: context["config_schema"],
    json_api=True,
)
serializer = ConfigSerializer(
    data=payload,
    context={"config_schema": config_schema},
)
```

The callable receives DRF context, not the native form's `BuildContext`. A wrapper
can adapt existing form schema factories. Both adapters also accept
`schema_registry`, `schema_resources`, `validate_formats` (default `False`), and
`max_errors` (default `100`). Reference resources must be registered explicitly;
validation never fetches remote schemas automatically.

For JSON dictionaries whose keys are data (such as CSS token names), pass
`preserve_key_paths=("**.colors", "**.dark_colors")`. Matching subtrees retain their
keys in both directions; the property naming the subtree still follows JSON:API.
Paths use internal property names, dots, `*` for one segment and `**` for any depth.
Schema validation still applies inside preserved subtrees.
