"""Resolve source_name, source_version, and ingest_source on ingest.

Ladder for `source_name` / `source_version` (always taken as a pair):
1. Explicit attributes (`weave.source.*`, `integration.*`, `weave.integration.*`).
2. OTel instrumentation scope, normalized.
3. `''`.

Not yet a rung: request `User-Agent` (needs FastAPI to thread the header in).

`ingest_source` records the server endpoint and never participates in the ladder.
See `agents/semconv.py` and migration 040.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from weave.trace_server.agents import semconv
from weave.trace_server.opentelemetry.helpers import get_attribute


@dataclass(frozen=True, slots=True)
class SourceAttribution:
    """Resolved source attribution. Empty string means unknown."""

    name: str = ""
    version: str = ""
    ingest_source: str = ""


def resolve_for_otel_span(
    *,
    attributes: dict[str, Any] | None,
    scope_name: str = "",
    scope_version: str = "",
) -> SourceAttribution:
    """Resolve attribution for a span ingested on an OTLP endpoint."""
    return _resolve(
        ingest_source=INGEST_SOURCE_OTLP,
        attributes=attributes,
        scope_name=scope_name,
        scope_version=scope_version,
    )


def resolve_for_call(
    *,
    attributes: dict[str, Any] | None,
    ingest_source: str,
    otel_dump: dict[str, Any] | None = None,
) -> SourceAttribution:
    """Resolve attribution from normalized call attributes and its OTel dump.

    OTLP-converted calls retain their full wire attributes and scope only in
    `otel_dump`. Normalized call attributes win when both carry an explicit
    source.
    """
    scope = _sub_dict(otel_dump, "scope")
    return _resolve(
        ingest_source=ingest_source,
        attributes=attributes,
        fallback_attributes=_sub_dict(otel_dump, "attributes"),
        scope_name=_as_str(scope.get("name")),
        scope_version=_as_str(scope.get("version")),
    )


# ---------------------------------------------------------------------------
# Helpers and constants
# ---------------------------------------------------------------------------

# Ingest surfaces. `weave` is the trace-server call API (`/call/start`,
# `/call/upsert_batch`, `/calls/complete`); `otlp` is the OTel trace export.
# Deliberately coarse: separating weave-python from weave-node needs the
# request `User-Agent`, and there is only one OTLP transport (HTTP) today.
INGEST_SOURCE_WEAVE = "weave"
INGEST_SOURCE_OTLP = "otlp"

# Namespaces producers put in front of the library they instrument. Longest
# match is not needed; none of these is a prefix of another.
_SCOPE_NAME_PREFIXES = (
    "opentelemetry.instrumentation.",
    "@opentelemetry/instrumentation-",
    "openinference.instrumentation.",
    "weave.",
)


def _resolve(
    *,
    ingest_source: str,
    attributes: dict[str, Any] | None,
    fallback_attributes: dict[str, Any] | None = None,
    scope_name: str,
    scope_version: str,
) -> SourceAttribution:
    """Walk the ladder, taking name and version from the same rung."""
    name, version = (
        _from_explicit_attributes(attributes)
        or _from_explicit_attributes(fallback_attributes)
        or _from_scope(scope_name, scope_version)
        or ("", "")
    )
    return SourceAttribution(
        name=name,
        version=version,
        ingest_source=ingest_source,
    )


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
