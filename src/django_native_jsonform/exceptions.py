from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.core.exceptions import ValidationError
from django.utils.functional import Promise


class JSONFormValidationError(ValidationError):
    """Validation error carrying messages indexed by JSON path.

    Validators attached to :class:`JSONSchemaFormField` may raise this exception
    to place an error beside a generated child field rather than only beside the
    outer JSON field.
    """

    def __init__(
        self,
        message: str,
        *,
        errors: Mapping[str, str | Iterable[str]],
        code: str = "invalid_json_form",
    ) -> None:
        super().__init__(message, code=code)
        self.path_errors = {
            path: [str(messages)]
            if isinstance(messages, (str, Promise))
            else list(messages)
            for path, messages in errors.items()
        }
