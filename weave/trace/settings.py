"""Settings for Weave.

The settings module exposes a process-level configuration value, scoped per
async-context via a single :class:`ContextVar`.  Read settings via
:func:`current` (returns a :class:`SettingsView` with environment-variable
overlay) or one of the back-compat accessor functions (e.g.
:func:`should_disable_weave`).  Mutate via :func:`apply` (replace-all) or
:func:`override` (scoped patch).

Each field's environment variable is ``WEAVE_<FIELD_NAME>`` (uppercased), e.g.
``WEAVE_DISABLED`` for the ``disabled`` field.  Environment variables override
the snapshot on every read.

## ``disabled``

* Environment Variable: ``WEAVE_DISABLED``
* Settings Key: ``disabled``
* Default: ``False``
* Type: ``bool``

If True, all weave ops will behave like regular functions and no network
requests will be made.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, get_args, get_origin, get_type_hints

DEFAULT_RETRY_MAX_INTERVAL_SECONDS = 60 * 5  # 5 minutes
SETTINGS_PREFIX = "WEAVE_"

# Entities that auto-opt-in to the calls_complete write path, independent of
# the WEAVE_USE_CALLS_COMPLETE env var. This lets us dogfood calls_complete on
# wandb-internal projects first so any regressions land on us, not customers.
# Expand the allowlist (or flip the env default) once we have confidence.
CALLS_COMPLETE_ENTITY_ALLOWLIST: frozenset[str] = frozenset({"wandb"})


# Attention Devs:
# To add a new setting:
# 1. Add a new field to `UserSettings`
# 2. Add a thin accessor (e.g. `def should_xyz() -> bool: return current().xyz`)


@dataclass(frozen=True, slots=True)
class UserSettings:
    """User configuration for Weave.

    All configs can be overridden with environment variables.  The precedence
    is environment variables > ``UserSettings`` instance > defaults.
    """

    disabled: bool = False
    """Toggles Weave tracing.

    If True, all weave ops will behave like regular functions.
    Can be overridden with the environment variable `WEAVE_DISABLED`"""

    print_call_link: bool = True
    """Toggles link printing to the terminal.

    If True, prints a link to the Weave UI when calling a weave op.
    Can be overridden with the environment variable `WEAVE_PRINT_CALL_LINK`"""

    log_level: str = "INFO"
    """Toggles the log level.

    Controls the log level of the weave logger.
    Valid values are: DEBUG, INFO, WARNING, ERROR, CRITICAL
    Can be overridden with the environment variable `WEAVE_LOG_LEVEL`"""

    display_viewer: Literal["auto", "rich", "print"] = "auto"
    """Sets the display viewer for console output.

    Controls which viewer implementation to use for display operations.
    Valid values are: auto, rich, print
    - auto: Automatically selects rich if available, otherwise falls back to print
    - rich: Uses the rich library for enhanced terminal output
    - print: Uses basic print functions for output
    Can be overridden with the environment variable `WEAVE_DISPLAY_VIEWER`"""

    capture_code: bool = True
    """Toggles code capture for ops.

    If True, saves code for ops so they can be reloaded for later use.
    Can be overridden with the environment variable `WEAVE_CAPTURE_CODE`

    WARNING: Switching between `save_code=True` and `save_code=False` mid-script
    may lead to unexpected behavior.  Make sure this is only set once at the start!
    """

    implicitly_patch_integrations: bool = True
    """Toggles implicit patching of integrations.

    If True, supported libraries (OpenAI, Anthropic, etc.) are automatically patched
    when imported, regardless of import order. If False, you must explicitly call
    patch functions like `weave.integrations.patch_openai()` to enable tracing for integrations.
    Can be overridden with the environment variable `WEAVE_IMPLICITLY_PATCH_INTEGRATIONS`"""

    redact_pii: bool = False
    """Toggles PII redaction using Microsoft Presidio.

    If True, redacts PII from trace data before sending to the server.
    Can be overridden with the environment variable `WEAVE_REDACT_PII`
    """

    redact_pii_fields: list[str] = field(default_factory=list)
    """List of fields to redact.

    If redact_pii is True, this list of fields will be redacted.
    If redact_pii is False, this list is ignored.
    If this list is left empty, the default fields will be redacted.

    A list of supported fields can be found here: https://microsoft.github.io/presidio/supported_entities/
    Can be overridden with the environment variable `WEAVE_REDACT_PII_FIELDS`
    """

    redact_pii_exclude_fields: list[str] = field(default_factory=list)
    """List of PII entity types to exclude from redaction.

    Only applies when `redact_pii` is True. Entities in this list are removed from the redaction set.
    Can be overridden with the environment variable `WEAVE_REDACT_PII_EXCLUDE_FIELDS`
    """

    capture_client_info: bool = True
    """Toggles capture of client information (Python version, SDK version) for ops."""

    capture_system_info: bool = True
    """Toggles capture of system information (OS name and version) for ops."""

    client_parallelism: int | None = None
    """
    Sets the number of workers to use for background operations.
    If not set, automatically adjusts based on the number of cores.

    Setting this to 0 will effectively execute all background operations
    immediately in the main thread. This will not be great for performance,
    but can be useful for debugging.

    This cannot be changed after the client has been initialized.
    """

    use_server_cache: bool = True
    """
    Toggles caching of server responses, defaults to True

    If True, caches server responses to disk at `WEAVE_SERVER_CACHE_DIR`.
    Can be overridden with the environment variable `WEAVE_USE_SERVER_CACHE`
    """

    server_cache_size_limit: int = 1_000_000_000
    """
    Sets the size limit in bytes for the server cache, defaults to 1GB (1_000_000_000 bytes).
    Ignored if `use_server_cache` is False.

    Can be overridden with the environment variable `WEAVE_SERVER_CACHE_SIZE_LIMIT`
    """

    server_cache_dir: str | None = None
    """
    Sets the directory for the server cache, defaults to None (temporary cache)
    Ignored if `use_server_cache` is False.

    Can be overridden with the environment variable `WEAVE_SERVER_CACHE_DIR`
    """

    scorers_dir: str = str(Path.home() / ".cache" / "wandb" / "weave-scorers")
    """
    Sets the directory for the scorers model checkpoints. Defaults to
    ~/.cache/wandb/weave-scorers.

    Can be overridden with the environment variable `WEAVE_SCORERS_DIR`

    """

    max_calls_queue_size: int = 100_000
    """
    Sets the maximum size of the calls queue.  Defaults to 100_000.
    Setting a value of 0 means the queue can grow unbounded.

    Can be overridden with the environment variable `WEAVE_MAX_CALLS_QUEUE_SIZE`
    """

    retry_max_interval: float = DEFAULT_RETRY_MAX_INTERVAL_SECONDS
    """
    Sets the maximum interval between retries.  Defaults to 5 minutes.

    Can be overridden with the environment variable `WEAVE_RETRY_MAX_INTERVAL`
    """

    retry_max_attempts: int = 3
    """
    Sets the maximum number of retries.  Defaults to 3.

    Can be overridden with the environment variable `WEAVE_RETRY_MAX_ATTEMPTS`
    """

    enable_disk_fallback: bool = True
    """
    Toggles disk fallback for dropped items.

    If True, items that fail to be processed or are dropped due to queue limits
    will be written to disk as a fallback instead of being lost.
    Can be overridden with the environment variable `WEAVE_ENABLE_DISK_FALLBACK`
    """

    use_parallel_table_upload: bool = True
    """
    Toggles parallel table upload chunking.

    If True, enables parallel upload of table chunks when tables are large enough
    to require chunking. If False, uses incremental upload method.
    Can be overridden with the environment variable `WEAVE_USE_PARALLEL_TABLE_UPLOAD`
    """

    http_timeout: float = 30.0
    """
    Sets the HTTP request timeout in seconds. Defaults to 30 seconds.

    This timeout applies to all HTTP requests made by the Weave client,
    including initialization calls and API requests.

    Can be overridden with the environment variable `WEAVE_HTTP_TIMEOUT`
    """

    use_stainless_server: bool = False
    """
    Toggles use of the stainless-generated HTTP client for trace server communication.

    If True, uses StainlessRemoteHTTPTraceServer instead of RemoteHTTPTraceServer.
    This provides better type safety and automatic client generation from OpenAPI specs.
    Can be overridden with the environment variable `WEAVE_USE_STAINLESS_SERVER`
    """

    use_calls_complete: bool = False
    """
    Toggles use of the calls_complete write path for new calls.

    If True, uses the new calls_complete endpoint which batches complete calls
    (with both start and end information) together before sending to the server.
    This reduces the number of write operations and improves performance.

    If False (default), uses the legacy call_start/call_end endpoints which
    send start and end events separately.

    Can be overridden with the environment variable `WEAVE_USE_CALLS_COMPLETE`.

    Note: entities in `CALLS_COMPLETE_ENTITY_ALLOWLIST` auto-opt-in regardless
    of this setting (see `should_use_calls_complete`).
    """

    enable_client_side_digests: bool = False
    """
    Toggles client-side digest computation for objects and tables.

    If True, the client computes digests locally and constructs refs
    immediately, then sends data to the server with an expected_digest for
    validation. This avoids blocking on server round-trips.

    If False (default), the client defers digest computation to the server
    (legacy behavior).
    Use this if the server does not yet support internal refs or expected_digest.

    Can be overridden with the environment variable `WEAVE_ENABLE_CLIENT_SIDE_DIGESTS`
    """

    enable_wal: bool = False
    """
    Toggles the Write-Ahead Log (WAL) for durable request persistence.

    If True, all requests to the trace server are written to a local JSONL
    WAL file before being sent.  This makes requests durable across process
    crashes — a background consumer can replay unflushed records on restart.

    If False (default), requests are only held in memory before sending.

    Can be overridden with the environment variable `WEAVE_ENABLE_WAL`
    """

    disable_wal_sender: bool = False
    """
    Disables the background WAL sender thread.

    When True and WAL is enabled, records are written to disk but never
    drained automatically.  Useful for testing the WAL write path in
    isolation or for scenarios where a separate process handles draining.

    Can be overridden with the environment variable `WEAVE_DISABLE_WAL_SENDER`
    """


# Resolve string annotations once at import; used for env-var coercion.
_FIELD_TYPES: dict[str, Any] = get_type_hints(UserSettings)
_FIELD_NAMES: frozenset[str] = frozenset(_FIELD_TYPES)

# UserSettings is a frozen dataclass, so this instance is immutable and safe
# to share as the ContextVar default.
_DEFAULT_SETTINGS = UserSettings()

_current_settings: ContextVar[UserSettings] = ContextVar(
    "weave_settings", default=_DEFAULT_SETTINGS
)


def _parse_bool(v: str) -> bool:
    return v.lower() in {"yes", "true", "1", "on"}


# Back-compat alias for callers outside this module.
_str2bool_truthy = _parse_bool


def _parse_env_value(raw: str, annotation: Any) -> Any:
    """Coerce an environment-variable string into the field's declared type."""
    origin = get_origin(annotation)
    if origin is None:
        if annotation is bool:
            return _parse_bool(raw)
        if annotation is int:
            return int(raw)
        if annotation is float:
            return float(raw)
        # str, Literal[...] fall through and return the raw string
        return raw
    # list[X] / tuple[X] — split on comma. Checked before Optional handling
    # because `get_args(list[str])` is `(str,)` which would otherwise look like
    # a single-arm Optional.
    if origin in {list, tuple}:
        return raw.split(",")
    # Optional[X] / X | None — pick the non-None arm
    non_none_args = [a for a in get_args(annotation) if a is not type(None)]
    if len(non_none_args) == 1:
        return _parse_env_value(raw, non_none_args[0])
    return raw


