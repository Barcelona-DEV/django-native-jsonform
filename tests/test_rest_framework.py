from copy import deepcopy

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

pytest.importorskip("rest_framework")

from rest_framework import serializers  # noqa: E402

from django_native_jsonform.rest_framework import (  # noqa: E402
    JSONSchemaField,
    JSONSchemaSerializer,
    serializer_from_schema,
)

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "short_title": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"min_score": {"type": "number", "minimum": 0}},
                "required": ["min_score"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title"],
    "additionalProperties": False,
}


def test_factory_reuses_schema_without_mutating_or_coercing_values():
    schema = deepcopy(SCHEMA)
    cls = serializer_from_schema(schema, name="ConfigSerializer")
    schema["required"].append("short_title")
    payload = {"title": "Crossword", "rows": [{"min_score": 0}]}
    serializer = cls(data=payload)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == payload
    assert serializer.data == payload
    serializer.validated_data["rows"][0]["min_score"] = 10
    assert payload["rows"][0]["min_score"] == 0
    assert cls.__name__ == "ConfigSerializer"


@pytest.mark.parametrize(
    "payload", [{}, {"title": ""}, {"title": 2}, {"title": "X", "other": 1}]
)
def test_schema_constraints_are_enforced(payload):
    serializer = serializer_from_schema(SCHEMA)(data=payload)
    assert not serializer.is_valid()
    assert serializer.errors


def test_nested_errors_keep_json_pointer_and_keyword():
    serializer = serializer_from_schema(SCHEMA)(
        data={"title": "X", "rows": [{"min_score": -1}]}
    )
    assert not serializer.is_valid()
    assert serializer.errors["/rows/0/min_score"][0].code == "minimum"


@pytest.mark.parametrize("value", [None, 2, "text", [], False])
def test_object_serializer_rejects_non_objects(value):
    cls = serializer_from_schema(True)
    serializer = cls(data=value)
    assert not serializer.is_valid()
    with pytest.raises(serializers.ValidationError, match="Expected a JSON object"):
        cls().to_representation(value)


def test_field_supports_array_and_nullable_roots():
    field = JSONSchemaField(
        schema={"type": ["array", "null"], "items": {"type": "integer"}}
    )
    assert field.run_validation(None) is None
    assert field.run_validation([0, 1]) == [0, 1]
    with pytest.raises(serializers.ValidationError):
        field.run_validation(["1"])
    with pytest.raises(serializers.ValidationError):
        JSONSchemaField(schema={"type": "integer"}).run_validation(None)


def test_nested_field_and_partial_updates_validate_complete_documents():
    class Parent(serializers.Serializer):
        config = JSONSchemaField(schema=SCHEMA)

    assert Parent(data={}, partial=True).is_valid()
    assert not Parent(data={}).is_valid()
    assert not Parent(data={"config": {}}, partial=True).is_valid()
    instance = Parent(instance={"config": {"title": "X"}})
    assert instance.data == {"config": {"title": "X"}}


def test_class_schema_context_and_instance_override():
    class ContextSerializer(JSONSchemaSerializer):
        schema = staticmethod(lambda context: context["schema"])

    serializer = ContextSerializer(data={"title": "X"}, context={"schema": SCHEMA})
    assert serializer.is_valid(), serializer.errors
    assert ContextSerializer(schema=True, data={"anything": 1}).is_valid()
    with pytest.raises(TypeError, match="Pass a JSON schema"):
        JSONSchemaSerializer()


def test_refs_composition_and_external_resources():
    schema = {"$ref": "urn:config"}
    resource = {"oneOf": [SCHEMA, {"type": "null"}]}
    field = JSONSchemaField(schema=schema, schema_resources={"urn:config": resource})
    assert field.run_validation({"title": "X"}) == {"title": "X"}
    assert field.run_validation(None) is None
    with pytest.raises(serializers.ValidationError):
        field.run_validation({"title": 1})
    with pytest.raises(ImproperlyConfigured):
        JSONSchemaField(schema=schema).run_validation({})


