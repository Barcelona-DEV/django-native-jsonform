"""Optional DRF adapters; importing the forms package does not require DRF."""

from __future__ import annotations

from copy import deepcopy

from rest_framework import serializers

from .binding import path_matches
from .validation import JSONSchemaValidator


def _format_keys(value, formatter, preserve_paths=(), path=(), *, incoming=False):
    """Format nested JSON keys without mutating data or silently losing collisions."""
    if any(path_matches(pattern, path) for pattern in preserve_paths):
        return deepcopy(value)
    if isinstance(value, list):
        return [
            _format_keys(
                item, formatter, preserve_paths, (*path, index), incoming=incoming
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, child in value.items():
        if not isinstance(key, str):
            raise serializers.ValidationError("JSON object keys must be strings.")
        formatted = next(iter(formatter({key: None})))
        if formatted in result:
            raise serializers.ValidationError(
                f"Multiple keys resolve to '{formatted}'. Submit only one spelling."
            )
        result[formatted] = _format_keys(
            child,
            formatter,
            preserve_paths,
            (*path, formatted if incoming else key),
            incoming=incoming,
        )
    return result


class _SchemaAdapter:
    schema = None

    def __init__(
        self,
        *args,
        schema=None,
        json_api=False,
        preserve_key_paths=(),
        schema_registry=None,
        schema_resources=None,
        validate_formats=False,
        max_errors=100,
        **kwargs,
    ):
        self.schema = deepcopy(schema if schema is not None else self.schema)
        if self.schema is None:
            raise TypeError("Pass a JSON schema or declare a class-level schema.")
        self.json_api = json_api
        self.preserve_key_paths = tuple(preserve_key_paths)
        self.schema_registry = schema_registry
        self.schema_resources = deepcopy(schema_resources)
        self.validate_formats = validate_formats
        self.max_errors = max_errors
        super().__init__(*args, **kwargs)

    def validate_empty_values(self, data):
        # Nullability belongs to JSON Schema, including nulls inside unions.
        if data is None and not self.read_only:
            return False, data
        return super().validate_empty_values(data)

    def _document_validator(self):
        schema = self.schema(self.context) if callable(self.schema) else self.schema
        return JSONSchemaValidator(
            schema,
            schema_registry=self.schema_registry,
            schema_resources=self.schema_resources,
            validate_formats=self.validate_formats,
            max_errors=self.max_errors,
        )

    def _validate_document(self, data):
        issues = self._document_validator().issues(data)
        if issues:
            errors = {}
            for issue in issues:
                errors.setdefault(issue.pointer or "/", []).append(
                    serializers.ErrorDetail(issue.message, code=issue.keyword)
                )
            raise serializers.ValidationError(errors)

    def _json_api_formatter(self, *, incoming):
        # Keep JSON:API optional for users who only need DRF or Django forms.
        from rest_framework_json_api.utils import (
            format_field_names,
            undo_format_field_names,
        )

        return undo_format_field_names if incoming else format_field_names

    def to_internal_value(self, data):
        if self.json_api:
            data = _format_keys(
                data,
                self._json_api_formatter(incoming=True),
                self.preserve_key_paths,
                incoming=True,
            )
        self._validate_document(data)
        return deepcopy(data)

    def to_representation(self, value):
        self._validate_document(value)
        if self.json_api:
            return _format_keys(
                value, self._json_api_formatter(incoming=False), self.preserve_key_paths
            )
        return deepcopy(value)


class JSONSchemaField(_SchemaAdapter, serializers.Field):
    """Validate a JSON attribute from its schema, with optional JSON:API key casing.

    Supports any JSON root type. A supplied value is always a complete document,
    including during PATCH. Omitting the entire field follows DRF's partial rules.
    """


class JSONSchemaSerializer(_SchemaAdapter, serializers.BaseSerializer):
    """Object serializer backed by JSON Schema instead of hand-written DRF fields.

    Use JSONSchemaField for scalar/array roots, or many=True for a list of objects.
    Persistence of JSON values belongs to the enclosing model serializer or view.
    """

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        return super().to_internal_value(data)

    def to_representation(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        return super().to_representation(value)


def serializer_from_schema(schema, *, name="GeneratedJSONSchemaSerializer", **options):
    """Return a reusable serializer class for an object schema or context callable.

    Options are the same as JSONSchemaSerializer; instance arguments override them.
    """
    frozen_schema = deepcopy(schema)
    frozen_options = deepcopy(options)

    class GeneratedSerializer(JSONSchemaSerializer):
        def __init__(self, *args, **kwargs):
            super().__init__(
                *args,
                schema=kwargs.pop("schema", deepcopy(frozen_schema)),
                **{**deepcopy(frozen_options), **kwargs},
            )

    GeneratedSerializer.__name__ = name
    GeneratedSerializer.__qualname__ = name
    return GeneratedSerializer
