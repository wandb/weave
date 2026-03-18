"""Utilities for OTel-based GenAI tracing with Weave.

Key surface area:

Setup:
    - ``setup_tracing``: one-call TracerProvider configuration.
    - ``SystemPromptInjector``: SpanProcessor that fills the upstream gap
      where instrumentors don't emit ``gen_ai.system_instructions``.
    - ``LiveSpanProcessor``: ships span-start notifications for real-time UI.

Span enrichment (operate on the **active OTel span**):
    - ``log_content``: store bytes and attach a content-addressed reference.
    - ``use_artifact``: mark that the span consumed a W&B artifact.
    - ``use_object``: mark that the span consumed a Weave object.

Examples:
    >>> from weave.otel import setup_tracing, SystemPromptInjector, log_content
    >>> provider = setup_tracing(
    ...     service_name="my-agent",
    ...     project="demo",
    ...     genai_endpoint="http://localhost:6345/otel/v1/genai/traces",
    ...     processors=[SystemPromptInjector({"Bot": "You are helpful."})],
    ... )
    >>> # Inside any OTel-traced tool:
    >>> log_content(image_bytes, key="poster", media_type="image/png")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def __getattr__(name: str) -> Any:
    if name == "LiveSpanProcessor":
        from weave.otel.live_processor import LiveSpanProcessor

        return LiveSpanProcessor
    if name in {"SystemPromptInjector", "setup_tracing"}:
        from weave.otel import setup as _setup

        return getattr(_setup, name)
    if name in {
        "ToolDefinitionsInjector",
        "ReasoningTokenExtractor",
        "patch_openai_reasoning",
        "unpatch_openai_reasoning",
    }:
        from weave.otel import processors as _proc

        return getattr(_proc, name)
    if name in {"patch_openai_compaction", "unpatch_openai_compaction"}:
        from weave.otel import compaction as _comp

        return getattr(_comp, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

_CONTENT_REFS_ATTR = "weave.content_refs"
_ARTIFACT_REFS_ATTR = "weave.artifact_refs"
_OBJECT_REFS_ATTR = "weave.object_refs"


def _get_active_span() -> Any:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            return span
    except ImportError:
        pass
    return None


def _append_to_span_attr(span: Any, attr_name: str, entry: dict) -> None:
    existing_raw = span.attributes.get(attr_name) if hasattr(span, "attributes") else None
    existing: list = []
    if existing_raw:
        try:
            existing = json.loads(existing_raw)
        except (json.JSONDecodeError, TypeError):
            existing = []
    existing.append(entry)
    span.set_attribute(attr_name, json.dumps(existing))


def log_content(
    data: bytes | str | Path | Any,
    *,
    key: str | None = None,
    media_type: str | None = None,
    role: str = "output",
) -> str | None:
    """Store content and attach a reference to the active OTel span.

    Args:
        data: Raw bytes, file path, PIL Image, or readable file object.
        key: Human-readable label (e.g. ``"flier_draft_candidate"``).
            Integrations use names like ``"generated_image"`` or ``"tts_audio"``.
        media_type: MIME type (e.g. ``"image/png"``). Auto-detected if omitted.
        role: One of ``"input"``, ``"output"``, or ``"context"``.

    Returns:
        The content-addressed digest, or ``None`` if the operation was skipped.

    Examples:
        >>> weave.otel.log_content(png_bytes, key="chart", media_type="image/png")
        'abc123...'
    """
    span = _get_active_span()
    if span is None:
        logger.debug("log_content: no active recording span, skipping")
        return None

    from weave.otel._storage import (
        detect_media_type,
        resolve_content_bytes,
        resolve_project_id,
        upload_content,
    )

    content_bytes, filename = resolve_content_bytes(data)
    if not media_type:
        media_type = detect_media_type(content_bytes, filename)

    project_id = resolve_project_id()
    if not project_id:
        logger.debug("log_content: could not resolve project_id, skipping upload")
        return None

    digest = upload_content(content_bytes, project_id)

    ref_entry = {
        "digest": digest,
        "media_type": media_type,
        "role": role,
        "size_bytes": len(content_bytes),
    }
    if key:
        ref_entry["key"] = key

    _append_to_span_attr(span, _CONTENT_REFS_ATTR, ref_entry)

    return digest


def use_artifact(
    name: str,
    *,
    key: str | None = None,
    alias: str | None = None,
) -> None:
    """Mark that the active span consumed a W&B artifact.

    Args:
        name: Artifact name with optional version (e.g. ``"my-dataset:v3"``).
        key: Human-readable label (e.g. ``"training_data"``).
        alias: Optional alias (e.g. ``"latest"``).

    Examples:
        >>> weave.otel.use_artifact("my-dataset:v3", key="eval_data")
    """
    span = _get_active_span()
    if span is None:
        return

    entry: dict[str, str] = {"name": name}
    if key:
        entry["key"] = key
    if alias:
        entry["alias"] = alias

    _append_to_span_attr(span, _ARTIFACT_REFS_ATTR, entry)


def use_object(
    ref: str,
    *,
    key: str | None = None,
) -> None:
    """Mark that the active span consumed a Weave object.

    Args:
        ref: Object reference (e.g. ``"my-prompt:abc123"`` or a ``weave://`` URI).
        key: Human-readable label (e.g. ``"system_prompt"``).

    Examples:
        >>> weave.otel.use_object("my-prompt:latest", key="system_prompt")
    """
    span = _get_active_span()
    if span is None:
        return

    entry: dict[str, str] = {"ref": ref}
    if key:
        entry["key"] = key

    _append_to_span_attr(span, _OBJECT_REFS_ATTR, entry)
