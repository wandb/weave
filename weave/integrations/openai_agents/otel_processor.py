"""OTel-emitting tracing processor for OpenAI Agents.

Emits one OpenTelemetry span per OpenAI Agents span using GenAI semantic
conventions where they apply (``invoke_agent`` for Agent/Task/Turn/SubAgent,
``execute_tool`` for Function). Span types without a clean semconv mapping
(Handoff, Guardrail, Transcription, Speech, SpeechGroup, MCPListTools,
Custom) emit with a descriptive span name and ``weave.openai_agents.*``
attributes.

``ResponseSpanData`` and ``GenerationSpanData`` are intentionally skipped:
the openai SDK has its own (forthcoming) OTel patcher that emits ``chat``
spans for those API calls, and we don't want to dual-log. Until that lands,
LLM calls show up only in the Calls tab via the unchanged ``openai_sdk``
patch; the Agents tab shows agent invocations, tools, handoffs etc. without
the chat spans nested inside.

OpenAI trace/span IDs are preserved as ``weave.openai_agents.trace_id`` /
``weave.openai_agents.span_id`` attributes so they remain cross-referenceable
with the OpenAI Agents SDK's own logs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from agents.tracing import (
    AgentSpanData,
    CustomSpanData,
    FunctionSpanData,
    GenerationSpanData,
    GuardrailSpanData,
    HandoffSpanData,
    MCPListToolsSpanData,
    ResponseSpanData,
    Span,
    SpeechGroupSpanData,
    SpeechSpanData,
    Trace,
    TracingProcessor,
    TranscriptionSpanData,
)

from weave.integrations.openai_agents.openai_agents import (
    _call_name,
    _is_task_span_data,
    _is_turn_span_data,
)
from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
)

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.trace import StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)

_TRACER_NAME = "weave.openai_agents"
_WEAVE_ATTR_PREFIX = "weave.openai_agents"


def _iso_to_ns(value: str | None) -> int | None:
    """Convert an OpenAI Agents ISO 8601 timestamp to nanoseconds since epoch."""
    if not value:
        return None
    return int(datetime.fromisoformat(value).timestamp() * 1_000_000_000)


def _conversation_id_for_trace(trace: Trace) -> str:
    """Resolve ``gen_ai.conversation.id`` for a trace: group_id, else trace_id."""
    return getattr(trace, "group_id", None) or trace.trace_id


def _set_attrs(span: Any, attrs: dict[str, Any]) -> None:
    """Set every (non-None, non-empty-string) attribute on the OTel span."""
    for key, val in attrs.items():
        if val is None:
            continue
        if isinstance(val, str) and not val:
            continue
        span.set_attribute(key, val)


def _agent_attrs(span: Span[AgentSpanData], conversation_id: str) -> dict[str, Any]:
    attrs = invoke_agent_attributes(
        agent_name=span.span_data.name or "",
        conversation_id=conversation_id,
    )
    if tools := getattr(span.span_data, "tools", None):
        attrs[f"{_WEAVE_ATTR_PREFIX}.agent.tools"] = list(tools)
    if handoffs := getattr(span.span_data, "handoffs", None):
        attrs[f"{_WEAVE_ATTR_PREFIX}.agent.handoffs"] = list(handoffs)
    if output_type := getattr(span.span_data, "output_type", None):
        attrs[f"{_WEAVE_ATTR_PREFIX}.agent.output_type"] = output_type
    return attrs


def _task_attrs(span: Span, conversation_id: str) -> dict[str, Any]:
    name = getattr(span.span_data, "name", None) or ""
    attrs = invoke_agent_attributes(
        agent_name=name,
        conversation_id=conversation_id,
    )
    if isinstance(meta := getattr(span.span_data, "metadata", None), dict):
        for k, v in meta.items():
            if v is None:
                continue
            attrs[f"{_WEAVE_ATTR_PREFIX}.task.metadata.{k}"] = v
    return attrs


def _turn_attrs(span: Span, conversation_id: str) -> dict[str, Any]:
    agent_name = getattr(span.span_data, "agent_name", None) or ""
    attrs = invoke_agent_attributes(
        agent_name=agent_name,
        conversation_id=conversation_id,
    )
    if (turn := getattr(span.span_data, "turn", None)) is not None:
        attrs[f"{_WEAVE_ATTR_PREFIX}.turn.number"] = turn
    if isinstance(meta := getattr(span.span_data, "metadata", None), dict):
        for k, v in meta.items():
            if v is None:
                continue
            attrs[f"{_WEAVE_ATTR_PREFIX}.turn.metadata.{k}"] = v
    return attrs


def _function_attrs(
    span: Span[FunctionSpanData], conversation_id: str
) -> dict[str, Any]:
    return execute_tool_attributes(
        tool_name=span.span_data.name or "",
        conversation_id=conversation_id,
        tool_call_arguments=span.span_data.input or "",
        tool_call_result=span.span_data.output or "",
    )


def _handoff_attrs(span: Span[HandoffSpanData]) -> dict[str, Any]:
    return {
        f"{_WEAVE_ATTR_PREFIX}.handoff.from_agent": span.span_data.from_agent or "",
        f"{_WEAVE_ATTR_PREFIX}.handoff.to_agent": span.span_data.to_agent or "",
    }


def _guardrail_attrs(span: Span[GuardrailSpanData]) -> dict[str, Any]:
    return {
        f"{_WEAVE_ATTR_PREFIX}.guardrail.name": span.span_data.name or "",
        f"{_WEAVE_ATTR_PREFIX}.guardrail.triggered": bool(span.span_data.triggered),
    }


def _transcription_attrs(span: Span[TranscriptionSpanData]) -> dict[str, Any]:
    sd = span.span_data
    return {
        f"{_WEAVE_ATTR_PREFIX}.transcription.model": getattr(sd, "model", "") or "",
        f"{_WEAVE_ATTR_PREFIX}.transcription.input": getattr(sd, "input", "") or "",
        f"{_WEAVE_ATTR_PREFIX}.transcription.input_format": (
            getattr(sd, "input_format", "") or ""
        ),
        f"{_WEAVE_ATTR_PREFIX}.transcription.output": getattr(sd, "output", "") or "",
    }


def _speech_attrs(span: Span[SpeechSpanData]) -> dict[str, Any]:
    sd = span.span_data
    return {
        f"{_WEAVE_ATTR_PREFIX}.speech.model": getattr(sd, "model", "") or "",
        f"{_WEAVE_ATTR_PREFIX}.speech.input": getattr(sd, "input", "") or "",
        f"{_WEAVE_ATTR_PREFIX}.speech.output": getattr(sd, "output", "") or "",
        f"{_WEAVE_ATTR_PREFIX}.speech.output_format": (
            getattr(sd, "output_format", "") or ""
        ),
    }


def _speech_group_attrs(span: Span[SpeechGroupSpanData]) -> dict[str, Any]:
    return {
        f"{_WEAVE_ATTR_PREFIX}.speech_group.input": (
            getattr(span.span_data, "input", "") or ""
        ),
    }


def _mcp_list_tools_attrs(span: Span[MCPListToolsSpanData]) -> dict[str, Any]:
    return {
        f"{_WEAVE_ATTR_PREFIX}.mcp.server": getattr(span.span_data, "server", "") or "",
        f"{_WEAVE_ATTR_PREFIX}.mcp.result": list(
            getattr(span.span_data, "result", []) or []
        ),
    }


def _custom_attrs(span: Span[CustomSpanData]) -> dict[str, Any]:
    """Surface custom span data under ``weave.openai_agents.custom.*``."""
    out: dict[str, Any] = {}
    data = getattr(span.span_data, "data", None) or {}
    for k, v in data.items():
        if v is None:
            continue
        out[f"{_WEAVE_ATTR_PREFIX}.custom.{k}"] = v
    return out


def _attrs_for_span(span: Span, conversation_id: str) -> dict[str, Any]:
    """Pick the attribute builder for a span type and produce the final attrs dict."""
    sd = span.span_data
    if isinstance(sd, AgentSpanData):
        return _agent_attrs(span, conversation_id)
    if _is_task_span_data(sd):
        return _task_attrs(span, conversation_id)
    if _is_turn_span_data(sd):
        return _turn_attrs(span, conversation_id)
    if isinstance(sd, FunctionSpanData):
        return _function_attrs(span, conversation_id)
    if isinstance(sd, HandoffSpanData):
        return _handoff_attrs(span)
    if isinstance(sd, GuardrailSpanData):
        return _guardrail_attrs(span)
    if isinstance(sd, TranscriptionSpanData):
        return _transcription_attrs(span)
    if isinstance(sd, SpeechSpanData):
        return _speech_attrs(span)
    if isinstance(sd, SpeechGroupSpanData):
        return _speech_group_attrs(span)
    if isinstance(sd, MCPListToolsSpanData):
        return _mcp_list_tools_attrs(span)
    if isinstance(sd, CustomSpanData):
        return _custom_attrs(span)
    return {}


class WeaveOtelTracingProcessor(TracingProcessor):  # pyright: ignore[reportGeneralTypeIssues]
    """A TracingProcessor that emits OTel GenAI spans for OpenAI Agents traces.

    One OTel span per OpenAI span, mapped to GenAI semconv where applicable.
    Maintains parent linkage via internal dicts (the openai-agents SDK passes
    parent_id strings; OTel parent-child propagation is reconstructed by
    setting ``context=`` on ``Tracer.start_span``).

    Skips ``ResponseSpanData`` and ``GenerationSpanData`` to avoid dual-logging
    with the openai SDK's (future) OTel patcher.
    """

    def __init__(self) -> None:
        self._trace_root_spans: dict[str, Any] = {}
        self._span_otel: dict[str, Any] = {}
        self._conversation_ids: dict[str, str] = {}

    def _tracer(self) -> Any:
        return otel_trace.get_tracer(_TRACER_NAME)

    def _parent_context(self, span: Span) -> Any:
        """Build an OTel context bound to this span's parent.

        Returns ``None`` if no parent OTel span exists (the new span becomes a
        new trace root in OTel — should be rare, only if on_trace_start was
        skipped).
        """
        parent_id = getattr(span, "parent_id", None)
        parent_otel = (
            self._span_otel.get(parent_id) if parent_id else None
        ) or self._trace_root_spans.get(span.trace_id)
        if parent_otel is None:
            return None
        return otel_trace.set_span_in_context(parent_otel)

    def on_trace_start(self, trace: Trace) -> None:
        if not _OTEL_AVAILABLE:
            return
        conversation_id = _conversation_id_for_trace(trace)
        self._conversation_ids[trace.trace_id] = conversation_id

        attrs = invoke_agent_attributes(
            agent_name=trace.name or "",
            conversation_id=conversation_id,
            conversation_name=trace.name or "",
        )
        attrs[f"{_WEAVE_ATTR_PREFIX}.trace_id"] = trace.trace_id

        root = self._tracer().start_span(
            f"invoke_agent {trace.name}" if trace.name else "invoke_agent",
        )
        _set_attrs(root, attrs)
        self._trace_root_spans[trace.trace_id] = root

    def on_trace_end(self, trace: Trace) -> None:
        if not _OTEL_AVAILABLE:
            return
        root = self._trace_root_spans.pop(trace.trace_id, None)
        if root is not None and root.is_recording():
            root.end()
        self._conversation_ids.pop(trace.trace_id, None)

    def on_span_start(self, span: Span) -> None:
        if not _OTEL_AVAILABLE:
            return
        # Skip Response/Generation entirely — openai SDK's OTel patcher is
        # the source of truth for chat spans (see module docstring).
        if isinstance(span.span_data, (ResponseSpanData, GenerationSpanData)):
            return
        if span.trace_id not in self._trace_root_spans:
            return

        parent_ctx = self._parent_context(span)
        if parent_ctx is None:
            return

        otel_span = self._tracer().start_span(
            _otel_span_name(span),
            context=parent_ctx,
            start_time=_iso_to_ns(span.started_at),
        )
        otel_span.set_attribute(f"{_WEAVE_ATTR_PREFIX}.span_id", span.span_id)
        otel_span.set_attribute(
            f"{_WEAVE_ATTR_PREFIX}.trace_id", span.trace_id
        )
        self._span_otel[span.span_id] = otel_span

    def on_span_end(self, span: Span) -> None:
        if not _OTEL_AVAILABLE:
            return
        if isinstance(span.span_data, (ResponseSpanData, GenerationSpanData)):
            return
        otel_span = self._span_otel.pop(span.span_id, None)
        if otel_span is None:
            return

        conversation_id = self._conversation_ids.get(span.trace_id, "")
        attrs = _attrs_for_span(span, conversation_id)
        _set_attrs(otel_span, attrs)

        if span.error:
            otel_span.set_status(
                StatusCode.ERROR, str(span.error.get("message", "")) or ""
            )
            if data := span.error.get("data"):
                otel_span.set_attribute(
                    f"{_WEAVE_ATTR_PREFIX}.error.data", str(data)
                )

        end_ns = _iso_to_ns(span.ended_at)
        if end_ns is not None:
            otel_span.end(end_time=end_ns)
        else:
            otel_span.end()

    def shutdown(self) -> None:
        """End any open spans so they don't leak on interpreter exit."""
        self._end_open_spans()

    def force_flush(self) -> None:
        """End any open spans; the BatchSpanProcessor handles export flushing."""
        self._end_open_spans()

    def _end_open_spans(self) -> None:
        if not _OTEL_AVAILABLE:
            return
        for otel_span in self._span_otel.values():
            if otel_span.is_recording():
                otel_span.end()
        for root in self._trace_root_spans.values():
            if root.is_recording():
                root.end()
        self._span_otel.clear()
        self._trace_root_spans.clear()
        self._conversation_ids.clear()


