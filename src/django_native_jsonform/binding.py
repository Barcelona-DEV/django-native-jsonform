from __future__ import annotations

import inspect
from collections import OrderedDict
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model, QuerySet

from .registry import FieldFactoryContext, JSONFormRegistry, clone_field
from .validation import JSONSchemaValidator, Schema


class _Missing:
    def __deepcopy__(self, memo):
        return self

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()


@dataclass(frozen=True)
class JSONFormSubmission:
    data: Mapping[str, Any]
    files: Mapping[str, Any]
    prefix: str


@dataclass
class Node:
    kind: str
    path: tuple[str | int, ...]
    key_path: tuple[str | int, ...]
    schema: dict[str, Any]
    title: str = ""
    help_text: str = ""
    required: bool = False
    active: bool = True
    read_only: bool = False
    exists: bool = False
    initial: Any = MISSING
    presence_key: str | None = None
    field_key: str | None = None
    json_key: str | None = None
    children: list[Node] = field(default_factory=list)
    branches: list[Node] = field(default_factory=list)
    selected_branch: int = 0
    branch_values: list[Any] = field(default_factory=list)
    discriminator: str | None = None
    selector_key: str | None = None
    items: list[Node] = field(default_factory=list)
    prototype: Node | None = None
    count_key: str | None = None
    order_key: str | None = None
    delete_key: str | None = None
    deleted: bool = False
    serializer: Callable[[Any], Any] | None = None
    template_name: str | None = None
    override: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def path_string(self) -> str:
        return path_to_string(self.path)


@dataclass(frozen=True)
class BuildContext:
    path: tuple[str | int, ...]
    schema: dict[str, Any]
    required: bool
    disabled: bool
    form_context: Any
    initial: Any
    exists: bool
    override: Mapping[str, Any]


FieldResolver = Callable[[BuildContext], forms.Field | None]
Serializer = Callable[[Any], Any]


