import os
from contextvars import ContextVar
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, PrivateAttr

disabled = ContextVar("disabled", default=False)
print_call_link = ContextVar("disabled", default=True)


class UserSettings(BaseModel):
    """User configuration for Weave.

    All configs can be overrided with environment variables.  The precedence is
    environment variables > `weave.trace.settings` > default"""

    disabled: bool = False
    """Whether to disable the Weave tracing completely.
    
    This setting will make all weave code into no-ops.

    Can be overrided with the environment variable `WEAVE_DISABLED`"""

    print_call_link: bool = True
    """Whether to print call links when calling an op.

    Can be overrided with the environment variable `WEAVE_PRINT_CALL_LINK`"""

    model_config = ConfigDict(extra="forbid")
    _is_first_apply: bool = PrivateAttr(True)

    def _reset(self) -> None:
        self.disabled = False
        self.print_call_link = True

    def apply(self) -> None:
        if self._is_first_apply:
            self._is_first_apply = False
        else:
            self._reset()

        disabled.set(self.disabled)
        print_call_link.set(self.print_call_link)


def should_disable_weave() -> bool:
    if os.getenv("WEAVE_DISABLED") == "true":
        return True
    if disabled.get():
        return True
    return False


def should_print_call_link() -> bool:
    if os.getenv("WEAVE_PRINT_CALL_LINK") == "true":
        return True
    if print_call_link.get():
        return True
    return False


def parse_and_apply_settings(
    settings: Optional[Union[UserSettings, dict[str, Any]]] = None,
) -> None:
    if settings is None:
        settings = UserSettings()
    elif isinstance(settings, dict):
        settings = UserSettings.model_validate(settings)
    settings.apply()