def _otel_span_name(span: Span) -> str:
    """Pick a descriptive OTel span name based on the span type.

    Semconv-mapped types use the conventional ``<operation> <subject>`` shape
    (e.g. ``invoke_agent Triage``, ``execute_tool get_weather``). Custom types
    use ``<kind> <subject>`` for readability in trace viewers.
    """
    sd = span.span_data
    name = _call_name(span)
    if isinstance(sd, AgentSpanData) or _is_task_span_data(sd) or _is_turn_span_data(sd):
        return f"invoke_agent {name}"
    if isinstance(sd, FunctionSpanData):
        return f"execute_tool {name}"
    if isinstance(sd, HandoffSpanData):
        from_a = sd.from_agent or "?"
        to_a = sd.to_agent or "?"
        return f"handoff {from_a} -> {to_a}"
    if isinstance(sd, GuardrailSpanData):
        return f"guardrail {name}"
    if isinstance(sd, TranscriptionSpanData):
        return f"transcription {name}"
    if isinstance(sd, SpeechSpanData):
        return f"speech {name}"
    if isinstance(sd, SpeechGroupSpanData):
        return "speech_group"
    if isinstance(sd, MCPListToolsSpanData):
        return f"mcp_list_tools {name}"
    if isinstance(sd, CustomSpanData):
        return name
    return name