class SchemaBinding:
    """One bound or unbound schema tree backed by ordinary Django fields."""

    def __init__(
        self,
        *,
        schema: Schema,
        initial: Any,
        prefix: str,
        registry: JSONFormRegistry,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        context: Any = None,
        overrides: Mapping[
            str, Mapping[str, Any] | Callable[[BuildContext], Mapping[str, Any]]
        ]
        | None = None,
        field_resolver: FieldResolver | None = None,
        default_policy: str = "preserve",
        presence_mode: str = "auto",
        preserve_unknown: bool = True,
        max_array_items: int = 250,
        max_depth: int = 32,
        max_nodes: int = 5000,
        validation_options: Mapping[str, Any] | None = None,
        root_required: bool = True,
    ) -> None:
        if default_policy not in {"preserve", "materialize"}:
            raise ValueError("default_policy must be 'preserve' or 'materialize'")
        self.schema = deepcopy(schema)
        self.initial = deepcopy(initial)
        self.prefix = prefix
        self.registry = registry
        self.data = data
        self.files = files
        self.context = context
        self.overrides = overrides or {}
        self.field_resolver = field_resolver
        self.default_policy = default_policy
        if presence_mode not in {"auto", "explicit"}:
            raise ValueError("presence_mode must be 'auto' or 'explicit'")
        self.presence_mode = presence_mode
        self.preserve_unknown = preserve_unknown
        self.max_array_items = max_array_items
        if max_array_items < 1 or max_depth < 1 or max_nodes < 1:
            raise ValueError("Editor resource limits must be positive")
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self._node_count = 0
        self.document_validator = JSONSchemaValidator(
            schema, **(validation_options or {})
        )
        self._document_checked = False
        self.fields: OrderedDict[str, forms.Field] = OrderedDict()
        self.field_initial: dict[str, Any] = {}
        self.path_nodes: dict[str, list[Node]] = {}
        self._errors_applied: list[tuple[str, str]] = []

        root_exists = initial is not MISSING
        root_initial = initial if root_exists else MISSING
        self.root = self._build_node(
            self.schema,
            path=(),
            key_path=(),
            initial=root_initial,
            exists=root_exists,
            required=root_required,
            active=True,
            read_only=False,
        )
        self.form = forms.Form(data=data, files=files, prefix=prefix)
        self.form.fields = self.fields
        self.form.initial = self.field_initial

    @property
    def is_bound(self) -> bool:
        return self.data is not None

    def is_valid(self) -> bool:
        if not self.is_bound:
            return False
        valid = self.form.is_valid()
        if valid and not self._document_checked:
            self._document_checked = True
            value = self._clean_node(self.root)
            if value is not MISSING:
                self._attach_schema_issues(self.document_validator.issues(value))
            elif self.root.required:
                self.form.add_error(None, "This JSON value is required.")
            valid = not self.form.errors
        return valid

    def _serialized_targets(self):
        # Build a map in serialized coordinates: deleting array item 0 shifts
        # item 1 to JSON position 0, but not to the same HTML field name.
        targets = {}

        def visit(node, path):
            if not node.active or self._clean_node(node) is MISSING:
                return
            targets[path] = node
            if node.kind == "object":
                for child in node.children:
                    visit(child, (*path, child.json_key))
            elif node.kind == "union":
                visit(node.branches[node.selected_branch], path)
            elif node.kind == "array":
                index = 0
                for item in node.items:
                    if self._cleaned_truthy(item.delete_key):
                        continue
                    visit(item.children[0], (*path, index))
                    index += 1

        visit(self.root, ())
        return targets

    def _attach_schema_issues(self, issues) -> None:
        targets = self._serialized_targets()
        for issue in issues:
            path = issue.path
            while path and path not in targets:
                path = path[:-1]
            target = targets.get(path, self.root)
            target.errors.append(issue.message)
            key = target.field_key or target.selector_key or target.count_key
            # Store the path with a non-field error as well, so custom templates
            # and raw JSON editors never silently hide a container error.
            self.form.add_error(None, f"{issue.pointer or '/'}: {issue.message}")
            if key and key in self.form.fields:
                self.form.add_error(key, issue.message)

    def cleaned_value(self) -> Any:
        if not self.is_valid():
            raise ValueError("Cannot read cleaned_value from an invalid schema form")
        value = self._clean_node(self.root)
        if value is MISSING:
            return None
        return value

    def add_path_errors(self, errors: Mapping[str, list[str]]) -> None:
        # Ensure the flat form has completed its own validation before adding
        # application-level errors.
        self.form.is_valid()
        targets = self._serialized_targets()
        pointer_targets = {
            "".join(
                "/" + str(part).replace("~", "~0").replace("/", "~1") for part in path
            ): node
            for path, node in targets.items()
        }
        dot_targets = {path_to_string(path): node for path, node in targets.items()}
        for path, messages in errors.items():
            locations = pointer_targets if path.startswith("/") else dot_targets
            separator = "/" if path.startswith("/") else "."
            nearest = path
            while nearest and nearest not in locations:
                nearest = (
                    nearest.rsplit(separator, 1)[0] if separator in nearest else ""
                )
            target = locations.get(nearest, self.root)
            field_key = target.field_key or target.selector_key or target.count_key
            for message in messages:
                target.errors.append(message)
                self.form.add_error(None, f"{path or '/'}: {message}")
                if field_key:
                    self.form.add_error(field_key, message)
                self._errors_applied.append((path, message))

    def bound_field(self, key: str | None):
        if not key:
            return None
        return self.form[key]

    def _build_node(
        self,
        schema: dict[str, Any],
        *,
        path: tuple[str | int, ...],
        key_path: tuple[str | int, ...],
        initial: Any,
        exists: bool,
        required: bool,
        active: bool,
        read_only: bool,
        prototype: bool = False,
    ) -> Node:
        self._node_count += 1
        if self._node_count > self.max_nodes:
            raise ImproperlyConfigured(
                "JSON form exceeds max_nodes. "
                "Use a JSON editor override on a large subtree."
            )
        schema = self._resolve_schema(schema)
        override = self._override_for(
            path, schema, required, not active or read_only, initial, exists
        )
        override.setdefault("presence_mode", self.presence_mode)
        if override["presence_mode"] not in {"auto", "explicit"}:
            raise ValueError("presence_mode must be 'auto' or 'explicit'")
        required = bool(
            override.get("required", required or schema.get("required") is True)
        )
        read_only = bool(
            override.get(
                "readonly",
                read_only or schema.get("readonly", schema.get("readOnly", False)),
            )
        )
        default_policy = override.get("default_policy", self.default_policy)
        display_initial = initial
        if not exists and "default" in schema:
            display_initial = deepcopy(schema["default"])
        materialize = (
            not exists
            and "default" in schema
            and default_policy == "materialize"
            and not read_only
        )

        raw_reason = self._raw_editor_reason(schema, display_initial, key_path)
        if (
            override.get("editor") == "json"
            or override.get("field") is not None
            or raw_reason
        ):
            if raw_reason:
                override = {**override, "editor": "json", "editor_reason": raw_reason}
            return self._build_leaf(
                schema,
                path=path,
                key_path=key_path,
                initial=display_initial,
                exists=exists,
                required=required,
                active=active,
                read_only=read_only,
                materialize=materialize,
                override=override,
                prototype=prototype,
            )

        nullable_types = schema.get("type")
        if (
            isinstance(nullable_types, list)
            and "null" in nullable_types
            and len(nullable_types) == 2
            and not any(key in schema for key in ("oneOf", "enum", "choices", "const"))
            and next(kind for kind in nullable_types if kind != "null")
            in {"number", "integer"}
        ):
            # Use a native scalar control; document validation still uses the
            # original nullable schema. Optional blank controls stay unset.
            scalar_schema = {
                **schema,
                "type": next(kind for kind in nullable_types if kind != "null"),
            }
            return self._build_leaf(
                scalar_schema,
                path=path,
                key_path=key_path,
                initial=display_initial,
                exists=exists,
                required=required,
                active=active,
                read_only=read_only,
                materialize=materialize,
                override=override,
                prototype=prototype,
            )

        if isinstance(schema.get("type"), list):
            schema = {
                **schema,
                "oneOf": [
                    {"type": json_type, "title": json_type.capitalize()}
                    for json_type in schema["type"]
                ],
            }
            schema.pop("type")

        if "oneOf" in schema:
            return self._build_union(
                schema,
                path=path,
                key_path=key_path,
                initial=display_initial,
                exists=exists,
                required=required,
                active=active,
                read_only=read_only,
                materialize=materialize,
                override=override,
                prototype=prototype,
            )

        json_type = schema.get("type")
        if json_type is None and "properties" in schema:
            json_type = "object"
        if json_type == "object":
            return self._build_object(
                schema,
                path=path,
                key_path=key_path,
                initial=display_initial,
                exists=exists,
                required=required,
                active=active,
                read_only=read_only,
                materialize=materialize,
                override=override,
                prototype=prototype,
            )
        if json_type == "array":
            return self._build_array(
                schema,
                path=path,
                key_path=key_path,
                initial=display_initial,
                exists=exists,
                required=required,
                active=active,
                read_only=read_only,
                materialize=materialize,
                override=override,
                prototype=prototype,
            )
        return self._build_leaf(
            schema,
            path=path,
            key_path=key_path,
            initial=display_initial,
            exists=exists,
            required=required,
            active=active,
            read_only=read_only,
            materialize=materialize,
            override=override,
            prototype=prototype,
        )

    def _raw_editor_reason(self, schema, initial, key_path):
        if schema.get("x-jsonform-raw"):
            return "schema"
        if len(key_path) >= self.max_depth:
            return "depth"
        if any(
            key in schema
            for key in (
                "allOf",
                "anyOf",
                "if",
                "then",
                "else",
                "dependentSchemas",
                "patternProperties",
                "propertyNames",
                "prefixItems",
                "$dynamicRef",
            )
        ):
            return "composition"
        if "$id" in schema and key_path:
            return "resource"
        if isinstance(schema.get("additionalProperties"), dict):
            return "dynamic-properties"
        if schema.get("additionalProperties") is True:
            return "dynamic-properties"
        if "oneOf" not in schema and (
            schema.get("type") == "object" or "properties" in schema
        ):
            properties = schema.get("properties", {})
            if any("__" in name for name in properties):
                return "reserved-property-names"
            required = schema.get("required", [])
            if not properties or (
                isinstance(required, list) and set(required) - properties.keys()
            ):
                return "dynamic-properties"
            if (
                isinstance(initial, dict)
                and initial.keys() - properties.keys()
                and (
                    schema.get("additionalProperties") is False
                    or schema.get("unevaluatedProperties") is False
                )
            ):
                return "extra-properties"
        if isinstance(initial, list) and len(initial) > self.max_array_items:
            return "large-array"
        if schema.get("minItems", 0) > self.max_array_items:
            return "large-array"
        if isinstance(schema.get("items"), bool):
            return "boolean-items"
        if "oneOf" in schema and any(
            not isinstance(branch, dict) for branch in schema["oneOf"]
        ):
            return "boolean-branches"
        if isinstance(schema.get("type"), list) and {"number", "integer"}.issubset(
            schema["type"]
        ):
            # A type union is inclusive, unlike oneOf's exact-one semantics.
            return "overlapping-types"
        if any(isinstance(choice, (dict, list)) for choice in schema.get("enum", [])):
            return "structured-enum"
        choices = schema.get("enum", [])
        if None in choices or len({str(value) for value in choices}) != len(choices):
            return "ambiguous-enum"
        if (
            "type" not in schema
            and "oneOf" not in schema
            and "properties" not in schema
            and isinstance(schema.get("default"), (dict, list))
        ):
            return "structured-default"
        if "type" not in schema and not any(
            key in schema
            for key in ("properties", "oneOf", "const", "enum", "choices", "default")
        ):
            return "unconstrained"
        return None

    def _build_object(
        self,
        schema: dict[str, Any],
        *,
        path: tuple[str | int, ...],
        key_path: tuple[str | int, ...],
        initial: Any,
        exists: bool,
        required: bool,
        active: bool,
        read_only: bool,
        materialize: bool,
        override: dict[str, Any],
        prototype: bool,
    ) -> Node:
        actual = initial if exists and isinstance(initial, dict) else {}
        displayed_defaults = initial if not exists and isinstance(initial, dict) else {}
        presence_key = self._internal_key("present", key_path)
        present = self._add_presence_field(
            presence_key,
            initial=required or exists or materialize,
            mode=override["presence_mode"],
            active=active,
            prototype=prototype,
        )
        child_active = active and (required or present or not self.is_bound)
        node = self._base_node(
            "object",
            schema,
            path,
            key_path,
            initial,
            exists,
            required,
            active,
            read_only,
            override,
        )
        node.presence_key = presence_key
        required_names = schema.get("required", [])
        if not isinstance(required_names, (list, tuple, set)):
            required_names = []
        for name, child_schema in schema.get("properties", {}).items():
            child_exists = name in actual
            child_initial = actual[name] if child_exists else MISSING
            if (
                not child_exists
                and name in displayed_defaults
                and isinstance(child_schema, dict)
            ):
                child_schema = {
                    **child_schema,
                    "default": deepcopy(displayed_defaults[name]),
                }
            child = self._build_node(
                child_schema,
                path=(*path, name),
                key_path=(*key_path, name),
                initial=child_initial,
                exists=child_exists,
                required=name in required_names
                or (
                    isinstance(child_schema, dict)
                    and child_schema.get("required") is True
                ),
                active=child_active,
                read_only=read_only,
                prototype=prototype,
            )
            child.json_key = name
            node.children.append(child)
        return node

    def _build_array(
        self,
        schema: dict[str, Any],
        *,
        path: tuple[str | int, ...],
        key_path: tuple[str | int, ...],
        initial: Any,
        exists: bool,
        required: bool,
        active: bool,
        read_only: bool,
        materialize: bool,
        override: dict[str, Any],
        prototype: bool,
    ) -> Node:
        values = initial if isinstance(initial, list) else []
        presence_key = self._internal_key("present", key_path)
        present = self._add_presence_field(
            presence_key,
            initial=required or exists or materialize,
            active=active,
            prototype=prototype,
            mode=override["presence_mode"],
        )
        count_key = self._internal_key("count", key_path)
        raw_count = self._raw_value(count_key)
        try:
            count = int(raw_count) if raw_count not in (None, "") else len(values)
        except (TypeError, ValueError):
            count = len(values)
        # Keep a bounded number of generated controls. A submitted count beyond
        # this budget fails its IntegerField; existing large lists use the raw
        # editor before reaching this method and are never truncated.
        count = min(max(count, 0), self.max_array_items)
        self._add_field(
            count_key,
            forms.IntegerField(
                required=False,
                min_value=0,
                max_value=self.max_array_items,
                widget=forms.HiddenInput(attrs={"data-jsonform-count": ""}),
                disabled=prototype
                or not active
                or (self.is_bound and not (required or present)),
            ),
            count,
        )
        node = self._base_node(
            "array",
            schema,
            path,
            key_path,
            initial,
            exists,
            required,
            active,
            read_only,
            override,
        )
        node.presence_key = presence_key
        node.count_key = count_key
        node.override["max_render_items"] = self.max_array_items
        items_schema = schema.get("items", {})
        array_active = active and (required or present or not self.is_bound)
        for index in range(count):
            item_has_display_value = index < len(values)
            item_exists = exists and item_has_display_value
            item_initial = values[index] if item_has_display_value else MISSING
            item_key_path = (*key_path, index)
            order_key = self._internal_key("order", item_key_path)
            self._add_field(
                order_key,
                forms.IntegerField(
                    required=False,
                    min_value=0,
                    widget=forms.HiddenInput(attrs={"data-jsonform-order": ""}),
                    disabled=prototype or not active or read_only,
                ),
                index,
            )
            delete_key = self._internal_key("delete", item_key_path)
            deleted = self._raw_truthy(delete_key)
            self._add_field(
                delete_key,
                forms.BooleanField(
                    required=False,
                    widget=forms.HiddenInput(attrs={"data-jsonform-delete": ""}),
                    disabled=prototype or not active,
                ),
                False,
            )
            child = self._build_node(
                items_schema,
                path=(*path, index),
                key_path=item_key_path,
                initial=item_initial,
                exists=item_exists,
                required=True,
                active=array_active and not deleted,
                read_only=read_only,
                prototype=prototype,
            )
            item_node = Node(
                kind="array_item",
                path=(*path, index),
                key_path=item_key_path,
                schema=items_schema,
                active=array_active,
                read_only=read_only,
                exists=item_exists,
                initial=item_initial,
                children=[child],
                order_key=order_key,
                delete_key=delete_key,
                deleted=deleted,
            )
            node.items.append(item_node)

        def submitted_order(item):
            try:
                return int(self._raw_value(item.order_key))
            except (TypeError, ValueError):
                return item.path[-1]

        if not read_only:
            node.items.sort(key=submitted_order)

        prototype_depth = sum(str(part).startswith("__index_") for part in key_path)
        token = f"__index_{prototype_depth}__"
        prototype_key_path = (*key_path, token)
        prototype_child = self._build_node(
            items_schema,
            path=(*path, "*"),
            key_path=prototype_key_path,
            initial=MISSING,
            exists=False,
            required=True,
            active=False,
            read_only=read_only,
            prototype=True,
        )
        prototype_delete_key = self._internal_key("delete", prototype_key_path)
        self._add_field(
            prototype_delete_key,
            forms.BooleanField(
                required=False,
                widget=forms.HiddenInput(
                    attrs={
                        "data-jsonform-delete": "",
                    }
                ),
                disabled=True,
            ),
            False,
        )
        prototype_order_key = self._internal_key("order", prototype_key_path)
        self._add_field(
            prototype_order_key,
            forms.IntegerField(
                required=False,
                min_value=0,
                widget=forms.HiddenInput(attrs={"data-jsonform-order": ""}),
                disabled=True,
            ),
            0,
        )
        node.prototype = Node(
            kind="array_item",
            path=(*path, "*"),
            key_path=prototype_key_path,
            schema=items_schema,
            active=False,
            read_only=read_only,
            children=[prototype_child],
            order_key=prototype_order_key,
            delete_key=prototype_delete_key,
            override={"index_token": token},
        )
        return node

    def _build_union(
        self,
        schema: dict[str, Any],
        *,
        path: tuple[str | int, ...],
        key_path: tuple[str | int, ...],
        initial: Any,
        exists: bool,
        required: bool,
        active: bool,
        read_only: bool,
        materialize: bool,
        override: dict[str, Any],
        prototype: bool,
    ) -> Node:
        branches = [self._resolve_schema(branch) for branch in schema.get("oneOf", [])]
        discriminator, discriminator_values = self._union_discriminator(
            schema, branches
        )
        branch_values = discriminator_values or list(range(len(branches)))
        selected = self._select_branch(
            schema,
            branches,
            initial,
            key_path,
            branch_values,
            discriminator,
        )
        selector_key = self._internal_key("variant", key_path)
        selector_context = BuildContext(
            path=(*path, discriminator) if discriminator else path,
            schema=schema,
            required=True,
            disabled=read_only or prototype or not active,
            form_context=self.context,
            initial=branch_values[selected] if branch_values else None,
            exists=exists,
            override=override,
        )
        discriminator_schema = self._discriminator_schema(
            schema, branches, discriminator
        )
        inferred_selector_label = (
            str(discriminator).replace("_", " ").capitalize() if discriminator else None
        )
        selector_label = (
            override.get("selector_label")
            or discriminator_schema.get("title")
            or inferred_selector_label
            or schema.get("title")
            or "Type"
        )
        selector_help_text = (
            override.get("selector_help_text")
            or discriminator_schema.get("help_text")
            or discriminator_schema.get("description")
            or ""
        )
        selector_attrs = {
            "data-jsonform-selector": "",
            **override.get("selector_attrs", {}),
        }
        if discriminator:
            selector_attrs["data-jsonform-discriminator"] = discriminator
        selector = forms.TypedChoiceField(
            choices=[
                (
                    branch_values[index],
                    branch.get("title")
                    or self._branch_discriminator_title(branch, discriminator)
                    or str(branch_values[index]),
                )
                for index, branch in enumerate(branches)
            ],
            coerce=self._choice_coercer(branch_values),
            required=True,
            disabled=read_only or prototype or not active,
            label=selector_label,
            help_text=selector_help_text,
            widget=forms.Select(attrs=selector_attrs),
        )
        configured_selector = override.get("selector_field")
        if configured_selector is not None:
            selector = self._configured_selector_field(
                configured_selector,
                selector_context,
                choices=selector.choices,
                attrs=selector_attrs,
            )
            if not selector.label:
                selector.label = selector_label
            if not selector.help_text:
                selector.help_text = selector_help_text
        if read_only:
            selector.widget.attrs["data-jsonform-permanent-disabled"] = ""
        self._add_field(
            selector_key,
            selector,
            branch_values[selected] if branch_values else None,
        )
        presence_key = self._internal_key("present", key_path)
        present = self._add_presence_field(
            presence_key,
            initial=required or exists or materialize,
            active=active,
            prototype=prototype,
            mode=override["presence_mode"],
        )
        node = self._base_node(
            "union",
            schema,
            path,
            key_path,
            initial,
            exists,
            required,
            active,
            read_only,
            override,
        )
        node.selector_key = selector_key
        selector.disabled = selector.disabled or (
            self.is_bound and not (required or present)
        )
        node.presence_key = presence_key
        node.selected_branch = selected
        node.branch_values = branch_values
        node.discriminator = discriminator

        initial_dict = initial if isinstance(initial, dict) else {}
        all_known = set()
        for branch in branches:
            all_known.update(branch.get("properties", {}).keys())
        for index, branch in enumerate(branches):
            merged = self._merge_union_branch(schema, branch)
            if initial_dict:
                selected_known = set(merged.get("properties", {}).keys())
                branch_initial = {
                    key: value
                    for key, value in initial_dict.items()
                    if key not in all_known or key in selected_known
                }
            elif index == selected:
                # Scalar and array unions have no properties to filter. Pass
                # their persisted value to the selected branch so its native
                # Django field can hydrate it instead of rendering empty.
                branch_initial = initial
            else:
                branch_initial = MISSING
            branch_exists = exists and index == selected
            branch_node = self._build_node(
                merged,
                path=path,
                key_path=(*key_path, f"__branch_{index}__"),
                initial=branch_initial,
                exists=branch_exists,
                required=True,
                active=active
                and (required or present or not self.is_bound)
                and index == selected,
                read_only=read_only,
                prototype=prototype,
            )
            branch_node.override["branch_index"] = index
            node.branches.append(branch_node)
        return node

    def _build_leaf(
        self,
        schema: dict[str, Any],
        *,
        path: tuple[str | int, ...],
        key_path: tuple[str | int, ...],
        initial: Any,
        exists: bool,
        required: bool,
        active: bool,
        read_only: bool,
        materialize: bool,
        override: dict[str, Any],
        prototype: bool,
    ) -> Node:
        is_const = "const" in schema
        required = required or is_const
        presence_key = self._internal_key("present", key_path)
        present = self._add_presence_field(
            presence_key,
            initial=required or exists or materialize,
            active=active,
            prototype=prototype,
            mode=override["presence_mode"],
        )
        disabled = (
            read_only or not active or prototype or (self.is_bound and not present)
        )
        build_context = BuildContext(
            path=path,
            schema=schema,
            required=required and active,
            disabled=disabled,
            form_context=self.context,
            initial=initial,
            exists=exists,
            override=override,
        )
        field = self._create_leaf_field(build_context)
        field.disabled = disabled or bool(override.get("disabled", False))
        # Presence belongs to JSON Schema. Empty strings, false, [], {}, and
        # null are values, not missing Django form fields.
        field.required = False
        if is_const:
            field.required = False
            field.disabled = True
            field.widget = forms.HiddenInput()
        if is_const or read_only or override.get("disabled", False):
            field.widget.attrs["data-jsonform-permanent-disabled"] = ""

        field_key = self._field_key(key_path)
        value = (
            schema["const"] if is_const else (None if initial is MISSING else initial)
        )
        deserializer = override.get("deserialize")
        if deserializer and value is not None:
            value = deserializer(value)
        self._add_field(field_key, field, value)
        node = self._base_node(
            "leaf",
            schema,
            path,
            key_path,
            initial,
            exists,
            required,
            active,
            read_only,
            override,
        )
        node.field_key = field_key
        node.presence_key = presence_key
        node.serializer = override.get("serialize") or serialize_json_value
        self.path_nodes.setdefault(path_to_string(path), []).append(node)
        return node

    def _create_leaf_field(self, context: BuildContext) -> forms.Field:
        override = context.override
        configured = override.get("field")
        field: forms.Field | None = None
        if isinstance(configured, forms.Field):
            field = clone_field(configured)
        elif inspect.isclass(configured) and issubclass(configured, forms.Field):
            field = configured()
        elif callable(configured):
            field = configured(context)
        elif self.field_resolver:
            field = self.field_resolver(context)

        factory_context = FieldFactoryContext(
            path=context.path,
            schema=context.schema,
            required=context.required,
            disabled=context.disabled,
            form_context=context.form_context,
        )
        if field is None:
            if override.get("editor") == "json" or context.schema.get("type") == "null":
                field = forms.JSONField(
                    required=False,
                    label=context.schema.get("title")
                    or (str(context.path[-1]) if context.path else "Value"),
                    help_text=context.schema.get(
                        "description", context.schema.get("help_text", "")
                    ),
                    widget=forms.Textarea(
                        attrs={"rows": 8, "data-jsonform-json-editor": ""}
                    ),
                )
            else:
                field = self._choice_field(
                    factory_context
                ) or self.registry.create_field(factory_context)

        widget = override.get("widget", context.schema.get("widget"))
        if isinstance(widget, str):
            field.widget = self.registry.create_widget(
                widget,
                path=context.path,
                schema=context.schema,
                form_context=context.form_context,
            )
        elif isinstance(widget, forms.Widget):
            field.widget = deepcopy(widget)
        elif inspect.isclass(widget) and issubclass(widget, forms.Widget):
            field.widget = widget()
        elif callable(widget):
            field.widget = widget(context)
        elif context.schema.get("format") == "color" and not context.schema.get(
            "widget"
        ):
            field.widget = self.registry.create_widget(
                "color",
                path=context.path,
                schema=context.schema,
                form_context=context.form_context,
            )

        if "label" in override:
            field.label = override["label"]
        if "help_text" in override:
            field.help_text = override["help_text"]
        attrs = {**context.schema.get("attrs", {}), **override.get("attrs", {})}
        field.widget.attrs.update(attrs)
        return field

    def _choice_field(self, context: FieldFactoryContext) -> forms.Field | None:
        schema = context.schema
        raw_choices = schema.get("choices")
        if raw_choices is None and "enum" in schema:
            raw_choices = schema["enum"]
        if raw_choices is None:
            return None
        choices: list[tuple[Any, str]] = []
        for choice in raw_choices:
            if isinstance(choice, dict):
                value = choice.get("value")
                label = choice.get("title", choice.get("label", value))
            else:
                value = choice
                label = choice
            choices.append((value, str(label)))
        value_map = {str(value): value for value, _ in choices}
        json_type = schema.get("type", "string")
        empty_value: Any = "" if json_type == "string" else None
        return forms.TypedChoiceField(
            choices=choices,
            coerce=lambda value: value_map.get(str(value), value),
            empty_value=empty_value,
            required=context.required,
            disabled=context.disabled,
            label=schema.get("title")
            or (str(context.path[-1]) if context.path else "Value"),
            help_text=schema.get("help_text")
            or schema.get("helpText")
            or schema.get("description", ""),
        )

    def _base_node(
        self,
        kind: str,
        schema: dict[str, Any],
        path: tuple[str | int, ...],
        key_path: tuple[str | int, ...],
        initial: Any,
        exists: bool,
        required: bool,
        active: bool,
        read_only: bool,
        override: dict[str, Any],
    ) -> Node:
        return Node(
            kind=kind,
            path=path,
            key_path=key_path,
            schema=schema,
            title=str(schema.get("title") or (path[-1] if path else "")),
            help_text=str(
                schema.get("help_text")
                or schema.get("helpText")
                or schema.get("description", "")
            ),
            required=required,
            active=active,
            read_only=read_only,
            exists=exists,
            initial=initial,
            override=override,
            template_name=override.get("template"),
        )

    def _add_presence_field(
        self,
        key: str,
        *,
        initial: bool,
        active: bool,
        prototype: bool,
        mode: str = "explicit",
    ) -> bool:
        raw = self._raw_value(key)
        if raw is None:
            present = initial
        else:
            present = str(raw).lower() not in {"", "0", "false", "none"}
        self._add_field(
            key,
            forms.BooleanField(
                required=False,
                widget=forms.HiddenInput(attrs={"data-jsonform-presence": ""}),
                disabled=prototype or not active,
            ),
            initial,
        )
        return present or mode == "auto"

    def _add_field(self, key: str, field: forms.Field, initial: Any) -> None:
        if key in self.fields:
            raise ValueError(f"Generated duplicate Django form field {key!r}")
        self.fields[key] = field
        self.field_initial[key] = initial

    def _raw_value(self, key: str) -> Any:
        if self.data is None:
            return None
        return self.data.get(self._html_name(key))

    def _raw_truthy(self, key: str) -> bool:
        value = self._raw_value(key)
        return str(value).lower() not in {"", "0", "false", "none"}

    def _html_name(self, key: str) -> str:
        return f"{self.prefix}-{key}" if self.prefix else key

    def _field_key(self, key_path: tuple[str | int, ...]) -> str:
        return "__".join(map(str, key_path)) or "__root_value__"

    def _internal_key(self, kind: str, key_path: tuple[str | int, ...]) -> str:
        suffix = self._field_key(key_path)
        return f"__jsonform_{kind}__{suffix}"

    def _resolve_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        if isinstance(schema, bool):
            return {"x-jsonform-raw": True}
        result = deepcopy(schema)
        seen = set()
        while "$ref" in result:
            ref = result["$ref"]
            if not ref.startswith("#/") or ref in seen:
                return {**result, "x-jsonform-raw": True}
            seen.add(ref)
            resolved: Any = self.schema
            try:
                for part in ref[2:].split("/"):
                    resolved = resolved[part.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError):
                return {**result, "x-jsonform-raw": True}
            if not isinstance(resolved, dict):
                return {**result, "x-jsonform-raw": True}
            siblings = {key: value for key, value in result.items() if key != "$ref"}
            # Overlapping constraints must intersect, not overwrite. Let the
            # JSON editor represent the complete value in that case.
            overlapping = (resolved.keys() & siblings.keys()) - {
                "title",
                "description",
                "default",
                "help_text",
                "widget",
                "attrs",
            }
            if overlapping:
                return {**result, "x-jsonform-raw": True}
            result = {**deepcopy(resolved), **siblings}
        return result

    def _override_for(
        self,
        path: tuple[str | int, ...],
        schema: dict[str, Any],
        required: bool,
        disabled: bool,
        initial: Any,
        exists: bool,
    ) -> dict[str, Any]:
        matches = []
        for pattern, configured in self.overrides.items():
            if path_matches(pattern, path):
                specificity = sum(
                    part not in {"*", "**"} for part in pattern.split(".")
                )
                matches.append((specificity, configured))
        result: dict[str, Any] = {}
        base_context = BuildContext(
            path=path,
            schema=schema,
            required=required,
            disabled=disabled,
            form_context=self.context,
            initial=initial,
            exists=exists,
            override=result,
        )
        for _, configured in sorted(matches, key=lambda item: item[0]):
            value = configured(base_context) if callable(configured) else configured
            result.update(value)
        return result

    def _select_branch(
        self,
        schema: dict[str, Any],
        branches: list[dict[str, Any]],
        initial: Any,
        key_path: tuple[str | int, ...],
        branch_values: list[Any],
        discriminator: str | None,
    ) -> int:
        raw = self._raw_value(self._internal_key("variant", key_path))
        if raw is not None:
            for index, value in enumerate(branch_values):
                if str(raw) == str(value):
                    return index
            # Keep the expected branch visible if an old, already-open form
            # posts the numeric selector used by the first implementation.
            try:
                selected = int(raw)
                if 0 <= selected < len(branches):
                    return selected
            except (TypeError, ValueError):
                pass
        candidates = [initial, schema.get("default")]
        for candidate in candidates:
            if candidate is MISSING:
                continue
            if (
                isinstance(candidate, dict)
                and discriminator
                and discriminator in candidate
            ):
                for index, value in enumerate(branch_values):
                    if candidate[discriminator] == value:
                        return index
            if isinstance(candidate, dict):
                for index, branch in enumerate(branches):
                    consts = {}
                    for name, child in branch.get("properties", {}).items():
                        value = self._single_schema_value(child)
                        if value is not MISSING:
                            consts[name] = value
                    matches = all(
                        candidate.get(name) == value for name, value in consts.items()
                    )
                    if consts and matches:
                        return index
            for index, branch in enumerate(branches):
                if self._schema_matches_value(branch, candidate):
                    return index
        return 0

    def _schema_matches_value(self, schema: dict[str, Any], value: Any) -> bool:
        """Return whether a persisted JSON value belongs to a union branch.

        This is deliberately a small structural matcher, not a second JSON
        Schema validator. Its purpose is to select the native Django widget
        which can faithfully hydrate the existing value before validation.
        """
        schema = self._resolve_schema(schema)

        if "const" in schema and not self._json_values_equal(value, schema["const"]):
            return False
        enum = schema.get("enum")
        if isinstance(enum, list) and not any(
            self._json_values_equal(value, choice) for choice in enum
        ):
            return False

        nested_branches = schema.get("oneOf")
        if isinstance(nested_branches, list):
            return any(
                self._schema_matches_value(branch, value)
                for branch in nested_branches
                if isinstance(branch, dict)
            )

        json_types = schema.get("type")
        if json_types is None:
            if "properties" in schema:
                json_types = "object"
            elif "items" in schema:
                json_types = "array"
            elif "const" not in schema and enum is None:
                return True
        if isinstance(json_types, str):
            json_types = [json_types]
        if isinstance(json_types, list) and not any(
            self._value_matches_type(value, json_type) for json_type in json_types
        ):
            return False

        if isinstance(value, dict):
            required_names = schema.get("required", [])
            if isinstance(required_names, list) and any(
                name not in value for name in required_names
            ):
                return False
            properties = schema.get("properties", {})
            if isinstance(properties, dict):
                for name, child_schema in properties.items():
                    if (
                        name in value
                        and isinstance(child_schema, dict)
                        and not self._schema_matches_value(child_schema, value[name])
                    ):
                        return False

        if isinstance(value, list) and isinstance(schema.get("items"), dict):
            return all(
                self._schema_matches_value(schema["items"], item) for item in value
            )
        return True

    def _value_matches_type(self, value: Any, json_type: Any) -> bool:
        if json_type == "null":
            return value is None
        if json_type == "boolean":
            return isinstance(value, bool)
        if json_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if json_type == "number":
            return isinstance(value, (int, float, Decimal)) and not isinstance(
                value, bool
            )
        if json_type == "string":
            return isinstance(value, str)
        if json_type == "object":
            return isinstance(value, dict)
        if json_type == "array":
            return isinstance(value, list)
        return False

    def _json_values_equal(self, left: Any, right: Any) -> bool:
        # Python considers True == 1, but JSON Schema treats booleans and
        # numbers as different instance types.
        if isinstance(left, bool) != isinstance(right, bool):
            return False
        if isinstance(left, dict) and isinstance(right, dict):
            return left.keys() == right.keys() and all(
                self._json_values_equal(value, right[key])
                for key, value in left.items()
            )
        if isinstance(left, list) and isinstance(right, list):
            return len(left) == len(right) and all(
                self._json_values_equal(a, b) for a, b in zip(left, right, strict=True)
            )
        return left == right

    def _union_discriminator(
        self,
        schema: dict[str, Any],
        branches: list[dict[str, Any]],
    ) -> tuple[str | None, list[Any]]:
        """Return the property which identifies each branch and its values.

        OpenAPI's explicit ``discriminator.propertyName`` is supported, but
        most schemas in this project use plain JSON Schema and put a distinct
        ``const`` in the same property of every branch. In that case the
        discriminator is inferred.
        """
        configured = schema.get("discriminator")
        if isinstance(configured, str):
            property_name = configured
        elif isinstance(configured, Mapping):
            property_name = configured.get("propertyName")
        else:
            property_name = None

        candidates: list[str] = []
        if property_name:
            candidates.append(str(property_name))
        elif branches:
            first_properties = branches[0].get("properties", {})
            candidates.extend(first_properties)

        for candidate in candidates:
            values = []
            for branch in branches:
                child_schema = branch.get("properties", {}).get(candidate)
                value = self._single_schema_value(child_schema)
                if value is MISSING:
                    values = []
                    break
                values.append(value)
            unique_values = {(type(value).__name__, repr(value)) for value in values}
            if values and len(unique_values) == len(values):
                return candidate, values

        # OpenAPI mappings may discriminate $ref branches without repeating a
        # const inside the referenced object.
        if property_name and isinstance(configured, Mapping):
            mapping = configured.get("mapping", {})
            if isinstance(mapping, Mapping):
                values_by_ref = {str(ref): value for value, ref in mapping.items()}
                original_branches = schema.get("oneOf", [])
                values = [
                    values_by_ref.get(str(branch.get("$ref")), MISSING)
                    for branch in original_branches
                ]
                if values and all(value is not MISSING for value in values):
                    return str(property_name), values

        return None, []

    def _single_schema_value(self, schema: Any) -> Any:
        if not isinstance(schema, dict):
            return MISSING
        schema = self._resolve_schema(schema)
        if "const" in schema:
            return schema["const"]
        enum = schema.get("enum")
        if isinstance(enum, list) and len(enum) == 1:
            return enum[0]
        return MISSING

    def _discriminator_schema(
        self,
        schema: dict[str, Any],
        branches: list[dict[str, Any]],
        discriminator: str | None,
    ) -> dict[str, Any]:
        if not discriminator:
            return {}
        configured = schema.get("properties", {}).get(discriminator)
        if isinstance(configured, dict):
            return self._resolve_schema(configured)
        for branch in branches:
            configured = branch.get("properties", {}).get(discriminator)
            if isinstance(configured, dict):
                return self._resolve_schema(configured)
        return {}

    def _branch_discriminator_title(
        self,
        branch: dict[str, Any],
        discriminator: str | None,
    ) -> str | None:
        if not discriminator:
            return None
        configured = branch.get("properties", {}).get(discriminator)
        if not isinstance(configured, dict):
            return None
        configured = self._resolve_schema(configured)
        title = configured.get("title")
        return str(title) if title else None

    def _choice_coercer(self, values: list[Any]) -> Callable[[Any], Any]:
        values_by_string = {str(value): value for value in values}
        return lambda value: values_by_string.get(str(value), value)

    def _configured_selector_field(
        self,
        configured: Any,
        context: BuildContext,
        *,
        choices: Any,
        attrs: dict[str, Any],
    ) -> forms.Field:
        if isinstance(configured, forms.Field):
            selector = clone_field(configured)
        elif inspect.isclass(configured) and issubclass(configured, forms.Field):
            selector = configured()
        elif callable(configured):
            selector = configured(context)
        else:
            raise TypeError("selector_field must be a Django Field or field factory")
        if not hasattr(selector, "choices"):
            raise TypeError("selector_field must support choices")
        selector.choices = choices
        selector.required = True
        selector.disabled = context.disabled
        selector.widget.attrs.update(attrs)
        return selector

    def _merge_union_branch(
        self, schema: dict[str, Any], branch: dict[str, Any]
    ) -> dict[str, Any]:
        merged = {
            key: deepcopy(value)
            for key, value in schema.items()
            if key not in {"oneOf", "default", "title", "help_text", "description"}
        }
        merged.update(
            {
                key: deepcopy(value)
                for key, value in branch.items()
                if key not in {"properties", "required"}
            }
        )
        if "properties" in schema or "properties" in branch:
            merged["properties"] = {
                **deepcopy(schema.get("properties", {})),
                **deepcopy(branch.get("properties", {})),
            }
            merged.setdefault("type", "object")
        required_names = list(
            dict.fromkeys(
                [
                    *(
                        schema.get("required", [])
                        if isinstance(schema.get("required"), list)
                        else []
                    ),
                    *(
                        branch.get("required", [])
                        if isinstance(branch.get("required"), list)
                        else []
                    ),
                ]
            )
        )
        if required_names:
            merged["required"] = required_names
        return merged

    def _clean_node(self, node: Node) -> Any:
        if (
            node.kind == "leaf"
            and node.active
            and not node.required
            and not node.read_only
            and node.override.get("presence_mode") == "auto"
        ):
            field = self.fields[node.field_key]
            name = self._html_name(node.field_key)
            raw = field.widget.value_from_datadict(self.data, self.files or {}, name)
            if field.widget.value_omitted_from_data(self.data, self.files or {}, name):
                return deepcopy(node.initial) if node.exists else MISSING
            if (
                not node.exists
                and not self._cleaned_truthy(node.presence_key)
                and node.override.get("default_policy", self.default_policy)
                == "preserve"
                and not field.has_changed(self.field_initial[node.field_key], raw)
            ):
                return MISSING
        value = self._clean_node_value(node)
        if (
            node.required
            or node.read_only
            or not node.active
            or node.override.get("presence_mode") != "auto"
        ):
            return value
        # Preserve already stored empty values. Clearing a populated optional
        # value omits it; explicit mode exposes absence as a separate control.
        if node.exists and self._json_values_equal(value, node.initial):
            return value
        if not self._has_content(value, node):
            return MISSING
        return value

    def _has_content(self, value, node):
        if value is MISSING or value is None or value == "":
            return False
        if node.kind == "union":
            return self._has_content(value, node.branches[node.selected_branch])
        if isinstance(value, dict) and node.kind == "object":
            children = {child.json_key: child for child in node.children}
            return any(
                key not in children
                or (
                    "const" not in children[key].schema
                    and self._has_content(item, children[key])
                )
                for key, item in value.items()
            )
        if isinstance(value, (dict, list)):
            return bool(value)
        # Zero and false are real JSON values, never generic "empty" values.
        return True

    def _clean_node_value(self, node: Node) -> Any:
        if not node.active:
            return MISSING
        if node.read_only:
            return (
                deepcopy(node.initial)
                if node.exists or (node.required and node.initial is not MISSING)
                else MISSING
            )
        present = (
            node.required
            or node.override.get("presence_mode") == "auto"
            or self._cleaned_truthy(node.presence_key)
        )

        if node.kind == "leaf":
            if not present:
                return MISSING
            if "const" in node.schema:
                return deepcopy(node.schema["const"])
            value = self.form.cleaned_data.get(node.field_key)
            return node.serializer(value) if node.serializer else value

        if node.kind == "object":
            if not present:
                return MISSING
            original = (
                node.initial if node.exists and isinstance(node.initial, dict) else {}
            )
            result = deepcopy(original) if self.preserve_unknown else {}
            for child in node.children:
                value = self._clean_node(child)
                if value is MISSING:
                    result.pop(child.json_key, None)
                else:
                    result[child.json_key] = value
            return result

        if node.kind == "union":
            if not present:
                return MISSING
            selected = self.form.cleaned_data.get(
                node.selector_key,
                node.branch_values[node.selected_branch],
            )
            try:
                branch_index = next(
                    index
                    for index, value in enumerate(node.branch_values)
                    if value == selected or str(value) == str(selected)
                )
                branch = node.branches[branch_index]
            except (IndexError, StopIteration, TypeError, ValueError):
                return MISSING
            return self._clean_node(branch)

        if node.kind == "array":
            if not present:
                return MISSING
            values = []
            for item in node.items:
                if self._cleaned_truthy(item.delete_key):
                    continue
                value = self._clean_node(item.children[0])
                if value is not MISSING:
                    values.append(value)
            return values

        if node.kind == "array_item":
            return self._clean_node(node.children[0])
        raise ValueError(f"Unknown schema node kind {node.kind!r}")

    def _cleaned_truthy(self, key: str | None) -> bool:
        if not key:
            return False
        return bool(self.form.cleaned_data.get(key, False))


