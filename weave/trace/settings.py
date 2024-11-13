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
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

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


class OpSettings(BaseModel):
    """Settings for weave ops intended to be used to configure auto-patched functions.

    These currently mirror the `op` decorator args to provide a consistent interface
    when working with auto-patched functions.  See the `op` decorator for more details."""

    call_display_name: Optional[Union[str, Callable[[Any], str]]] = None
    postprocess_inputs: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None
    postprocess_output: Optional[Callable[[Any], Any]] = None


class IntegrationSettings(BaseModel):
    """Settings for a specific integration.

    By default, integrations are enabled and have no additional op options set."""

    enabled: bool = True
    options: OpSettings = Field(default_factory=OpSettings)


class PatchSettings(BaseModel):
    """Settings for configuring auto-patching integrations."""

    openai: IntegrationSettings = Field(default_factory=IntegrationSettings)
    mistral: IntegrationSettings = Field(default_factory=IntegrationSettings)
    litellm: IntegrationSettings = Field(default_factory=IntegrationSettings)
    llamaindex: IntegrationSettings = Field(default_factory=IntegrationSettings)
    langchain: IntegrationSettings = Field(default_factory=IntegrationSettings)
    anthropic: IntegrationSettings = Field(default_factory=IntegrationSettings)
    groq: IntegrationSettings = Field(default_factory=IntegrationSettings)
    instructor: IntegrationSettings = Field(default_factory=IntegrationSettings)
    dspy: IntegrationSettings = Field(default_factory=IntegrationSettings)
    cerebras: IntegrationSettings = Field(default_factory=IntegrationSettings)
    cohere: IntegrationSettings = Field(default_factory=IntegrationSettings)
    google_genai: IntegrationSettings = Field(default_factory=IntegrationSettings)
    notdiamond: IntegrationSettings = Field(default_factory=IntegrationSettings)


__doc_spec__ = [UserSettings, PatchSettings]
