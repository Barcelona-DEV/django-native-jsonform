from types import SimpleNamespace

from .fields import JSONSchemaFormMixin, JSONSchemaModelFormMixin


class JSONSchemaAdminMixin:
    """Give native JSON fields the current admin user and edited object."""

    def get_json_form_context(self, request, obj=None):
        return SimpleNamespace(user=request.user, obj=obj, request=request)

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)
        bases = (
            (base_form,)
            if issubclass(base_form, JSONSchemaFormMixin)
            else (JSONSchemaModelFormMixin, base_form)
        )
        return type(
            f"NativeJSON{base_form.__name__}",
            bases,
            {
                "__module__": base_form.__module__,
                "json_form_context": self.get_json_form_context(request, obj),
            },
        )