def resolve_schema(schema: Schema | Callable[..., Schema], context: Any) -> Schema:
    if not callable(schema):
        return deepcopy(schema)
    try:
        signature = inspect.signature(schema)
    except (TypeError, ValueError):
        return schema(context)
    return schema() if not signature.parameters else schema(context)


def serialize_json_value(value: Any) -> Any:
    if isinstance(value, Model):
        return value.pk
    if isinstance(value, QuerySet):
        return list(value.values_list("pk", flat=True))
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def path_to_string(path: tuple[str | int, ...]) -> str:
    return ".".join(map(str, path))


def path_matches(pattern: str, path: tuple[str | int, ...]) -> bool:
    if pattern in {"", "$"}:
        return not path
    pattern_parts = pattern.split(".")
    path_parts = [str(part) for part in path]

    def match(pi: int, xi: int) -> bool:
        while pi < len(pattern_parts):
            token = pattern_parts[pi]
            if token == "**":
                if pi == len(pattern_parts) - 1:
                    return True
                return any(
                    match(pi + 1, next_x) for next_x in range(xi, len(path_parts) + 1)
                )
            if xi >= len(path_parts):
                return False
            if token != "*" and token != path_parts[xi]:
                return False
            pi += 1
            xi += 1
        return xi == len(path_parts)

    return match(0, 0)
