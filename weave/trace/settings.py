"""Settings for Weave.

To add new settings:
1. Add a new field to `UserSettings`
2. Add a new `should_{xyz}` function
"""

import os
from contextvars import ContextVar
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, PrivateAttr

SETTINGS_PREFIX = "WEAVE_"


class UserSettings(BaseModel):
    """User configuration for Weave.

    All configs can be overrided with environment variables.  The precedence is
    environment variables > `weave.trace.settings.UserSettings`."""

    disabled: bool = False
    """Toggles Weave tracing.
    
    If True, all weave ops will behave like regular functions.
    Can be overrided with the environment variable `WEAVE_DISABLED`"""

    print_call_link: bool = True
    """Toggles link printing to the terminal.

    If True, prints a link to the Weave UI when calling a weave op.
    Can be overrided with the environment variable `WEAVE_PRINT_CALL_LINK`"""

    model_config = ConfigDict(extra="forbid")
    _is_first_apply: bool = PrivateAttr(True)

    def _reset(self) -> None:
        for name, field in self.model_fields.items():
            setattr(self, name, field.default)

    def apply(self) -> None:
        if self._is_first_apply:
            self._is_first_apply = False
        else:
            self._reset()

        for name in self.model_fields:
            context_var = _context_vars[name]
            context_var.set(getattr(self, name))


def should_disable_weave() -> bool:
    return _should("disabled")


def should_print_call_link() -> bool:
    return _should("print_call_link")


def parse_and_apply_settings(
    settings: Optional[Union[UserSettings, dict[str, Any]]] = None,
) -> None:
    if settings is None:
        user_settings = UserSettings()
    if isinstance(settings, dict):
        user_settings = UserSettings.model_validate(settings)
    if isinstance(settings, UserSettings):
        user_settings = settings

    user_settings.apply()


_context_vars = {
    name: ContextVar(name, default=field.default)
    for name, field in UserSettings.model_fields.items()
}


def _str2bool_truthy(v: str) -> bool:
    return v.lower() in ("yes", "true", "1", "on")


def _should(name: str) -> bool:
    if env := os.getenv(f"{SETTINGS_PREFIX}{name.upper()}"):
        return _str2bool_truthy(env)
    return _context_vars[name].get()
