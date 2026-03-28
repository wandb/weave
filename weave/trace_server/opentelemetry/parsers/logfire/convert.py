"""Convert logfire-scoped OTEL spans to Weave call pairs.

For every logfire.* span the event_parser is used to extract structured
inputs / output / usage / model info rather than the legacy attribute-key
priority approach.

Additionally, when a single span contains *embedded* tool-call round-trips
(i.e. ``gen_ai.assistant.message`` events with ``tool_calls`` + matching
``gen_ai.tool.message`` result events) synthetic child calls are created so
that each tool invocation appears as its own Weave op call.  This pattern
is emitted by ``logfire.instrument_openai_agents()`` and similar wrappers
that capture a full agent turn inside one span.

The ``logfire.msg`` span attribute is used as the human-readable display name
wherever it is available.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.opentelemetry.event_parser import (
    EventType,
    OtelEvent,
    TokenUsage,
    _try_json,
    span_to_event,
)
from weave.trace_server.opentelemetry.python_spans import Span

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synthetic_span_id(parent_span_id: str, tool_call_id: str) -> str:
    """Return a deterministic 16-char hex ID for a synthetic tool-call span."""
    raw = f"{parent_span_id}::{tool_call_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _inputs_dict(event: OtelEvent) -> dict[str, Any]:
    """Convert OtelEvent.inputs to the dict form required by StartedCallSchemaForInsert."""
    if isinstance(event.inputs, list):
        return {"messages": event.inputs}
    return dict(event.inputs) if event.inputs else {}


def _build_summary(event: OtelEvent) -> tsi.SummaryInsertMap:
    usage: tsi.LLMUsageSchema = {}
    if event.usage:
        u: TokenUsage = event.usage
        if u.input_tokens is not None:
            usage["input_tokens"] = u.input_tokens
        if u.output_tokens is not None:
            usage["output_tokens"] = u.output_tokens
        if u.total_tokens is not None:
            usage["total_tokens"] = u.total_tokens

    summary: tsi.SummaryInsertMap = {}
    if usage:
        key = event.model or "usage"
        summary["usage"] = {key: usage}
    return summary


def _dt(iso: str | None) -> datetime:
    if iso:
        return datetime.fromisoformat(iso)
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Core call-pair builder
# ---------------------------------------------------------------------------


def _event_to_call_pair(
    event: OtelEvent,
    project_id: str,
    op_name: str,
    display_name: str | None,
    wb_user_id: str | None = None,
    wb_run_id: str | None = None,
) -> tuple[tsi.StartedCallSchemaForInsert, tsi.EndedCallSchemaForInsert]:
    started_at = _dt(event.started_at)
    ended_at = _dt(event.ended_at)
    latency_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))

    status = (
        tsi.TraceStatus.ERROR if event.status == "error" else tsi.TraceStatus.SUCCESS
    )
    weave_summary = tsi.WeaveSummarySchema(
        status=status,
        latency_ms=latency_ms,
        trace_name=display_name or op_name,
    )
    summary = _build_summary(event)
    summary["weave"] = weave_summary  # type: ignore[typeddict-unknown-key]

    start_call = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=event.id,
        op_name=op_name,
        display_name=display_name,
        trace_id=event.trace_id,
        parent_id=event.parent_id,
        started_at=started_at,
        attributes={},
        inputs=_inputs_dict(event),
        wb_user_id=wb_user_id,
        wb_run_id=wb_run_id,
    )

    end_call = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=event.id,
        ended_at=ended_at,
        exception=event.error,
        output=event.output,
        summary=summary,
    )

    return start_call, end_call


# ---------------------------------------------------------------------------
# Embedded tool-call extraction from span events
# ---------------------------------------------------------------------------

_CallPair = tuple[tsi.StartedCallSchemaForInsert, tsi.EndedCallSchemaForInsert]


def _extract_embedded_tool_calls(span: Span) -> list[dict[str, Any]]:
    """Extract tool-call invocations and their results from span events.

    Looks for ``gen_ai.assistant.message`` events that carry ``tool_calls``
    and ``gen_ai.tool.message`` events that carry the corresponding results.

    Returns a list of dicts with keys ``id``, ``name``, ``arguments``,
    ``result``.  Only returns non-empty when *both* invocations and results
    are found — a bare tool-call list with no results means the tool ran
    outside logfire's scope and we should not manufacture phantom results.
    """
    tool_calls: dict[str, dict[str, Any]] = {}  # call_id → {name, arguments}
    tool_results: dict[str, Any] = {}           # call_id → result

    for evt in span.events:
        attrs = evt.attributes or {}

        if evt.name == "gen_ai.assistant.message":
            body_raw = attrs.get("event_body")
            body = _try_json(body_raw) if body_raw is not None else attrs
            if not isinstance(body, dict):
                continue
            tcs = body.get("tool_calls")
            if not tcs or not isinstance(tcs, list):
                continue
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                tc_id = tc.get("id", "")
                # Accept both flat {id, name, arguments} and OpenAI-style
                # {id, function: {name, arguments}} shapes.
                func = tc.get("function") or {}
                name = tc.get("name") or func.get("name", "")
                arguments = tc.get("arguments") or func.get("arguments")
                if isinstance(arguments, str):
                    arguments = _try_json(arguments)
                if tc_id:
                    tool_calls[tc_id] = {"name": name, "arguments": arguments}

        elif evt.name == "gen_ai.tool.message":
            body_raw = attrs.get("event_body")
            body = _try_json(body_raw) if body_raw is not None else attrs
            if isinstance(body, dict):
                tc_id = (
                    body.get("id")
                    or body.get("tool_call_id")
                    or attrs.get("id", "")
                )
                content = body.get("content", "")
            else:
                tc_id = attrs.get("id") or attrs.get("tool_call_id", "")
                content = attrs.get("content", "")
            if isinstance(content, str):
                content = _try_json(content)
            if tc_id:
                tool_results[tc_id] = content

    # Only emit synthetic calls when we have both sides of the exchange.
    if not tool_calls or not tool_results:
        return []

    return [
        {
            "id": tc_id,
            "name": tc_data["name"],
            "arguments": tc_data["arguments"],
            "result": tool_results.get(tc_id),
        }
        for tc_id, tc_data in tool_calls.items()
    ]


def _synthetic_tool_call_pairs(
    embedded: list[dict[str, Any]],
    parent_event: OtelEvent,
    project_id: str,
    wb_user_id: str | None,
    wb_run_id: str | None,
) -> list[_CallPair]:
    """Build (StartCall, EndCall) pairs for embedded tool calls."""
    pairs: list[_CallPair] = []
    started_at = _dt(parent_event.started_at)
    ended_at = _dt(parent_event.ended_at)

    for tc in embedded:
        synthetic_id = _synthetic_span_id(parent_event.id, tc["id"])
        name = tc["name"] or "tool_call"
        args = tc["arguments"]
        inputs: dict[str, Any] = args if isinstance(args, dict) else {"arguments": args}

        weave_summary = tsi.WeaveSummarySchema(
            status=tsi.TraceStatus.SUCCESS,
            latency_ms=0,
            trace_name=name,
        )

        start_call = tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=synthetic_id,
            op_name=name,
            display_name=name,
            trace_id=parent_event.trace_id,
            parent_id=parent_event.id,
            started_at=started_at,
            attributes={},
            inputs=inputs,
            wb_user_id=wb_user_id,
            wb_run_id=wb_run_id,
        )

        end_call = tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=synthetic_id,
            ended_at=ended_at,
            output=tc["result"],
            summary={"weave": weave_summary},
        )

        pairs.append((start_call, end_call))

    return pairs


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


# Span names that are internal pydantic validation noise emitted by pydantic-ai
_SKIP_PREFIXES = ("pydantic.",)


def span_to_calls(
    span: Span,
    project_id: str,
    known_span_ids: set[str],
    wb_user_id: str | None = None,
    wb_run_id: str | None = None,
) -> list[_CallPair]:
    """Convert one logfire-scoped span to one or more Weave call pairs.

    Parameters
    ----------
    span:
        The parsed OTEL span (already converted from protobuf).
    project_id:
        Target Weave project.
    known_span_ids:
        All span IDs present in the current import batch; used to decide
        whether a span's parent_id points within the batch or is external
        (external → treated as root).
    wb_user_id / wb_run_id:
        Forwarded from the import request.

    Returns
    -------
    list of (StartedCallSchemaForInsert, EndedCallSchemaForInsert) pairs.
    One pair per real span, plus zero or more synthetic tool-call children
    when the span contains embedded tool-call round-trips in its events.
    """
    # Skip pydantic-internal validation noise
    if any(span.name.startswith(p) for p in _SKIP_PREFIXES):
        return []

    event = span_to_event(span, known_span_ids)

    attrs = span.attributes
    display_name: str = attrs.get("logfire.msg") or span.name

    main_pair = _event_to_call_pair(
        event,
        project_id,
        op_name=span.name,
        display_name=display_name,
        wb_user_id=wb_user_id,
        wb_run_id=wb_run_id,
    )

    pairs: list[_CallPair] = [main_pair]

    # Create synthetic child calls for embedded tool-call round-trips.
    # This surfaces tool invocations as first-class Weave calls even when
    # the framework records them only as span events rather than child spans.
    if event.type == EventType.LLM:
        embedded = _extract_embedded_tool_calls(span)
        if embedded:
            pairs.extend(
                _synthetic_tool_call_pairs(
                    embedded, event, project_id, wb_user_id, wb_run_id
                )
            )

    return pairs
