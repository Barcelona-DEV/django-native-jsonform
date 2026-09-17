"""Document validation independent of Django fields and renderer decisions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from itertools import islice
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from jsonschema import Draft202012Validator, FormatChecker, validators
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from .exceptions import JSONFormValidationError

Schema = dict[str, Any] | bool

SCHEMA_MAPS = {
    "properties",
    "patternProperties",
    "$defs",
    "definitions",
    "dependentSchemas",
}
SCHEMA_LISTS = {"allOf", "anyOf", "oneOf", "prefixItems"}
SCHEMA_SINGLES = {
    "additionalProperties",
    "unevaluatedProperties",
    "propertyNames",
    "items",
    "additionalItems",
    "contains",
    "unevaluatedItems",
    "not",
    "if",
    "then",
    "else",
    "contentSchema",
}
UI_KEYS = {"widget", "attrs", "help_text", "helpText", "choices", "readonly", "handler"}


def normalize_schema(schema: Schema) -> Schema:
    """Normalize legacy UI extensions only at schema locations, never in data.

    In particular, defaults/const/enum/examples may themselves contain keys
    named properties or required. Those are JSON values, not schemas.
    """
    if isinstance(schema, bool):
        return schema
    if not isinstance(schema, dict):
        raise ImproperlyConfigured("A JSON schema must be an object or boolean.")
    result = {
        key: deepcopy(value) for key, value in schema.items() if key not in UI_KEYS
    }
    if result.pop("nullable", False) is True and "type" in result:
        types = result["type"]
        types = [types] if isinstance(types, str) else list(types)
        result["type"] = types if "null" in types else [*types, "null"]
    if isinstance(result.get("required"), bool):
        result.pop("required")
    if "readonly" in schema and "readOnly" not in result:
        result["readOnly"] = schema["readonly"]
    if "choices" in schema and "enum" not in result:
        if not isinstance(schema["choices"], (list, tuple)):
            raise ImproperlyConfigured("choices must be an array.")
        result["enum"] = [
            deepcopy(choice.get("value"))
            if isinstance(choice, dict)
            else deepcopy(choice)
            for choice in schema["choices"]
        ]
    for key in SCHEMA_MAPS & result.keys():
        if not isinstance(result[key], dict):
            raise ImproperlyConfigured(f"{key} must be an object of schemas.")
        if any(not isinstance(name, str) for name in result[key]):
            raise ImproperlyConfigured(f"{key} names must be strings.")
        result[key] = {
            name: normalize_schema(child) for name, child in result[key].items()
        }
    for key in SCHEMA_LISTS & result.keys():
        if not isinstance(result[key], list):
            raise ImproperlyConfigured(f"{key} must be an array of schemas.")
        result[key] = [normalize_schema(child) for child in result[key]]
    for key in SCHEMA_SINGLES & result.keys():
        result[key] = normalize_schema(result[key])
    # The leaf-level required extension belongs on the enclosing object.
    required = result.get("required", [])
    if not isinstance(required, list):
        raise ImproperlyConfigured("required must be an array of property names.")
    for name, child in schema.get("properties", {}).items():
        if (
            isinstance(child, dict)
            and child.get("required") is True
            and name not in required
        ):
            required.append(name)
    if required:
        result["required"] = required
    for key in ("title", "description"):
        if key in result:
            result[key] = str(result[key])
    return result


def _multiple_of(validator, divisor, instance, schema):
    if not validator.is_type(instance, "number"):
        return
    # Decimal JSON numbers must not fail because 0.3 / 0.1 is a binary float.
    if (Fraction(str(instance)) / Fraction(str(divisor))).denominator != 1:
        yield ValidationError(f"{instance!r} is not a multiple of {divisor}")


def _properties(validator, properties, instance, schema):
    if not validator.is_type(instance, "object"):
        return
    for name, subschema in properties.items():
        if name not in instance:
            continue
        if subschema is False:
            # jsonschema's boolean-schema fast path skips descend's path prefix.
            yield ValidationError(
                f"False schema does not allow {instance[name]!r}",
                path=[name],
                schema_path=[name],
            )
        else:
            yield from validator.descend(
                instance[name], subschema, path=name, schema_path=name
            )


DocumentValidator = validators.extend(
    Draft202012Validator, {"multipleOf": _multiple_of, "properties": _properties}
)


@dataclass(frozen=True)
class SchemaIssue:
    path: tuple[str | int, ...]
    schema_path: tuple[str | int, ...]
    keyword: str
    message: str

    @property
    def pointer(self) -> str:
        return "".join(
            "/" + str(part).replace("~", "~0").replace("/", "~1") for part in self.path
        )


class JSONSchemaValidator:
    """Draft 2020-12 validation with explicit resources and optional formats.

    No remote schema is fetched automatically. Supply resources keyed by URI,
    or a referencing.Registry when application-controlled retrieval is needed.
    Format checks are opt-in; content* keywords remain annotations as required
    by the default content vocabulary.
    """

    def __init__(
        self,
        schema: Schema,
        *,
        schema_registry: Registry | None = None,
        schema_resources: Mapping[str, Schema] | None = None,
        validate_formats: bool = False,
        format_checker: FormatChecker | None = None,
        max_errors: int = 100,
    ) -> None:
        self.schema = normalize_schema(schema)
        if max_errors < 1:
            raise ValueError("max_errors must be positive")
        self.max_errors = max_errors
        if isinstance(self.schema, dict):
            dialect = self.schema.get(
                "$schema", Draft202012Validator.META_SCHEMA["$id"]
            )
            if (
                not isinstance(dialect, str)
                or dialect.rstrip("#") != Draft202012Validator.META_SCHEMA["$id"]
            ):
                raise ImproperlyConfigured(
                    f"Unsupported schema dialect: {dialect}. Use Draft 2020-12."
                )
        try:
            Draft202012Validator.check_schema(self.schema)
        except SchemaError as exc:
            raise ImproperlyConfigured(f"Invalid JSON schema: {exc.message}") from exc
        registry = schema_registry if schema_registry is not None else Registry()
        for uri, resource_schema in (schema_resources or {}).items():
            normalized = normalize_schema(resource_schema)
            try:
                Draft202012Validator.check_schema(normalized)
            except SchemaError as exc:
                raise ImproperlyConfigured(
                    f"Invalid resource {uri}: {exc.message}"
                ) from exc
            resource = Resource.from_contents(
                normalized, default_specification=DRAFT202012
            )
            registry = registry.with_resource(uri, resource)
        checker = format_checker or (FormatChecker() if validate_formats else None)
        self.validator = DocumentValidator(
            self.schema, registry=registry, format_checker=checker
        )

    def issues(self, value: Any) -> list[SchemaIssue]:
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError, RecursionError) as exc:
            return [
                SchemaIssue((), (), "json", f"Value is not JSON serializable: {exc}")
            ]
        pending = [((), value)]
        while pending:
            path, item = pending.pop()
            if isinstance(item, dict):
                if any(not isinstance(key, str) for key in item):
                    return [
                        SchemaIssue(
                            path, (), "json", "JSON object keys must be strings."
                        )
                    ]
                pending.extend(((*path, key), child) for key, child in item.items())
            elif isinstance(item, list):
                pending.extend(
                    ((*path, index), child) for index, child in enumerate(item)
                )
            elif item is not None and not isinstance(item, (str, bool, int, float)):
                return [SchemaIssue(path, (), "json", "Value must use JSON types.")]
        try:
            errors = list(islice(self.validator.iter_errors(value), self.max_errors))
        except (Unresolvable, RecursionError) as exc:
            raise ImproperlyConfigured(
                "JSON schema reference cannot be resolved "
                "or recurses without progress. "
                "Register referenced resources explicitly."
            ) from exc
        return [
            SchemaIssue(
                tuple(error.absolute_path),
                tuple(error.absolute_schema_path),
                str(error.validator),
                error.message,
            )
            for error in errors
        ]

    def __call__(self, value: Any) -> None:
        issues = self.issues(value)
        if issues:
            errors: dict[str, list[str]] = {}
            for issue in issues:
                errors.setdefault(issue.pointer, []).append(issue.message)
            raise JSONFormValidationError(
                "JSON schema validation failed.", errors=errors
            )
