"""Settings for Weave.

## `disabled`

* Environment Variable: `WEAVE_DISABLED`
* Settings Key: `disabled`
* Default: `False`
* Type: `bool`

If True, all weave ops will behave like regular functions and no network requests will be made.

## `print_call_link`

* Environment Variable: `WEAVE_PRINT_CALL_LINK`
* Settings Key: `print_call_link`
* Default: `True`
* Type: `bool`

If True, prints a link to the Weave UI when calling a weave op.
"""

import os
from contextvars import ContextVar
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, PrivateAttr

SETTINGS_PREFIX = "WEAVE_"

# Attention Devs:
# To add new settings:
# 1. Add a new field to `UserSettings`
# 2. Add a new `should_{xyz}` function


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

    capture_code: bool = True
    """Toggles code capture for ops.
    
    If True, saves code for ops so they can be reloaded for later use.
    Can be overrided with the environment variable `WEAVE_CAPTURE_CODE`
    
    WARNING: Switching between `save_code=True` and `save_code=False` mid-script
    may lead to unexpected behaviour.  Make sure this is only set once at the start!
    """

    client_parallelism: Optional[int] = None
    """
    Sets the number of workers to use for background operations.
    If not set, automatically adjusts based on the number of cores.

    Setting this to 0 will effectively execute all background operations
    immediately in the main thread. This will not be great for performance,
    but can be useful for debugging.

    This cannot be changed after the client has been initialized.
    """

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


def should_capture_code() -> bool:
    return _should("capture_code")


def client_parallelism() -> Optional[int]:
    return _optional_int("client_parallelism")


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


def _optional_int(name: str) -> Optional[int]:
    if env := os.getenv(f"{SETTINGS_PREFIX}{name.upper()}"):
        return int(env)
    return _context_vars[name].get()


__doc_spec__ = [UserSettings]
