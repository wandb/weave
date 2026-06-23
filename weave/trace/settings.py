"""Settings for Weave.

The settings module exposes a process-level configuration value, scoped per
async-context via a single :class:`ContextVar`.  Read settings via the
field-named accessor functions (e.g. :func:`should_disable_weave`).  Mutate
via :func:`replace_settings` (replace-all snapshot install, used at init) or
:func:`override_settings` (scoped partial change for the current async context).

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
from typing import (
    Any,
    Literal,
    TypedDict,
    TypeVar,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from typing_extensions import Unpack

DEFAULT_RETRY_MAX_INTERVAL_SECONDS = 60 * 5  # 5 minutes
SETTINGS_PREFIX = "WEAVE_"


# Attention Devs:
# To add a new setting:
# 1. Add a new field to `UserSettings`
# 2. Mirror the same name/type on `_SettingsOverrides` below (TypedDict can't
#    be derived from a dataclass while preserving mypy validation).  Drift is
#    caught by `test_settings_overrides_matches_user_settings`.
# 3. Add a thin accessor (e.g.
#    `def should_xyz() -> bool:
#         return _env_or_default("xyz", _current_settings.get().xyz)`)


@dataclass(frozen=True, slots=True)
class UserSettings:
    """User configuration for Weave.

    All configs can be overridden with environment variables.  The precedence
    is environment variables > ``UserSettings`` instance > defaults.

    KEEP IN SYNC WITH :class:`_SettingsOverrides` below.  Each field added,
    removed, or retyped here must be mirrored there so :func:`override_settings`'s
    typed kwargs stay accurate.  The :func:`test_settings_overrides_matches_user_settings`
    test fails on drift.
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

    use_calls_complete: bool = True
    """
    Toggles use of the calls_complete write path for new calls.

    If True (default), uses the calls_complete endpoint which batches complete
    calls (with both start and end information) together before sending to the
    server. This reduces the number of write operations and improves performance.

    If False, uses the legacy call_start/call_end endpoints which send start
    and end events separately.

    Can be overridden with the environment variable `WEAVE_USE_CALLS_COMPLETE`.
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

    use_otel_v2: bool = True
    """
    Routes OTel-capable integrations through their OTel variant.

    When True, integrations that ship a sibling OTel patcher (e.g. ``openai_agents``
    → ``openai_agents_otel``) dispatch to the OTel variant on implicit
    import-hook patching. Explicit ``patch_*`` calls are unaffected — they
    always do exactly what their name says.

    NOTE: plain ``openai`` has no OTel variant, so it is no longer patched on
    implicit import-hook patching. Call ``weave.integrations.patch_openai()``
    explicitly (or set this to False) to trace direct ``openai.*`` calls.

    Can be overridden with the environment variable `WEAVE_USE_OTEL_V2`
    """

    allow_unsafe_custom_obj_decode: bool = True
    """Permits reconstructing code-bearing custom objects (ops, or any type whose
    decode falls back to running a packaged `load_op`) on `client.get`.

    Defaults True, matching historical behavior. Set False to harden a client so it
    only reconstructs data-only custom objects (images, audio, datetimes, etc.) and
    refuses to import or run any stored `.py`. Server-side workers force this off
    regardless via `require_secure_weave_client`; deployments can disable it globally
    with the environment variable `WEAVE_ALLOW_UNSAFE_CUSTOM_OBJ_DECODE=false`.
    """


class _SettingsOverrides(TypedDict, total=False):
    """Typed kwargs accepted by :func:`override_settings`.

    KEEP IN SYNC WITH :class:`UserSettings` above.  This TypedDict mirrors
    every field on ``UserSettings``; mypy needs the field list spelled out
    statically (it can't introspect through ``get_type_hints(UserSettings)``
    or a dict comprehension).  All keys are optional (``total=False``) so
    ``override_settings`` can accept any subset of fields.

    The :func:`test_settings_overrides_matches_user_settings` test asserts
    that this TypedDict and ``UserSettings`` declare exactly the same
    name → type mapping.
    """

    disabled: bool
    print_call_link: bool
    log_level: str
    display_viewer: Literal["auto", "rich", "print"]
    capture_code: bool
    implicitly_patch_integrations: bool
    redact_pii: bool
    redact_pii_fields: list[str]
    redact_pii_exclude_fields: list[str]
    capture_client_info: bool
    capture_system_info: bool
    client_parallelism: int | None
    use_server_cache: bool
    server_cache_size_limit: int
    server_cache_dir: str | None
    scorers_dir: str
    max_calls_queue_size: int
    retry_max_interval: float
    retry_max_attempts: int
    enable_disk_fallback: bool
    use_parallel_table_upload: bool
    http_timeout: float
    use_calls_complete: bool
    enable_client_side_digests: bool
    enable_wal: bool
    disable_wal_sender: bool
    use_otel_v2: bool
    allow_unsafe_custom_obj_decode: bool


# Resolve string annotations once at import; used for env-var coercion.
_FIELD_TYPES: dict[str, Any] = get_type_hints(UserSettings)
_FIELD_NAMES: frozenset[str] = frozenset(_FIELD_TYPES)
_ENV_KEYS: dict[str, str] = {
    name: f"{SETTINGS_PREFIX}{name.upper()}" for name in _FIELD_NAMES
}

# UserSettings is a frozen dataclass, so this instance is immutable and safe
# to share as the ContextVar default.
_DEFAULT_SETTINGS = UserSettings()

_current_settings: ContextVar[UserSettings] = ContextVar(
    "weave_settings", default=_DEFAULT_SETTINGS
)


def _parse_bool(v: str) -> bool:
    return v.lower() in {"yes", "true", "1", "on"}


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


_T = TypeVar("_T")


def _env_or_default(name: str, default: _T) -> _T:
    """Return the env-var value for *name* if set, else *default*.

    The field's runtime type annotation is looked up from :data:`_FIELD_TYPES`
    and used to coerce the env-var string.  Empty env-var strings fall through
    to the default — matching the prior helpers' truthy-check semantics.
    """
    if env := os.getenv(_ENV_KEYS[name]):
        return cast(_T, _parse_env_value(env, _FIELD_TYPES[name]))
    return default


def replace_settings(
    settings: UserSettings | dict[str, Any] | None = None,
) -> None:
    """Replace the current settings snapshot wholesale.

    Pass a :class:`UserSettings` instance, a dict (constructed via
    ``UserSettings(**d)``), or None to reset to defaults.  This wipes every
    field — to change a subset, use :func:`override_settings` instead.
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
parse_and_apply_settings = replace_settings


