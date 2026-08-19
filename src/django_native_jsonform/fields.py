from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from types import SimpleNamespace
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .binding import MISSING, FieldResolver, JSONFormSubmission
from .exceptions import JSONFormValidationError
from .registry import JSONFormRegistry
from .renderers import JSONFormRenderer
from .widgets import JSONSchemaWidget


class JSONSchemaFormField(forms.Field):
    """A Django form field whose children are generated from a JSON schema.

    ``overrides`` accepts exact paths and ``*``/``**`` patterns. Each override
    may replace the field, widget, attrs, serializer, template, required flag,
    read-only state, or default materialization policy for that path.
    """

    widget = JSONSchemaWidget

    def __init__(
        self,
        *,
        schema: dict[str, Any] | Callable[..., dict[str, Any]],
        registry: JSONFormRegistry | None = None,
        overrides: Mapping[str, Mapping[str, Any] | Callable] | None = None,
        field_resolver: FieldResolver | None = None,
        renderer: JSONFormRenderer | None = None,
        templates: Mapping[str, str] | None = None,
        default_policy: str = "preserve",
        preserve_unknown: bool = True,
        max_array_items: int = 250,
        **kwargs,
    ) -> None:
        widget_attrs = kwargs.pop("widget_attrs", None)
        widget = JSONSchemaWidget(
            schema=schema,
            registry=registry,
            overrides=overrides,
            field_resolver=field_resolver,
            renderer=renderer,
            templates=templates,
            default_policy=default_policy,
            preserve_unknown=preserve_unknown,
            max_array_items=max_array_items,
            root_required=kwargs.get("required", True),
            attrs=widget_attrs,
        )
        super().__init__(widget=widget, **kwargs)

    def set_context(self, context: Any) -> None:
        self.widget.set_context(context)

    def clean(self, value):
        if not isinstance(value, JSONFormSubmission):
            value = super().clean(value)
            return value

        binding = self.widget.bind(value)
        self.widget.binding = binding
        if not binding.is_valid():
            raise ValidationError(
                _("Please correct the errors inside this JSON form."),
                code="invalid_json_form",
            )
        cleaned = binding._clean_node(binding.root)
        if cleaned is MISSING:
            cleaned = None
        self.validate(cleaned)
        self._run_json_validators(cleaned, binding)
        return cleaned

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        if not isinstance(data, JSONFormSubmission):
            return super().has_changed(initial, data)
        binding = self.widget.bind(data)
        self.widget.binding = binding
        if not binding.is_valid():
            return True
        cleaned = binding._clean_node(binding.root)
        if cleaned is MISSING:
            cleaned = None
        return initial != cleaned

    def _run_json_validators(self, value, binding) -> None:
        errors = []
        for validator in self.validators:
            try:
                validator(value)
            except JSONFormValidationError as exc:
                binding.add_path_errors(exc.path_errors)
                errors.extend(exc.error_list)
            except ValidationError as exc:
                errors.extend(exc.error_list)
        if errors:
            raise ValidationError(errors)


class JSONSchemaFormMixin:
    """Inject context and initial JSON into schema fields in any Django form."""

    json_form_context: Any = None

    def __init__(self, *args, json_form_context=None, **kwargs):
        self._json_form_context = json_form_context
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field, JSONSchemaFormField):
                field.set_context(self.get_json_form_context(name))
                # Seed the widget before validation so a bound form can merge
                # generated values into the model's existing sparse JSON.
                initial = self.initial.get(name)
                field.widget.binding = field.widget.build_binding(
                    initial=initial,
                    prefix=self.add_prefix(name),
                )

    def get_json_form_context(self, field_name: str) -> Any:
        fallback_user = SimpleNamespace(
            is_superuser=False,
            has_perm=lambda permission: False,
        )
        context = self._json_form_context
        if context is None:
            context = self.json_form_context
        if callable(context):
            context = context(self, field_name)
        if context is None:
            return SimpleNamespace(
                obj=getattr(self, "instance", None),
                user=fallback_user,
                form=self,
            )
        if isinstance(context, dict):
            values = {
                "obj": getattr(self, "instance", None),
                "user": fallback_user,
                **context,
                "form": self,
            }
            return SimpleNamespace(**values)
        if not hasattr(context, "user"):
            with suppress(AttributeError, TypeError):
                context.user = fallback_user
        if not hasattr(context, "form"):
            with suppress(AttributeError, TypeError):
                context.form = self
        return context


class JSONSchemaModelFormMixin(JSONSchemaFormMixin):
    """Semantic alias for forms which also inherit from ``ModelForm``."""


class JSONSchemaModelForm(JSONSchemaModelFormMixin, forms.ModelForm):
    """Convenient ModelForm base for schema-driven JSON fields."""
