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
from .validation import JSONSchemaValidator, Schema


class JSONSchemaWidget(forms.Widget):
    """Composite widget rendering a schema as native Django fields."""

    template_name = "django_native_jsonform/widget.html"

    @property
    def media(self) -> forms.Media:
        """Return core assets plus assets declared by generated child widgets."""

        media = forms.Media(
            css={"all": ("django_native_jsonform/json_forms.0.5.1.css",)},
            js=("django_native_jsonform/json_forms.0.5.1.js",),
        )
        if self.binding is not None:
            media += self.binding.form.media
        return media

    def __init__(
        self,
        *,
        schema: Schema | Callable[..., Schema],
        registry: JSONFormRegistry | None = None,
        overrides: Mapping[str, Mapping[str, Any] | Callable] | None = None,
        field_resolver: FieldResolver | None = None,
        renderer: JSONFormRenderer | None = None,
        templates: Mapping[str, str] | None = None,
        default_policy: str = "preserve",
        presence_mode: str = "auto",
        preserve_unknown: bool = True,
        max_array_items: int = 250,
        max_depth: int = 32,
        max_nodes: int = 5000,
        schema_registry=None,
        schema_resources=None,
        validate_formats: bool = False,
        format_checker=None,
        max_errors: int = 100,
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
        self.presence_mode = presence_mode
        self.preserve_unknown = preserve_unknown
        self.max_array_items = max_array_items
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.validation_options = {
            "schema_registry": schema_registry,
            "schema_resources": deepcopy(schema_resources),
            "validate_formats": validate_formats,
            "format_checker": format_checker,
            "max_errors": max_errors,
        }
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
            initial = value
            if value is None and (
                self.binding is None or self.binding.initial is MISSING
            ):
                initial = MISSING
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

    def document_validator(self):
        return JSONSchemaValidator(
            resolve_schema(self.schema, self.context or self.instance),
            **self.validation_options,
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
            presence_mode=self.presence_mode,
            preserve_unknown=self.preserve_unknown,
            max_array_items=self.max_array_items,
            max_depth=self.max_depth,
            max_nodes=self.max_nodes,
            validation_options=self.validation_options,
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
            presence_mode=self.presence_mode,
            preserve_unknown=self.preserve_unknown,
            max_array_items=self.max_array_items,
            max_depth=self.max_depth,
            max_nodes=self.max_nodes,
            **self.validation_options,
            root_required=self.root_required,
            attrs=deepcopy(self.attrs, memo),
        )
        memo[id(self)] = obj
        obj.context = self.context
        obj.instance = self.instance
        return obj