@contextmanager
def override_settings(
    **fields: Unpack[_SettingsOverrides],
) -> Iterator[UserSettings]:
    """Scope a partial settings change to the current async context.

    Example::

        with override_settings(disabled=True):
            ...

    Only valid :class:`UserSettings` field names are accepted, and each value
    is checked against the field's declared type.
    """
    new_snapshot = replace(_current_settings.get(), **fields)
    token = _current_settings.set(new_snapshot)
    try:
        yield new_snapshot
    finally:
        _current_settings.reset(token)


# ---------------------------------------------------------------------------
# Accessor functions — the public read API.  Each reads from the env-var
# overlay first, then from the current snapshot.
# ---------------------------------------------------------------------------


def should_disable_weave() -> bool:
    return _env_or_default("disabled", _current_settings.get().disabled)


def should_print_call_link() -> bool:
    return _env_or_default("print_call_link", _current_settings.get().print_call_link)


def log_level() -> str:
    return _env_or_default("log_level", _current_settings.get().log_level)


def display_viewer() -> str:
    """Returns the configured display viewer (auto, rich, or print)."""
    return _env_or_default("display_viewer", _current_settings.get().display_viewer)


def should_capture_code() -> bool:
    return _env_or_default("capture_code", _current_settings.get().capture_code)


