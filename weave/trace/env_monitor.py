"""Monitor and warn about late WEAVE_* environment variable settings.

This module tracks when Weave is initialized and detects if WEAVE_* environment
variables are set after initialization, which can lead to unexpected behavior
since the settings may have already been read.
"""

from __future__ import annotations

import logging
import os
import warnings
from typing import Any

logger = logging.getLogger(__name__)

# Track when weave has been initialized
_weave_initialized = False

# Store the initial state of WEAVE_* environment variables
_initial_weave_env_vars: dict[str, str | None] = {}


def mark_weave_initialized() -> None:
    """Mark that Weave has been initialized.

    This should be called in init_weave() to enable monitoring of
    subsequent environment variable changes.
    """
    global _weave_initialized, _initial_weave_env_vars
    _weave_initialized = True
    # Capture the current state of all WEAVE_* env vars
    _initial_weave_env_vars = {
        key: value for key, value in os.environ.items() if key.startswith("WEAVE_")
    }


def is_weave_initialized() -> bool:
    """Check if Weave has been initialized."""
    return _weave_initialized


def _check_for_late_env_vars() -> None:
    """Check if any WEAVE_* env vars have been added or modified after initialization."""
    if not _weave_initialized:
        return

    # Get current WEAVE_* env vars
    current_weave_env_vars = {
        key: value for key, value in os.environ.items() if key.startswith("WEAVE_")
    }

    # Check for new or modified env vars
    for key, value in current_weave_env_vars.items():
        initial_value = _initial_weave_env_vars.get(key)
        if initial_value != value:
            if initial_value is None:
                # New env var added after init
                warnings.warn(
                    f"Environment variable '{key}' was set to '{value}' after Weave "
                    f"initialization. This may not have any effect as Weave settings are "
                    f"typically read during initialization. Set environment variables "
                    f"before calling weave.init() to ensure they take effect.",
                    UserWarning,
                    stacklevel=3,
                )
                logger.warning(
                    f"Late environment variable detected: {key}={value}. "
                    f"This was set after Weave initialization and may not have any effect."
                )
            else:
                # Existing env var modified after init
                warnings.warn(
                    f"Environment variable '{key}' was changed from '{initial_value}' to "
                    f"'{value}' after Weave initialization. This may not have any effect as "
                    f"Weave settings are typically read during initialization. Set environment "
                    f"variables before calling weave.init() to ensure they take effect.",
                    UserWarning,
                    stacklevel=3,
                )
                logger.warning(
                    f"Late environment variable change detected: {key} changed from "
                    f"'{initial_value}' to '{value}' after Weave initialization."
                )
            # Update our tracking to avoid duplicate warnings
            _initial_weave_env_vars[key] = value


class _EnvMonitorDict(dict[str, str]):
    """A dict subclass that monitors WEAVE_* environment variable changes."""

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(key, value)
        if key.startswith("WEAVE_"):
            _check_for_late_env_vars()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        if key.startswith("WEAVE_"):
            _check_for_late_env_vars()

    def pop(self, key: str, *args: Any) -> Any:
        result = super().pop(key, *args)
        if key.startswith("WEAVE_"):
            _check_for_late_env_vars()
        return result

    def popitem(self) -> tuple[str, str]:
        result = super().popitem()
        if result[0].startswith("WEAVE_"):
            _check_for_late_env_vars()
        return result

    def setdefault(self, key: str, default: str | None = None) -> Any:
        result = super().setdefault(key, default)
        if key.startswith("WEAVE_"):
            _check_for_late_env_vars()
        return result

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        # Check if any WEAVE_* vars were updated
        if any(k.startswith("WEAVE_") for k in kwargs.keys()) or (
            args and any(k.startswith("WEAVE_") for k in (args[0].keys() if hasattr(args[0], 'keys') else []))
        ):
            _check_for_late_env_vars()


def install_env_monitor() -> None:
    """Install the environment variable monitor.

    This replaces os.environ with a monitored version that detects
    when WEAVE_* environment variables are set after initialization.

    Note: This is automatically called during weave.init().
    """
    if not isinstance(os.environ, _EnvMonitorDict):
        # Replace os.environ with our monitored version
        monitored_environ = _EnvMonitorDict(os.environ)
        os.environ = monitored_environ  # type: ignore


def reset_monitor() -> None:
    """Reset the monitor state. Primarily for testing purposes."""
    global _weave_initialized, _initial_weave_env_vars
    _weave_initialized = False
    _initial_weave_env_vars = {}