def test_output_is_validated_and_defaults_are_not_inserted():
    field = JSONSchemaField(
        schema={"type": "object", "properties": {"value": {"default": 1}}}
    )
    assert field.run_validation({}) == {}
    assert field.to_representation({}) == {}
    with pytest.raises(serializers.ValidationError):
        field.to_representation([])


def test_many_and_factory_instance_options():
    cls = serializer_from_schema(SCHEMA, json_api=True)
    serializer = cls(data=[{"title": "A"}, {"title": "B"}], many=True, json_api=False)
    assert serializer.is_valid(), serializer.errors
    assert serializer.data == [{"title": "A"}, {"title": "B"}]


@override_settings(JSON_API_FORMAT_FIELD_NAMES="camelize")
def test_json_api_round_trip_is_recursive_and_keeps_distinct_titles():
    pytest.importorskip("rest_framework_json_api")
    cls = serializer_from_schema(SCHEMA, json_api=True)
    payload = {
        "title": "Expert Crossword",
        "shortTitle": "Expert",
        "rows": [{"minScore": 0}],
    }
    serializer = cls(data=payload)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {
        "title": "Expert Crossword",
        "short_title": "Expert",
        "rows": [{"min_score": 0}],
    }
    assert serializer.data == payload
    assert "short_title" not in payload


@pytest.mark.parametrize(
    "format_name, wire_key", [("dasherize", "short-title"), (None, "short_title")]
)
def test_json_api_uses_project_format(format_name, wire_key):
    pytest.importorskip("rest_framework_json_api")
    with override_settings(JSON_API_FORMAT_FIELD_NAMES=format_name):
        cls = serializer_from_schema(SCHEMA, json_api=True)
        serializer = cls(data={"title": "X", wire_key: "Y"})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["short_title"] == "Y"
        assert serializer.data[wire_key] == "Y"


@override_settings(JSON_API_FORMAT_FIELD_NAMES="camelize")
def test_json_api_rejects_key_collisions_in_both_directions():
    pytest.importorskip("rest_framework_json_api")
    field = JSONSchemaField(schema=True, json_api=True)
    with pytest.raises(serializers.ValidationError, match="Multiple keys"):
        field.run_validation({"shortTitle": "A", "short_title": "B"})
    with pytest.raises(serializers.ValidationError, match="Multiple keys"):
        field.to_representation({"short_title": "A", "shortTitle": "B"})
    with pytest.raises(serializers.ValidationError, match="keys must be strings"):
        field.run_validation({1: "invalid"})


def test_unknown_properties_follow_schema_and_formats_are_opt_in():
    field = JSONSchemaField(schema={"type": "object"})
    assert field.run_validation({"custom": 1}) == {"custom": 1}
    field = JSONSchemaField(
        schema={"type": "string", "format": "email"}, validate_formats=True
    )
    with pytest.raises(serializers.ValidationError):
        field.run_validation("invalid")


@override_settings(JSON_API_FORMAT_FIELD_NAMES="camelize")
def test_named_dictionary_subtrees_preserve_keys_in_both_directions():
    field = JSONSchemaField(
        schema={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "short_title": {"type": "string"},
                    "color_tokens": {
                        "type": "object",
                        "properties": {"primarySoft": {"type": "string"}},
                    },
                },
            },
        },
        json_api=True,
        preserve_key_paths=("*.color_tokens",),
    )
    payload = [{"shortTitle": "Short", "colorTokens": {"primarySoft": "#fff"}}]
    internal = field.run_validation(payload)
    assert internal == [
        {"short_title": "Short", "color_tokens": {"primarySoft": "#fff"}}
    ]
    assert field.to_representation(internal) == payload
    internal[0]["color_tokens"]["primarySoft"] = "#000"
    assert payload[0]["colorTokens"]["primarySoft"] == "#fff"


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "string", "nullable": True},
        {"type": ["string", "null"], "nullable": True},
    ],
)
def test_nullable_schema_extension_accepts_explicit_null(schema):
    field = JSONSchemaField(schema=schema)
    assert field.run_validation(None) is None
    assert field.to_representation(None) is None
    with pytest.raises(serializers.ValidationError):
        field.run_validation(42)
