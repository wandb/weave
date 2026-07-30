"""Resolve which instrumentation produced an ingested row.

Answers "which SDK / integration / agent harness wrote this?" as three promoted
columns (`source_name`, `source_version`, `source_sdk`) instead of a JSON scan
over `attributes_dump` / `custom_attrs_string`. This module is the single source
of truth for that resolution; the calls path (`clickhouse/schema_converters.py`)
and the spans path (`opentelemetry/genai_extraction.py`) both go through it.

`source_name` / `source_version` come from the first rung of the ladder that
resolves, and are always taken as a pair so a version never describes a
different rung's name:

1. Explicit attributes — `weave.source.{name,version}` or the
   `attributes["integration"].{name,version}` block the Weave SDK integrations
   stamp (see `weave/integrations/integration_metadata.py`), in either nested or
   flat-dotted form. `agents/semconv.py` owns that key list.
2. The OTel instrumentation scope (`scope.name` / `scope.version`), normalized.
   This is what Codex, the Claude Code plugin, OpenInference and OpenLLMetry
   all set for free, so it attributes them with no client-side work.
3. Resource identity — `service.name` / `service.version`, then
   `telemetry.sdk.name` / `telemetry.sdk.version`.
4. `''` — unattributable.

Not yet a rung: the ingest request `User-Agent`. Reading it needs the FastAPI
layer in `wandb/core` to thread the header into the export request; the
`resolve_*` signatures below are where it would slot in.

`source_sdk` is orthogonal — it records the ingest surface the row arrived on,
which the server always knows exactly, so it never participates in the ladder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from weave.trace_server.agents import semconv
from weave.trace_server.opentelemetry.helpers import get_attribute


@dataclass(frozen=True, slots=True)
class SourceAttribution:
    """Resolved values for the `source_*` columns. Empty string means unknown."""

    name: str = ""
    version: str = ""
    sdk: str = ""


def resolve_for_otel_span(
    *,
    attributes: dict[str, Any] | None,
    scope_name: str = "",
    scope_version: str = "",
    resource_attributes: dict[str, Any] | None = None,
) -> SourceAttribution:
    """Resolve attribution for a span ingested on an OTLP endpoint."""
    return _resolve(
        sdk=SOURCE_SDK_OTLP,
        attributes=attributes,
        scope_name=scope_name,
        scope_version=scope_version,
        resource_attributes=resource_attributes,
    )


def resolve_for_call(
    *,
    attributes: dict[str, Any] | None,
    otel_dump: dict[str, Any] | None = None,
) -> SourceAttribution:
    """Resolve attribution from normalized call attributes and its OTel dump.

    OTLP-converted calls retain their full wire attributes, scope, and resource
    only in `otel_dump`. Normalized call attributes win when both carry an
    explicit source.
    """
    scope = _sub_dict(otel_dump, "scope")
    resource = _sub_dict(otel_dump, "resource")
    return _resolve(
        sdk=SOURCE_SDK_OTLP if otel_dump else SOURCE_SDK_WEAVE,
        attributes=attributes,
        fallback_attributes=_sub_dict(otel_dump, "attributes"),
        scope_name=_as_str(scope.get("name")),
        scope_version=_as_str(scope.get("version")),
        resource_attributes=_sub_dict(resource, "attributes"),
    )


# ---------------------------------------------------------------------------
# Helpers and constants
# ---------------------------------------------------------------------------

# Ingest surfaces. `weave` is the trace-server call API (`/call/start`,
# `/call/upsert_batch`, `/calls/complete`); `otlp` is the OTel trace export.
# Deliberately coarse: separating weave-python from weave-node needs the
# request `User-Agent`, and there is only one OTLP transport (HTTP) today.
SOURCE_SDK_WEAVE = "weave"
SOURCE_SDK_OTLP = "otlp"

# Namespaces producers put in front of the library they instrument. Longest
# match is not needed — none of these is a prefix of another.
_SCOPE_NAME_PREFIXES = (
    "opentelemetry.instrumentation.",
    "@opentelemetry/instrumentation-",
    "openinference.instrumentation.",
    "weave.",
)

# Resource keys probed for identity, name paired with its version. `service.name`
# comes first because it is the identifying one: `telemetry.sdk.name` is
# `opentelemetry` for nearly every producer, which names nothing.
_RESOURCE_IDENTITY_KEYS = (
    ("service.name", "service.version"),
    ("telemetry.sdk.name", "telemetry.sdk.version"),
)

# What OTel SDKs use for `service.name` when the producer never set one. Bare
# and `unknown_service:<executable>` forms both appear.
_PLACEHOLDER_SERVICE_NAME = "unknown_service"


def _resolve(
    *,
    sdk: str,
    attributes: dict[str, Any] | None,
    fallback_attributes: dict[str, Any] | None = None,
    scope_name: str,
    scope_version: str,
    resource_attributes: dict[str, Any] | None,
) -> SourceAttribution:
    """Walk the ladder, taking name and version from the same rung."""
    name, version = (
        _from_explicit_attributes(attributes)
        or _from_explicit_attributes(fallback_attributes)
        or _from_scope(scope_name, scope_version)
        or _from_resource(resource_attributes)
        or ("", "")
    )
    return SourceAttribution(name=name, version=version, sdk=sdk)


def _from_explicit_attributes(
    attributes: dict[str, Any] | None,
) -> tuple[str, str] | None:
    if not attributes:
        return None
    name = _first_str(attributes, semconv.SOURCE_NAME.lookup_keys)
    if not name:
        return None
    return name, _first_str(attributes, semconv.SOURCE_VERSION.lookup_keys)


def _normalize_scope_name(scope_name: str) -> str:
    """Strip instrumentation-library boilerplate from an OTel scope name.

    `opentelemetry.instrumentation.openai` and `openinference.instrumentation.openai`
    both normalize to `openai`, so the same integration groups under one value
    however the producer namespaced it.
    """
    normalized = scope_name.strip()
    for prefix in _SCOPE_NAME_PREFIXES:
        if normalized.startswith(prefix) and len(normalized) > len(prefix):
            return normalized[len(prefix) :]
    return normalized


def _from_scope(scope_name: str, scope_version: str) -> tuple[str, str] | None:
    normalized = _normalize_scope_name(scope_name)
    if not normalized:
        return None
    return normalized, scope_version.strip()


def _from_resource(
    resource_attributes: dict[str, Any] | None,
) -> tuple[str, str] | None:
    if not resource_attributes:
        return None
    for name_key, version_key in _RESOURCE_IDENTITY_KEYS:
        name = _as_str(get_attribute(resource_attributes, name_key))
        if not name or _is_placeholder_service_name(name):
            continue
        return name, _as_str(get_attribute(resource_attributes, version_key))
    return None


def _is_placeholder_service_name(name: str) -> bool:
    return name == _PLACEHOLDER_SERVICE_NAME or name.startswith(
        f"{_PLACEHOLDER_SERVICE_NAME}:"
    )


def _first_str(attributes: dict[str, Any], keys: tuple[str, ...]) -> str:
    """Return the first key in `keys` resolving to a non-empty string."""
    for key in keys:
        value = _as_str(get_attribute(attributes, key))
        if value:
            return value
    return ""


def _as_str(value: Any) -> str:
    """Coerce a scalar to a trimmed string; containers and None become empty."""
    if value is None or isinstance(value, (dict, list)):
        return ""
    return str(value).strip()


def _sub_dict(source: dict[str, Any] | None, key: str) -> dict[str, Any]:
    """Return `source[key]` when it is a dict, else an empty dict."""
    if not source:
        return {}
    value = source.get(key)
    return value if isinstance(value, dict) else {}