class SettingsView:
    """Read-only view over a :class:`UserSettings` snapshot, with env overlay.

    For every field, an environment variable named ``WEAVE_<FIELD_NAME>``
    overrides the snapshot's value when set to a truthy string (an empty env
    var falls through to the snapshot, matching the prior helpers' behavior).
    """

    __slots__ = ("_snapshot",)

    def __init__(self, snapshot: UserSettings) -> None:
        self._snapshot = snapshot

    def __getattr__(self, name: str) -> Any:
        if name not in _FIELD_NAMES:
            raise AttributeError(f"UserSettings has no field {name!r}")
        if env := os.getenv(f"{SETTINGS_PREFIX}{name.upper()}"):
            return _parse_env_value(env, _FIELD_TYPES[name])
        return getattr(self._snapshot, name)


def current() -> SettingsView:
    """Return a view over the current settings snapshot."""
    return SettingsView(_current_settings.get())


def apply(settings: UserSettings | dict[str, Any] | None = None) -> None:
    """Replace the current settings snapshot.

    Pass a :class:`UserSettings` instance, a dict (constructed via
    ``UserSettings(**d)``), or None to reset to defaults.
    """
    if settings is None:
        snapshot = UserSettings()
    elif isinstance(settings, UserSettings):
        snapshot = settings
    elif isinstance(settings, dict):
        snapshot = UserSettings(**settings)
    else:
        raise TypeError(
            f"settings must be UserSettings, dict, or None; got {type(settings).__name__}"
        )
    _current_settings.set(snapshot)


