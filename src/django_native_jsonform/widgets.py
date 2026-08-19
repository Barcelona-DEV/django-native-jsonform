from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from django import forms

from .binding import (
    MISSING,
    FieldResolver,
    JSONFormSubmission,
    SchemaBinding,
    resolve_schema,
)
from .registry import JSONFormRegistry, default_registry
from .renderers import JSONFormRenderer


class JSONSchemaWidget(forms.Widget):
    """Composite widget rendering a schema as native Django fields."""

    template_name = "django_native_jsonform/widget.html"

    @property
    def media(self) -> forms.Media:
        """Return core assets plus assets declared by generated child widgets."""

        media = forms.Media(
            css={"all": ("django_native_jsonform/json_forms.css",)},
            js=("django_native_jsonform/json_forms.js",),
        )
        if self.binding is not None:
            media += self.binding.form.media
        return media

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
        root_required: bool = True,
        attrs: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(attrs)
        self.schema = schema
        self.registry = (registry or default_registry).clone()
        self.overrides = overrides or {}
        self.field_resolver = field_resolver
        self.renderer = renderer or JSONFormRenderer(templates)
        self.default_policy = default_policy
        self.preserve_unknown = preserve_unknown
        self.max_array_items = max_array_items
        self.root_required = root_required
        self.context: Any = None
        # Compatibility surface for schema callables which receive an object.
        self.instance: Any = None
        self.binding: SchemaBinding | None = None

    def set_context(self, context: Any) -> None:
        self.context = context
        self.instance = context

    def value_from_datadict(self, data, files, name):
        return JSONFormSubmission(data=data, files=files, prefix=name)

    def value_omitted_from_data(self, data, files, name):
        prefix = f"{name}-"
        return not any(str(key).startswith(prefix) for key in data)

    def render(self, name, value, attrs=None, renderer=None):
        if isinstance(value, JSONFormSubmission):
            if self.binding is None or self.binding.prefix != name:
                self.binding = self.bind(value)
            binding = self.binding
        else:
            initial = MISSING if value is None else value
            binding = self.build_binding(initial=initial, prefix=name)
            self.binding = binding
        final_attrs = self.build_attrs(self.attrs, attrs)
        return self.renderer.render(binding, attrs=final_attrs)

    def bind(self, submission: JSONFormSubmission) -> SchemaBinding:
        return self.build_binding(
            initial=MISSING,
            prefix=submission.prefix,
            data=submission.data,
            files=submission.files,
        )

    def build_binding(
        self,
        *,
        initial: Any,
        prefix: str,
        data=None,
        files=None,
    ) -> SchemaBinding:
        # Bound forms still need the model's current JSON to preserve keys which
        # are hidden by permissions or absent from the active schema branch.
        if data is not None and self.binding is not None:
            current_initial = self.binding.initial
        else:
            current_initial = initial
        schema = resolve_schema(self.schema, self.context or self.instance)
        return SchemaBinding(
            schema=schema,
            initial=current_initial,
            prefix=prefix,
            registry=self.registry,
            data=data,
            files=files,
            context=self.context or self.instance,
            overrides=self.overrides,
            field_resolver=self.field_resolver,
            default_policy=self.default_policy,
            preserve_unknown=self.preserve_unknown,
            max_array_items=self.max_array_items,
            root_required=self.root_required,
        )

    def __deepcopy__(self, memo):
        obj = type(self)(
            schema=self.schema,
            registry=self.registry,
            overrides=self.overrides,
            field_resolver=self.field_resolver,
            renderer=deepcopy(self.renderer, memo),
            default_policy=self.default_policy,
            preserve_unknown=self.preserve_unknown,
            max_array_items=self.max_array_items,
            root_required=self.root_required,
            attrs=deepcopy(self.attrs, memo),
        )
        memo[id(self)] = obj
        obj.context = self.context
        obj.instance = self.instance
        return obj
