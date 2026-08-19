from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django import forms
from django.core.exceptions import ValidationError

FieldFactory = Callable[["FieldFactoryContext"], forms.Field]
WidgetFactory = Callable[["WidgetFactoryContext"], forms.Widget]


class ColorInput(forms.TextInput):
    input_type = "color"


@dataclass(frozen=True)
class FieldFactoryContext:
    path: tuple[str | int, ...]
    schema: dict[str, Any]
    required: bool
    disabled: bool
    form_context: Any = None


@dataclass(frozen=True)
class WidgetFactoryContext:
    """Information passed to a registered widget factory."""

    path: tuple[str | int, ...]
    schema: dict[str, Any]
    form_context: Any = None


class JSONFormRegistry:
    """Configurable mapping from schema types/formats to Django fields/widgets."""

    def __init__(self) -> None:
        self._field_factories: dict[tuple[str, str | None], FieldFactory] = {}
        self._widget_factories: dict[str, WidgetFactory] = {}

    def clone(self) -> JSONFormRegistry:
        registry = type(self)()
        registry._field_factories = self._field_factories.copy()
        registry._widget_factories = self._widget_factories.copy()
        return registry

    def register_field(
        self,
        json_type: str,
        factory: FieldFactory | None = None,
        *,
        format: str | None = None,
    ):
        """Register a field factory directly or use this method as a decorator."""

        def decorator(candidate: FieldFactory) -> FieldFactory:
            self._field_factories[(json_type, format)] = candidate
            return candidate

        return decorator(factory) if factory is not None else decorator

    def register_widget(self, name: str, factory: WidgetFactory | None = None):
        """Register a named widget factory directly or as a decorator."""

        def decorator(candidate: WidgetFactory) -> WidgetFactory:
            self._widget_factories[name] = candidate
            return candidate

        return decorator(factory) if factory is not None else decorator

    def create_field(self, context: FieldFactoryContext) -> forms.Field:
        json_type = context.schema.get("type") or _infer_scalar_type(context.schema)
        schema_format = context.schema.get("format")
        factory = self._field_factories.get((json_type, schema_format))
        if factory is None:
            factory = self._field_factories.get((json_type, None))
        if factory is None:
            raise ValueError(
                f"No Django field registered for JSON type {json_type!r} "
                f"and format {schema_format!r}"
            )
        field = factory(context)
        widget_hint = context.schema.get("widget")
        if widget_hint:
            field.widget = self.create_widget(
                widget_hint,
                path=context.path,
                schema=context.schema,
                form_context=context.form_context,
            )
        return field

    def create_widget(
        self,
        name: str,
        *,
        path: tuple[str | int, ...] = (),
        schema: dict[str, Any],
        form_context: Any = None,
    ) -> forms.Widget:
        try:
            factory = self._widget_factories[name]
        except KeyError as exc:
            raise ValueError(f"No Django widget registered as {name!r}") from exc
        return factory(
            WidgetFactoryContext(
                path=path,
                schema=schema,
                form_context=form_context,
            )
        )


def _common_kwargs(context: FieldFactoryContext) -> dict[str, Any]:
    schema = context.schema
    return {
        "required": context.required,
        "disabled": context.disabled,
        "label": schema.get("title") or _humanize(context.path),
        "help_text": schema.get("help_text")
        or schema.get("helpText")
        or schema.get("description", ""),
    }


def _string_field(context: FieldFactoryContext) -> forms.Field:
    kwargs = _common_kwargs(context)
    schema = context.schema
    kwargs["min_length"] = schema.get("minLength")
    kwargs["max_length"] = schema.get("maxLength")
    if schema.get("pattern"):
        return forms.RegexField(regex=schema["pattern"], **kwargs)
    return forms.CharField(**kwargs)


def _date_field(context: FieldFactoryContext) -> forms.Field:
    kwargs = _common_kwargs(context)
    return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **kwargs)


def _time_field(context: FieldFactoryContext) -> forms.Field:
    kwargs = _common_kwargs(context)
    return forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}), **kwargs)


def _uri_field(context: FieldFactoryContext) -> forms.Field:
    return forms.URLField(**_common_kwargs(context))


def _email_field(context: FieldFactoryContext) -> forms.Field:
    return forms.EmailField(**_common_kwargs(context))


def _uuid_field(context: FieldFactoryContext) -> forms.Field:
    return forms.UUIDField(**_common_kwargs(context))


def _datetime_field(context: FieldFactoryContext) -> forms.Field:
    kwargs = _common_kwargs(context)
    return forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), **kwargs
    )


def _integer_field(context: FieldFactoryContext) -> forms.Field:
    schema = context.schema
    return forms.IntegerField(
        min_value=schema.get("minimum"),
        max_value=schema.get("maximum"),
        **_common_kwargs(context),
    )


def _number_field(context: FieldFactoryContext) -> forms.Field:
    schema = context.schema
    if schema.get("multipleOf") == 1:
        return _integer_field(context)
    validators = []
    if schema.get("multipleOf") is not None:
        validators.append(_multiple_of(schema["multipleOf"]))
    return forms.DecimalField(
        min_value=schema.get("minimum"),
        max_value=schema.get("maximum"),
        validators=validators,
        **_common_kwargs(context),
    )


def _boolean_field(context: FieldFactoryContext) -> forms.Field:
    kwargs = _common_kwargs(context)
    # Django's required=True means "must be checked", whereas JSON Schema's
    # required means "the key must exist". Presence is tracked separately.
    kwargs["required"] = False
    return forms.BooleanField(**kwargs)


def _json_field(context: FieldFactoryContext) -> forms.Field:
    return forms.JSONField(**_common_kwargs(context))


def _infer_scalar_type(schema: dict[str, Any]) -> str:
    value = schema.get("const", schema.get("default"))
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, (float, Decimal)):
        return "number"
    return "string"


def _multiple_of(multiple: int | float | Decimal):
    divisor = Decimal(str(multiple))

    def validator(value):
        if value is not None and Decimal(str(value)) % divisor:
            raise ValidationError(f"Ensure this value is a multiple of {multiple}.")

    return validator


def _humanize(path: tuple[str | int, ...]) -> str:
    if not path:
        return "Value"
    return str(path[-1]).replace("_", " ").strip().capitalize()


default_registry = JSONFormRegistry()
default_registry.register_field("string", _string_field)
default_registry.register_field("string", _date_field, format="date")
default_registry.register_field("string", _time_field, format="time")
default_registry.register_field("string", _datetime_field, format="date-time")
default_registry.register_field("string", _uri_field, format="uri")
default_registry.register_field("string", _uri_field, format="url")
default_registry.register_field("string", _email_field, format="email")
default_registry.register_field("string", _uuid_field, format="uuid")
default_registry.register_field("integer", _integer_field)
default_registry.register_field("number", _number_field)
default_registry.register_field("boolean", _boolean_field)
default_registry.register_field("null", _json_field)
default_registry.register_widget("textarea", lambda context: forms.Textarea())
default_registry.register_widget("hidden", lambda context: forms.HiddenInput())
default_registry.register_widget("color", lambda context: ColorInput())


def clone_field(field: forms.Field) -> forms.Field:
    return deepcopy(field)