# Back-compat alias for the prior public API.
parse_and_apply_settings = apply


@contextmanager
def override(**fields: Any) -> Iterator[SettingsView]:
    """Scope a partial settings override to the current async context.

    Example::

        with override(disabled=True):
            ...
    """
    new_snapshot = replace(_current_settings.get(), **fields)
    token = _current_settings.set(new_snapshot)
    try:
        yield SettingsView(new_snapshot)
    finally:
        _current_settings.reset(token)


# ---------------------------------------------------------------------------
# Accessor functions (back-compat).  New code can call `current().<field>`.
# ---------------------------------------------------------------------------


def should_disable_weave() -> bool:
    return current().disabled


def should_print_call_link() -> bool:
    return current().print_call_link


def log_level() -> str:
    return current().log_level or "INFO"


def display_viewer() -> str:
    """Returns the configured display viewer.

    Returns:
        The display viewer to use (auto, rich, or print).
    """
    return current().display_viewer or "auto"


def should_capture_code() -> bool:
    return current().capture_code


def should_capture_client_info() -> bool:
    return current().capture_client_info


def should_capture_system_info() -> bool:
    return current().capture_system_info


def client_parallelism() -> int | None:
    return current().client_parallelism


def should_redact_pii() -> bool:
    return current().redact_pii