def should_capture_client_info() -> bool:
    return _env_or_default(
        "capture_client_info", _current_settings.get().capture_client_info
    )


def should_capture_system_info() -> bool:
    return _env_or_default(
        "capture_system_info", _current_settings.get().capture_system_info
    )


def client_parallelism() -> int | None:
    return _env_or_default(
        "client_parallelism", _current_settings.get().client_parallelism
    )


def should_redact_pii() -> bool:
    return _env_or_default("redact_pii", _current_settings.get().redact_pii)


def redact_pii_fields() -> list[str]:
    return _env_or_default(
        "redact_pii_fields", _current_settings.get().redact_pii_fields
    )


def redact_pii_exclude_fields() -> list[str]:
    return _env_or_default(
        "redact_pii_exclude_fields",
        _current_settings.get().redact_pii_exclude_fields,
    )


def use_server_cache() -> bool:
    return _env_or_default("use_server_cache", _current_settings.get().use_server_cache)


def server_cache_size_limit() -> int:
    return _env_or_default(
        "server_cache_size_limit", _current_settings.get().server_cache_size_limit
    )


def server_cache_dir() -> str | None:
    return _env_or_default("server_cache_dir", _current_settings.get().server_cache_dir)


def scorers_dir() -> str:
    return _env_or_default("scorers_dir", _current_settings.get().scorers_dir)


def max_calls_queue_size() -> int:
    return _env_or_default(
        "max_calls_queue_size", _current_settings.get().max_calls_queue_size
    )


def retry_max_attempts() -> int:
    """Returns the maximum number of retry attempts."""
    return _env_or_default(
        "retry_max_attempts", _current_settings.get().retry_max_attempts
    )


def retry_max_interval() -> float:
    """Returns the maximum interval between retries in seconds."""
    return _env_or_default(
        "retry_max_interval", _current_settings.get().retry_max_interval
    )


def should_enable_disk_fallback() -> bool:
    """Returns whether disk fallback should be enabled for dropped items."""
    return _env_or_default(
        "enable_disk_fallback", _current_settings.get().enable_disk_fallback
    )


def should_use_parallel_table_upload() -> bool:
    """Returns whether parallel table upload chunking should be used."""
    return _env_or_default(
        "use_parallel_table_upload",
        _current_settings.get().use_parallel_table_upload,
    )


def should_implicitly_patch_integrations() -> bool:
    """Returns whether implicit patching of integrations is enabled."""
    return _env_or_default(
        "implicitly_patch_integrations",
        _current_settings.get().implicitly_patch_integrations,
    )


def http_timeout() -> float:
    """Returns the HTTP request timeout in seconds."""
    return _env_or_default("http_timeout", _current_settings.get().http_timeout)


def should_use_calls_complete() -> bool:
    """Returns whether the calls_complete write path should be used."""
    return _env_or_default(
        "use_calls_complete", _current_settings.get().use_calls_complete
    )


def should_enable_client_side_digests() -> bool:
    """Returns whether client-side digest computation should be used."""
    return _env_or_default(
        "enable_client_side_digests",
        _current_settings.get().enable_client_side_digests,
    )


def should_enable_wal() -> bool:
    """Returns whether the Write-Ahead Log should be used."""
    return _env_or_default("enable_wal", _current_settings.get().enable_wal)


def should_disable_wal_sender() -> bool:
    """Returns whether the WAL sender thread should be disabled."""
    return _env_or_default(
        "disable_wal_sender", _current_settings.get().disable_wal_sender
    )


def should_use_otel_v2() -> bool:
    """Returns whether OTel-capable integrations should use their OTel variant."""
    return _env_or_default("use_otel_v2", _current_settings.get().use_otel_v2)


def should_allow_unsafe_custom_obj_decode() -> bool:
    """Returns whether reconstructing code-bearing custom objects is permitted."""
    return _env_or_default(
        "allow_unsafe_custom_obj_decode",
        _current_settings.get().allow_unsafe_custom_obj_decode,
    )
