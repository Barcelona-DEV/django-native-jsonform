"""Schema-driven JSON forms built from Django's native form primitives."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("django-native-jsonform")
except PackageNotFoundError:  # pragma: no cover - source checkout
    __version__ = "0.1.0"

from .admin import JSONSchemaAdminMixin
from .binding import BuildContext
from .exceptions import JSONFormValidationError
from .fields import (
    JSONSchemaFormField,
    JSONSchemaFormMixin,
    JSONSchemaModelForm,
    JSONSchemaModelFormMixin,
)
from .registry import (
    FieldFactoryContext,
    JSONFormRegistry,
    WidgetFactoryContext,
    default_registry,
)
from .renderers import JSONFormRenderer
from .widgets import JSONSchemaWidget

__all__ = [
    "BuildContext",
    "FieldFactoryContext",
    "JSONFormRegistry",
    "JSONFormRenderer",
    "JSONFormValidationError",
    "JSONSchemaAdminMixin",
    "JSONSchemaFormField",
    "JSONSchemaFormMixin",
    "JSONSchemaModelForm",
    "JSONSchemaModelFormMixin",
    "JSONSchemaWidget",
    "WidgetFactoryContext",
    "__version__",
    "default_registry",
]