def redact_pii_fields() -> list[str]:
    return current().redact_pii_fields


def redact_pii_exclude_fields() -> list[str]:
    return current().redact_pii_exclude_fields


def use_server_cache() -> bool:
    return current().use_server_cache


def server_cache_size_limit() -> int:
    return current().server_cache_size_limit or 1_000_000_000


def server_cache_dir() -> str | None:
    return current().server_cache_dir


def scorers_dir() -> str:
    return current().scorers_dir


def max_calls_queue_size() -> int:
    value = current().max_calls_queue_size
    if value is None:
        return 100_000
    return value


def retry_max_attempts() -> int:
    """Returns the maximum number of retry attempts."""
    value = current().retry_max_attempts
    if value is None:
        return 3
    return value


def retry_max_interval() -> float:
    """Returns the maximum interval between retries in seconds."""
    value = current().retry_max_interval
    if value is None:
        return DEFAULT_RETRY_MAX_INTERVAL_SECONDS
    return value


def should_enable_disk_fallback() -> bool:
    """Returns whether disk fallback should be enabled for dropped items."""
    return current().enable_disk_fallback


def should_use_parallel_table_upload() -> bool:
    """Returns whether parallel table upload chunking should be used."""
    return current().use_parallel_table_upload


def should_implicitly_patch_integrations() -> bool:
    """Returns whether implicit patching of integrations is enabled."""
    return current().implicitly_patch_integrations


def http_timeout() -> float:
    """Returns the HTTP request timeout in seconds."""
    value = current().http_timeout
    if value is None:
        return 30.0
    return value


def should_use_stainless_server() -> bool:
    """Returns whether the stainless-generated HTTP client should be used."""
    return current().use_stainless_server


def should_use_calls_complete(entity: str | None = None) -> bool:
    """Returns whether the calls_complete write path should be used.

    True if the `use_calls_complete` setting/env var is enabled, OR if
    `entity` is in `CALLS_COMPLETE_ENTITY_ALLOWLIST` (dogfood gate).
    """
    if current().use_calls_complete:
        return True
    return entity is not None and entity in CALLS_COMPLETE_ENTITY_ALLOWLIST


def should_enable_client_side_digests() -> bool:
    """Returns whether client-side digest computation should be used."""
    return current().enable_client_side_digests


def should_enable_wal() -> bool:
    """Returns whether the Write-Ahead Log should be used."""
    return current().enable_wal


def should_disable_wal_sender() -> bool:
    """Returns whether the WAL sender thread should be disabled."""
    return current().disable_wal_sender
