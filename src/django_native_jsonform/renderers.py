from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

from .binding import Node, SchemaBinding

DEFAULT_TEMPLATES = {
    "widget": "django_native_jsonform/widget.html",
    "leaf": "django_native_jsonform/leaf.html",
    "object": "django_native_jsonform/object.html",
    "array": "django_native_jsonform/array.html",
    "array_item": "django_native_jsonform/array_item.html",
    "union": "django_native_jsonform/union.html",
}


class JSONFormRenderer:
    """Template-based renderer; every node template can be replaced."""

    def __init__(self, templates: Mapping[str, str] | None = None) -> None:
        self.templates = {**DEFAULT_TEMPLATES, **(templates or {})}

    def render(
        self,
        binding: SchemaBinding,
        *,
        attrs: Mapping[str, Any] | None = None,
    ) -> SafeString:
        return mark_safe(
            render_to_string(
                self.templates["widget"],
                {
                    "binding": binding,
                    "root": binding.root,
                    "root_html": self.render_node(binding, binding.root),
                    "attrs": attrs or {},
                },
            )
        )

    def render_node(self, binding: SchemaBinding, node: Node) -> SafeString:
        template_name = node.template_name or self.templates[node.kind]
        context: dict[str, Any] = {
            "binding": binding,
            "node": node,
            "presence": binding.bound_field(node.presence_key),
            "show_presence_toggle": node.override.get("presence_mode") == "explicit",
        }
        if node.kind == "leaf":
            context["field"] = binding.bound_field(node.field_key)
        elif node.kind == "object":
            context["children"] = [
                self.render_node(binding, child) for child in node.children
            ]
        elif node.kind == "union":
            context["selector"] = binding.bound_field(node.selector_key)
            context["branches"] = [
                {
                    "index": index,
                    "value": node.branch_values[index],
                    "active": index == node.selected_branch,
                    "html": self.render_node(binding, branch),
                }
                for index, branch in enumerate(node.branches)
            ]
        elif node.kind == "array":
            context["count"] = binding.bound_field(node.count_key)
            context["items"] = [self.render_node(binding, item) for item in node.items]
            context["prototype"] = (
                self.render_node(binding, node.prototype) if node.prototype else ""
            )
            context["index_token"] = (
                node.prototype.override.get("index_token") if node.prototype else ""
            )
        elif node.kind == "array_item":
            context["order"] = binding.bound_field(node.order_key)
            context["delete"] = binding.bound_field(node.delete_key)
            context["child"] = self.render_node(binding, node.children[0])
            context["index"] = node.override.get(
                "index_token", node.path[-1] if node.path else ""
            )
        html = mark_safe(render_to_string(template_name, context))
        if (
            node.override.get("presence_mode") == "explicit"
            and node.override.get("enable_label")
            and not node.required
        ):
            html = format_html(
                '<div data-jsonform-optional-section data-enable-label="{}" '
                'data-disable-label="{}">{}</div>',
                node.override["enable_label"],
                node.override["disable_label"],
                html,
            )
        rule = node.schema.get("visible_when")
        if not rule:
            return html
        return format_html(
            '<div data-jsonform-visibility="{}" data-jsonform-visibility-parent="{}">'
            '{}<div class="help" data-jsonform-visibility-warning hidden>'
            "{}</div></div>",
            json.dumps(rule),
            ".".join(str(part) for part in node.path[:-1]),
            html,
            node.schema.get("visibility_warning", ""),
        )
