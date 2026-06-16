"""OTel-emitting tracing processor for OpenAI Agents.

Emits one OpenTelemetry span per OpenAI Agents span using GenAI semantic
conventions where they apply:

- ``invoke_agent`` for AgentSpan (the real agent instance). Each AgentSpan
  triggers an ``agent_start`` event in the timeline so handoff / multi-agent
  flows show which agent acted when.
- ``chat`` for ResponseSpan / GenerationSpan, extracted directly from the
  ``ResponseSpanData.response`` openai object — no separate openai patcher.
- ``execute_tool`` for Function.

TaskSpan and TurnSpan are emitted as *structural* spans (no
``gen_ai.operation.name``):

- TaskSpan: wraps the Runner.run workflow, not an agent invocation. Emitting
  invoke_agent here would surface every Runner.run as a duplicate agent
  event alongside the AgentSpan it contains.
- TurnSpan: one loop iteration within an agent. Emitting invoke_agent here
  would multiply the agent_start events (one per turn) for a single agent.

Span types without a clean semconv mapping (Handoff, Guardrail, Transcription,
Speech, SpeechGroup, MCPListTools, Custom) emit with a descriptive span name
and ``weave.openai_agents.*`` attributes.

The system under observation is the OpenAI Agents SDK itself. We don't
instrument raw ``openai.*`` calls separately — when the Agents SDK invokes
the LLM, the SDK's own ``ResponseSpanData`` exposes the request, response,
and usage data, which we lift into the GenAI chat span attributes. Direct
``openai.*`` calls outside of an agent run are out of scope for this
integration (use the calls-mode ``patch_openai`` for those).

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
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.trace import StatusCode

from weave.integrations.openai_agents.openai_agents import (
    OPENAI_AGENTS_INTEGRATION,
    _call_name,
    _is_task_span_data,
    _is_turn_span_data,
)
from weave.session.adapters.openai import (
    message_from_openai_responses_input,
    reasoning_from_openai_responses,
    usage_from_openai_responses,
)
from weave.session.agent_context import resolve_agent_name
from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)
from weave.session.types import Message, Reasoning, Usage

logger = logging.getLogger(__name__)

_TRACER_NAME = "weave.openai_agents"
_WEAVE_ATTR_PREFIX = "weave.openai_agents"
_PROVIDER_NAME = "openai"
_DEFAULT_CHAT_OUTPUT_TYPE = "text"
_WEAVE_ISSUES_URL = "https://github.com/wandb/weave/issues/"

# Span-data subtypes we've already warned about in this process. Used by
# ``_attrs_for_span`` to surface (once) any SpanData class the SDK starts
# emitting that we don't have a handler for, without flooding the log.
_warned_unhandled_span_types: set[type] = set()

# Keys we extract from ``GenerationSpanData.model_config`` into the equivalent
# ``llm_attributes`` request_* kwargs. The map keeps the wire shape (raw openai
# request body keys) → the Session SDK kwarg name in one place.
_GENERATION_MODEL_CONFIG_KEYS = {
    "temperature": "request_temperature",
    "top_p": "request_top_p",
    "frequency_penalty": "request_frequency_penalty",
    "presence_penalty": "request_presence_penalty",
    "max_tokens": "request_max_tokens",
    "seed": "request_seed",
    "stop": "request_stop_sequences",
    "n": "request_choice_count",
}


def _iso_to_ns(value: str | None) -> int | None:
    """Convert an OpenAI Agents ISO 8601 timestamp to nanoseconds since epoch."""
    if not value:
        return None
    return int(datetime.fromisoformat(value).timestamp() * 1_000_000_000)


def _conversation_id_for_trace(trace: Trace) -> str:
    """Resolve ``gen_ai.conversation.id`` for a trace: group_id, else trace_id."""
    return trace.group_id or trace.trace_id


def _set_attrs(span: Any, attrs: dict[str, Any]) -> None:
    """Set every (non-None, non-empty-string) attribute on the OTel span."""
    for key, val in attrs.items():
        if val is None:
            continue
        if isinstance(val, str) and not val:
            continue
        span.set_attribute(key, val)


def _agent_attrs(span: Span[AgentSpanData], conversation_id: str) -> dict[str, Any]:
    """``invoke_agent`` semconv attrs for an AgentSpan.

    AgentSpan IS an agent invocation, so it carries ``gen_ai.operation.name``.
    The Agents-tab events panel renders each invoke_agent as an ``agent_start``
    timeline event so the user can see which agent acted when — important for
    handoff / multi-agent flows where the timeline would otherwise be empty
    between user message and the final assistant reply.
    """
    sd = span.span_data
    attrs = invoke_agent_attributes(
        # An explicit ambient override wins over the SDK-native agent name.
        agent_name=resolve_agent_name(sd.name or ""),
        conversation_id=conversation_id,
        provider_name=_PROVIDER_NAME,
    )
    if sd.tools:
        attrs[f"{_WEAVE_ATTR_PREFIX}.agent.tools"] = list(sd.tools)
    if sd.handoffs:
        attrs[f"{_WEAVE_ATTR_PREFIX}.agent.handoffs"] = list(sd.handoffs)
    if sd.output_type:
        attrs[f"{_WEAVE_ATTR_PREFIX}.agent.output_type"] = sd.output_type
    return attrs


def _task_attrs(span: Span, conversation_id: str) -> dict[str, Any]:
    """Structural attrs for a TaskSpan (one per ``Runner.run``).

    Intentionally NOT semconv ``invoke_agent``: the Task wraps a workflow,
    not an agent invocation. Treating it as an agent invocation causes the
    Agents-tab events panel to render every Runner.run as a redundant
    "sub-agent" event alongside the real ``AgentSpan``.
    """
    sd = span.span_data
    attrs: dict[str, Any] = {
        f"{_WEAVE_ATTR_PREFIX}.task.workflow_name": sd.name or "",
    }
    if conversation_id:
        attrs["gen_ai.conversation.id"] = conversation_id
    if isinstance(sd.metadata, dict):
        for k, v in sd.metadata.items():
            if v is None:
                continue
            attrs[f"{_WEAVE_ATTR_PREFIX}.task.metadata.{k}"] = v
    return attrs


def _turn_attrs(span: Span, conversation_id: str) -> dict[str, Any]:
    """Structural attrs for a TurnSpan (one loop iteration within an agent).

    Intentionally NOT semconv ``invoke_agent`` — a turn is a step within an
    agent invocation, not a separate agent.
    """
    sd = span.span_data
    attrs: dict[str, Any] = {
        f"{_WEAVE_ATTR_PREFIX}.turn.agent_name": sd.agent_name or "",
    }
    if conversation_id:
        attrs["gen_ai.conversation.id"] = conversation_id
    if sd.turn is not None:
        attrs[f"{_WEAVE_ATTR_PREFIX}.turn.number"] = sd.turn
    if isinstance(sd.metadata, dict):
        for k, v in sd.metadata.items():
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


def _response_chat_attrs(
    span: Span[ResponseSpanData], conversation_id: str
) -> dict[str, Any]:
    """Build ``chat`` semconv attrs from an OpenAI Responses-API span.

    Pulls input/output messages, usage, reasoning, model, and response id
    directly off ``ResponseSpanData`` — the Agents SDK already serializes the
    full request/response on the span, so there's nothing to do at the openai
    HTTP boundary.
    """
    sd = span.span_data
    input_messages: list[Message] = []
    media_attachments: list[Any] = []
    if isinstance(sd.input, str):
        input_messages = [Message(role="user", content=sd.input)]
    elif isinstance(sd.input, list):
        input_messages, media_attachments = message_from_openai_responses_input(
            list(sd.input)
        )

    output_messages: list[Message] = []
    reasoning: Reasoning | None = None
    model = ""
    response_id = ""
    response_model = ""
    usage = Usage()
    finish_reasons: list[str] = []
    response = sd.response
    if response is not None:
        model = response.model or ""
        response_id = response.id or ""
        response_model = response.model or ""
        usage = usage_from_openai_responses(response)
        output_items = [
            item.model_dump(exclude_none=True) for item in (response.output or [])
        ]
        output_messages, _ = message_from_openai_responses_input(output_items)
        for item in output_items:
            if item.get("type") == "reasoning":
                reasoning = reasoning_from_openai_responses(item)
                break
        for item in output_items:
            finish = item.get("finish_reason")
            if isinstance(finish, str) and finish:
                finish_reasons.append(finish)

    return llm_attributes(
        model=model,
        provider_name=_PROVIDER_NAME,
        conversation_id=conversation_id,
        input_messages=input_messages,
        output_messages=output_messages,
        media_attachments=media_attachments,
        usage=usage,
        reasoning=reasoning,
        response_id=response_id,
        response_model=response_model,
        finish_reasons=finish_reasons or None,
        output_type=_DEFAULT_CHAT_OUTPUT_TYPE,
    )


def _generation_chat_attrs(
    span: Span[GenerationSpanData], conversation_id: str
) -> dict[str, Any]:
    """Build ``chat`` semconv attrs from a (legacy chat-completions) generation span."""
    sd = span.span_data
    input_messages = _chat_completion_messages(sd.input, default_role="user")
    output_messages = _chat_completion_messages(sd.output, default_role="assistant")

    usage = Usage()
    if isinstance(sd.usage, dict):
        input_tokens = (
            sd.usage.get("input_tokens") or sd.usage.get("prompt_tokens") or 0
        )
        output_tokens = (
            sd.usage.get("output_tokens") or sd.usage.get("completion_tokens") or 0
        )
        usage = Usage(input_tokens=int(input_tokens), output_tokens=int(output_tokens))

    request_kwargs = _request_kwargs_from_model_config(sd.model_config)

    return llm_attributes(
        model=sd.model or "",
        provider_name=_PROVIDER_NAME,
        conversation_id=conversation_id,
        input_messages=input_messages,
        output_messages=output_messages,
        usage=usage,
        output_type=_DEFAULT_CHAT_OUTPUT_TYPE,
        **request_kwargs,
    )


def _request_kwargs_from_model_config(model_config: Any) -> dict[str, Any]:
    """Extract ``gen_ai.request.*`` kwargs from a GenerationSpanData model_config.

    Only the keys listed in ``_GENERATION_MODEL_CONFIG_KEYS`` are forwarded;
    everything else on ``model_config`` is ignored (the rest is openai-specific
    and doesn't map cleanly to GenAI semconv). Lists/strings for ``stop`` are
    normalized to a list — semconv wants ``stop_sequences`` as a list of strings.
    """
    if not isinstance(model_config, dict):
        return {}
    out: dict[str, Any] = {}
    for src_key, kwarg in _GENERATION_MODEL_CONFIG_KEYS.items():
        value = model_config.get(src_key)
        if value is None:
            continue
        if kwarg == "request_stop_sequences":
            if isinstance(value, str):
                value = [value]
            elif not isinstance(value, list):
                continue
        out[kwarg] = value
    return out


def _chat_completion_messages(raw: Any, *, default_role: str) -> list[Message]:
    """Convert an openai chat-completions message list to ``Message`` objects.

    GenerationSpanData carries the legacy ``[{"role": "...", "content": "..."}]``
    shape. ``content`` can be a string, ``None`` (e.g. assistant messages
    carrying tool_calls), or a multimodal block list. We keep the turn
    structure in all three cases — string content passes through; everything
    else surfaces as an empty-string message so the role/turn is preserved.
    The legacy path is rare in agent flows; ResponseSpanData covers the new
    API where multimodal content is preserved properly.
    """
    if not raw:
        return []
    messages: list[Message] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or default_role)
        content = entry.get("content")
        if isinstance(content, str):
            messages.append(Message(role=role, content=content))
        else:
            messages.append(Message(role=role, content=""))
    return messages


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
        f"{_WEAVE_ATTR_PREFIX}.transcription.model": sd.model or "",
        f"{_WEAVE_ATTR_PREFIX}.transcription.input": sd.input or "",
        f"{_WEAVE_ATTR_PREFIX}.transcription.input_format": sd.input_format or "",
        f"{_WEAVE_ATTR_PREFIX}.transcription.output": sd.output or "",
    }


def _speech_attrs(span: Span[SpeechSpanData]) -> dict[str, Any]:
    sd = span.span_data
    return {
        f"{_WEAVE_ATTR_PREFIX}.speech.model": sd.model or "",
        f"{_WEAVE_ATTR_PREFIX}.speech.input": sd.input or "",
        f"{_WEAVE_ATTR_PREFIX}.speech.output": sd.output or "",
        f"{_WEAVE_ATTR_PREFIX}.speech.output_format": sd.output_format or "",
    }


def _speech_group_attrs(span: Span[SpeechGroupSpanData]) -> dict[str, Any]:
    return {
        f"{_WEAVE_ATTR_PREFIX}.speech_group.input": span.span_data.input or "",
    }


def _mcp_list_tools_attrs(span: Span[MCPListToolsSpanData]) -> dict[str, Any]:
    sd = span.span_data
    return {
        f"{_WEAVE_ATTR_PREFIX}.mcp.server": sd.server or "",
        f"{_WEAVE_ATTR_PREFIX}.mcp.result": list(sd.result or []),
    }


def _custom_attrs(span: Span[CustomSpanData]) -> dict[str, Any]:
    """Surface custom span data under ``weave.openai_agents.custom.*``."""
    out: dict[str, Any] = {}
    for k, v in (span.span_data.data or {}).items():
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
    if isinstance(sd, ResponseSpanData):
        return _response_chat_attrs(span, conversation_id)
    if isinstance(sd, GenerationSpanData):
        return _generation_chat_attrs(span, conversation_id)
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

    # No handler matched. Most likely cause: a new SpanData subtype was
    # introduced by openai-agents that this processor doesn't know about yet.
    # Warn once per type so a future SDK bump surfaces the gap instead of
    # silently emitting attributeless spans.
    sd_type = type(sd)
    if sd_type not in _warned_unhandled_span_types:
        _warned_unhandled_span_types.add(sd_type)
        logger.warning(
            "No handler for span_data type %s.%s; spans of this type emit "
            "without GenAI semconv attributes. Please open an issue at %s so "
            "the Weave team can add support.",
            sd_type.__module__,
            sd_type.__name__,
            _WEAVE_ISSUES_URL,
        )
    return {}


class WeaveOtelTracingProcessor(TracingProcessor):  # pyright: ignore[reportGeneralTypeIssues]
    """A TracingProcessor that emits OTel GenAI spans for OpenAI Agents traces.

    One OTel span per OpenAI span, mapped to GenAI semconv where applicable.
    Maintains parent linkage via internal dicts (the openai-agents SDK passes
    parent_id strings; OTel parent-child propagation is reconstructed by
    setting ``context=`` on ``Tracer.start_span``).

    ``ResponseSpanData`` / ``GenerationSpanData`` are turned into ``chat``
    spans by lifting the request, response, usage, and reasoning data directly
    off the SpanData — the Agents SDK already serializes the full openai
    request/response, so no separate openai-side patch is needed.

    No synthetic OTel "trace root" is emitted on ``on_trace_start``: OpenAI's
    ``TaskSpanData`` already represents the workflow with strictly more detail
    (usage totals, metadata) than the bare ``Trace`` object, so we let the
    TaskSpan be the natural OTel root. ``trace.group_id`` is still propagated
    onto every span via ``gen_ai.conversation.id``, so conversation grouping
    in the Agents tab still works without an explicit root span.
    """

    def __init__(self) -> None:
        self._span_otel: dict[str, Any] = {}
        # OTel context tokens for each in-flight span. Each token comes from
        # ``otel_context.attach(set_span_in_context(span))`` — detaching it
        # restores the prior current span. Stored so on_span_end can detach
        # in LIFO order. Without this, child spans created inside the openai
        # wrapper wouldn't see our agent spans as the OTel parent.
        self._span_tokens: dict[str, Any] = {}
        self._conversation_ids: dict[str, str] = {}
        # In-flight openai span_ids per trace_id, kept as a dict acting as an
        # ordered set so on_trace_end can detach leftover tokens in LIFO
        # (reverse-insertion) order. ``otel_context.detach`` uses
        # ``ContextVar.reset``, which silently corrupts the context stack if
        # called out of LIFO order — a plain set's hash-bucket iteration would
        # almost never match LIFO. Lets the sweep handle spans the SDK never
        # closed without leaking state across Runner.run calls.
        self._trace_spans: dict[str, dict[str, None]] = {}

    def _tracer(self) -> Any:
        return otel_trace.get_tracer(_TRACER_NAME)

    def _parent_context(self, span: Span) -> Any:
        """Build an OTel context bound to this span's parent.

        Returns ``None`` if no parent OTel span exists — the new span then
        becomes the OTel root for the trace (this is how TaskSpan ends up
        as the root for typical Runner.run flows).
        """
        if span.parent_id and (parent := self._span_otel.get(span.parent_id)):
            return otel_trace.set_span_in_context(parent)
        return None

    def on_trace_start(self, trace: Trace) -> None:
        self._conversation_ids[trace.trace_id] = _conversation_id_for_trace(trace)
        self._trace_spans.setdefault(trace.trace_id, {})

    def on_trace_end(self, trace: Trace) -> None:
        # Sweep any in-flight spans belonging to this trace. In healthy flows
        # on_span_end already removed them; this handler covers the case where
        # the SDK ends the trace without closing every span (errors, abrupt
        # cancellations) so we don't leak OTel spans / context tokens.
        leftover = self._trace_spans.pop(trace.trace_id, {})
        # Detach in LIFO order — see comment on ``self._trace_spans``.
        for span_id in reversed(leftover):
            token = self._span_tokens.pop(span_id, None)
            if token is not None:
                otel_context.detach(token)
            otel_span = self._span_otel.pop(span_id, None)
            if otel_span is not None and otel_span.is_recording():
                otel_span.end()
        self._conversation_ids.pop(trace.trace_id, None)

    def on_span_start(self, span: Span) -> None:
        parent_ctx = self._parent_context(span)
        otel_span = self._tracer().start_span(
            _otel_span_name(span),
            context=parent_ctx,
            start_time=_iso_to_ns(span.started_at),
        )
        otel_span.set_attribute(f"{_WEAVE_ATTR_PREFIX}.span_id", span.span_id)
        otel_span.set_attribute(f"{_WEAVE_ATTR_PREFIX}.trace_id", span.trace_id)
        # Stamp integration provenance on every span (flattened for OTel).
        _set_attrs(otel_span, OPENAI_AGENTS_INTEGRATION.as_otel_attributes())
        self._span_otel[span.span_id] = otel_span
        self._trace_spans.setdefault(span.trace_id, {})[span.span_id] = None
        # Attach so any span the user creates inside an Agents-SDK span nests
        # under this one. Detached in on_span_end.
        self._span_tokens[span.span_id] = otel_context.attach(
            otel_trace.set_span_in_context(otel_span)
        )

    def on_span_end(self, span: Span) -> None:
        otel_span = self._span_otel.pop(span.span_id, None)
        if otel_span is None:
            return
        trace_spans = self._trace_spans.get(span.trace_id)
        if trace_spans is not None:
            trace_spans.pop(span.span_id, None)

        token = self._span_tokens.pop(span.span_id, None)
        if token is not None:
            otel_context.detach(token)

        # Enrich-then-end. The enrichment block walks SDK payloads (e.g.
        # response.output items expected to expose ``model_dump``) and can
        # raise on unexpected shapes. We must still end the OTel span on any
        # failure or it leaks: dropped from our maps above but never exported.
        try:
            # Re-compute the span name now that we have the full data (e.g. the
            # openai Response's model is only available on on_span_end, so the
            # chat span starts as "chat" and gains the model suffix here).
            otel_span.update_name(_otel_span_name(span))

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
        except Exception as exc:
            logger.exception(
                "Failed to enrich OTel span for openai span_id=%s", span.span_id
            )
            otel_span.set_status(StatusCode.ERROR, f"weave enrichment failed: {exc}")
        finally:
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
        # Detach in LIFO (reverse-insertion) order — see comment on
        # ``self._trace_spans``. ``dict.values()`` iterates in insertion order
        # in Python 3.7+, so reversing gives us the correct stack-unwind order.
        for token in reversed(self._span_tokens.values()):
            otel_context.detach(token)
        for otel_span in self._span_otel.values():
            if otel_span.is_recording():
                otel_span.end()
        self._span_tokens.clear()
        self._span_otel.clear()
        self._conversation_ids.clear()
        self._trace_spans.clear()


def _otel_span_name(span: Span) -> str:
    """Pick a descriptive OTel span name based on the span type.

    Semconv-mapped types use the conventional ``<operation> <subject>`` shape
    (e.g. ``invoke_agent Triage``, ``execute_tool get_weather``). Custom types
    use ``<kind> <subject>`` for readability in trace viewers.
    """
    sd = span.span_data
    name = _call_name(span)
    if isinstance(sd, AgentSpanData):
        # Keep the span name aligned with gen_ai.agent.name in _agent_attrs:
        # an explicit ambient override wins over the SDK-native name.
        return f"invoke_agent {resolve_agent_name(name)}"
    if _is_task_span_data(sd):
        # Structural span — NOT invoke_agent, since a Task wraps a workflow
        # not an agent. See _task_attrs.
        return f"workflow {name}"
    if _is_turn_span_data(sd):
        # Structural span — NOT invoke_agent, since a Turn is a loop iteration
        # within an agent. See _turn_attrs.
        return name
    if isinstance(sd, ResponseSpanData):
        model = sd.response.model if sd.response is not None else ""
        return f"chat {model}".rstrip()
    if isinstance(sd, GenerationSpanData):
        return f"chat {sd.model or ''}".rstrip()
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
