"""Weave OTel instrumentor for the OpenAI Agents SDK.

Replaces the community ``opentelemetry-instrumentation-openai-agents-v2``
package and all gap-closing patches with a single ``instrument()`` call
that emits GenAI semantic convention spans, auto-captures media, and
extracts agent metadata automatically from Agent objects.

Usage::

    from weave.otel import setup_tracing
    from weave.otel.instrumentors.openai_agents import instrument

    provider = setup_tracing(project="my-project", genai_endpoint="...")
    instrument(provider, agents=[my_agent], conversation="my-chat")

Dependencies:
    - ``openai-agents`` (the OpenAI Agents SDK)
    - ``opentelemetry-sdk``
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from agents import Agent
from agents.tracing import (
    AgentSpanData,
    CustomSpanData,
    FunctionSpanData,
    GuardrailSpanData,
    HandoffSpanData,
    ResponseSpanData,
    Span,
    Trace,
    TracingProcessor,
    add_trace_processor,
)
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import SpanKind, StatusCode

try:
    from agents.tracing import GenerationSpanData
except ImportError:
    GenerationSpanData = None  # type: ignore[assignment,misc]

try:
    from agents.tracing import TranscriptionSpanData
except ImportError:
    TranscriptionSpanData = None  # type: ignore[assignment,misc]

try:
    from agents.tracing import SpeechSpanData
except ImportError:
    SpeechSpanData = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

_active_processor: WeaveOTelProcessor | None = None


# ---------------------------------------------------------------------------
# Agent discovery
# ---------------------------------------------------------------------------


@dataclass
class _AgentMeta:
    """Metadata extracted from an Agent object."""

    name: str
    instructions: str = ""
    tool_defs: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""


def _discover_agents(agents: list[Agent]) -> dict[str, _AgentMeta]:
    """Recursively walk the agent tree and extract metadata.

    Inspects ``Agent.instructions``, ``Agent.tools``, ``Agent.handoffs``,
    and ``Agent.model`` on each agent, following handoff references to
    discover the full agent graph.

    Args:
        agents: Root agent(s) to start discovery from.

    Returns:
        Dict mapping agent name to its extracted metadata.

    Examples:
        >>> meta = _discover_agents([triage_agent])
        >>> meta["TriageAgent"].instructions
        'You route requests to specialists.'
    """
    result: dict[str, _AgentMeta] = {}
    queue = list(agents)
    seen: set[str] = set()

    while queue:
        agent = queue.pop(0)
        name = getattr(agent, "name", None)
        if not name or name in seen:
            continue
        seen.add(name)

        instructions = ""
        raw = getattr(agent, "instructions", None)
        if isinstance(raw, str):
            instructions = raw

        tool_defs: list[dict[str, Any]] = []

        for tool in getattr(agent, "tools", []) or []:
            tool_name = getattr(tool, "name", None)
            if not tool_name:
                continue
            tool_def: dict[str, Any] = {"type": "function", "name": tool_name}
            desc = getattr(tool, "description", None)
            if desc:
                tool_def["description"] = desc
            tool_defs.append(tool_def)

        for handoff in getattr(agent, "handoffs", []) or []:
            if isinstance(handoff, Agent):
                h_name = getattr(handoff, "name", "")
                h_desc = getattr(handoff, "handoff_description", "")
                tool_defs.append(
                    {"type": "handoff", "name": h_name, "description": h_desc}
                )
                queue.append(handoff)
            else:
                h_name = getattr(handoff, "agent_name", "") or getattr(
                    handoff, "tool_name", ""
                )
                h_desc = getattr(handoff, "tool_description", "")
                tool_defs.append(
                    {"type": "handoff", "name": h_name, "description": h_desc}
                )
                h_agent = getattr(handoff, "agent", None)
                if h_agent and isinstance(h_agent, Agent):
                    queue.append(h_agent)

        model = str(getattr(agent, "model", "") or "")

        result[name] = _AgentMeta(
            name=name,
            instructions=instructions,
            tool_defs=tool_defs,
            model=model,
        )

    return result


# ---------------------------------------------------------------------------
# Response serialization helpers
# ---------------------------------------------------------------------------


def _dump(obj: Any) -> dict[str, Any]:
    """Convert a pydantic model or dict to a plain dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {}


def _serialize_input(input_data: Any) -> str:
    """Convert ``ResponseSpanData.input`` to a ``gen_ai.input.messages`` JSON string.

    Args:
        input_data: The raw input from the span data (string, list, or None).

    Returns:
        JSON string of OpenAI-style message array.
    """
    if input_data is None:
        return ""
    if isinstance(input_data, str):
        return json.dumps([{"role": "user", "content": input_data}])

    if isinstance(input_data, list):
        messages: list[dict[str, Any]] = []
        for item in input_data:
            if isinstance(item, str):
                messages.append({"role": "user", "content": item})
            else:
                d = _dump(item)
                role = d.get("role", "user")
                item_type = d.get("type", "")
                if item_type == "message":
                    text = _extract_text_from_content_parts(d.get("content", []))
                    messages.append({"role": role, "content": text})
                elif item_type == "function_call_output":
                    messages.append(
                        {
                            "role": "tool",
                            "content": str(d.get("output", "")),
                            "tool_call_id": d.get("call_id", ""),
                        }
                    )
                elif "content" in d:
                    content = d["content"]
                    if isinstance(content, str):
                        messages.append({"role": role, "content": content})
                    elif isinstance(content, list):
                        text = _extract_text_from_content_parts(content)
                        messages.append({"role": role, "content": text})
                    else:
                        messages.append({"role": role, "content": str(content)})
                else:
                    messages.append(d)
        return json.dumps(messages) if messages else ""

    return ""


def _serialize_output(response: Any) -> str:
    """Convert a ``Response`` object to a ``gen_ai.output.messages`` JSON string.

    Produces a message array compatible with ``genai_extraction._normalize_raw_messages``
    and ``extract_reasoning_content``.

    Args:
        response: The OpenAI ``Response`` object from ``ResponseSpanData.response``.

    Returns:
        JSON string of message array, or empty string.
    """
    if response is None:
        return ""
    output = getattr(response, "output", None)
    if not output:
        return ""

    messages: list[dict[str, Any]] = []
    for item in output:
        d = _dump(item)
        item_type = d.get("type", "")

        if item_type == "message":
            content_parts = d.get("content", [])
            text = _extract_text_from_content_parts(content_parts)
            messages.append({"role": d.get("role", "assistant"), "content": text})

        elif item_type == "function_call":
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": d.get("name", ""),
                            "arguments": d.get("arguments", ""),
                            "id": d.get("call_id", ""),
                        }
                    ],
                }
            )

        elif item_type == "reasoning":
            reasoning_text = _extract_reasoning_text(d)
            if reasoning_text:
                messages.append(
                    {
                        "role": "assistant",
                        "parts": [{"type": "reasoning", "content": reasoning_text}],
                    }
                )

        elif item_type == "image_generation_call":
            messages.append(
                {
                    "role": "assistant",
                    "content": f"[image_generation: {d.get('id', '')}]",
                }
            )

        elif item_type in {
            "computer_call",
            "file_search_call",
            "code_interpreter_call",
            "mcp_call",
        }:
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": item_type.replace("_call", ""),
                            "arguments": json.dumps(
                                {
                                    k: v
                                    for k, v in d.items()
                                    if k not in {"type", "id", "status"}
                                }
                            ),
                            "id": d.get("id", ""),
                        }
                    ],
                }
            )

    return json.dumps(messages) if messages else ""


def _extract_text_from_content_parts(parts: Any) -> str:
    """Extract text from OpenAI-style content part arrays."""
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        return ""
    texts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            if part.get("type") == "output_text":
                texts.append(part.get("text", ""))
            elif part.get("type") == "input_text":
                texts.append(part.get("text", ""))
            elif "text" in part:
                texts.append(str(part["text"]))
            elif "content" in part and isinstance(part["content"], str):
                texts.append(part["content"])
    return "\n".join(texts)


def _extract_reasoning_text(d: dict[str, Any]) -> str:
    """Extract reasoning text from a reasoning output item dict."""
    content_items = d.get("content", [])
    if isinstance(content_items, str):
        return content_items
    if not isinstance(content_items, list):
        return ""
    texts: list[str] = []
    for ci in content_items:
        if isinstance(ci, dict) and ci.get("type") == "reasoning_text":
            texts.append(ci.get("text", ""))
        elif isinstance(ci, str):
            texts.append(ci)
    return "\n".join(texts)


def _extract_images_from_output(output: Any) -> list[bytes]:
    """Find base64-encoded images in response output items."""
    if not output:
        return []
    images: list[bytes] = []
    for item in output:
        d = _dump(item)
        if d.get("type") != "image_generation_call":
            continue
        result = d.get("result", "")
        if not result:
            continue
        if isinstance(result, str):
            try:
                images.append(base64.b64decode(result))
            except Exception:
                logger.debug("Failed to decode image_generation_call result")
        elif isinstance(result, bytes):
            images.append(result)
    return images


# ---------------------------------------------------------------------------
# Core OTel processor
# ---------------------------------------------------------------------------


class WeaveOTelProcessor(TracingProcessor):  # type: ignore[misc]
    """TracingProcessor that emits OTel spans with GenAI semantic conventions.

    Registered via ``instrument()`` with the OpenAI Agents SDK's trace
    processor system.  Translates SDK trace/span lifecycle events into
    properly-attributed OTel spans that feed directly into Weave's GenAI
    pipeline (``genai_extraction.py`` -> ``genai_spans`` table -> UI).
    """

    def __init__(
        self,
        tracer: trace.Tracer,
        agent_meta: dict[str, _AgentMeta],
        conversation_id: str,
        conversation_name: str,
        capture_media: bool = True,
    ) -> None:
        self._tracer = tracer
        self._agent_meta = agent_meta
        self._conversation_id = conversation_id
        self._conversation_name = conversation_name
        self._capture_media = capture_media
        self._disabled = False

        self._otel_spans: dict[str, trace.Span] = {}
        self._otel_tokens: dict[str, object] = {}

    # -- helpers -------------------------------------------------------------

    def _get_parent_context(self, span: Span) -> otel_context.Context | None:
        """Build an OTel context referencing the parent span, if any."""
        parent_id = getattr(span, "parent_id", None)
        if parent_id and parent_id in self._otel_spans:
            parent = self._otel_spans[parent_id]
            return trace.set_span_in_context(parent)
        return None

    def _set_common_attrs(self, otel_span: trace.Span) -> None:
        """Set attributes shared across all span types."""
        if self._conversation_id:
            otel_span.set_attribute("gen_ai.conversation.id", self._conversation_id)
        if self._conversation_name:
            otel_span.set_attribute("gen_ai.conversation.name", self._conversation_name)
        otel_span.set_attribute("gen_ai.provider.name", "openai")

    def _attach_span(self, span_id: str, otel_span: trace.Span) -> None:
        """Make an OTel span the current active span in the thread context."""
        ctx = trace.set_span_in_context(otel_span)
        token = otel_context.attach(ctx)
        self._otel_tokens[span_id] = token

    def _detach_span(self, span_id: str) -> None:
        """Restore the previous context after a span completes."""
        token = self._otel_tokens.pop(span_id, None)
        if token is not None:
            otel_context.detach(token)  # type: ignore[arg-type]

    # -- trace lifecycle -----------------------------------------------------

    def on_trace_start(self, sdk_trace: Trace) -> None:
        """No-op — the root agent span serves as the OTel trace root."""

    def on_trace_end(self, sdk_trace: Trace) -> None:
        """No-op — span cleanup happens in on_span_end."""

    # -- span lifecycle: start -----------------------------------------------

    def on_span_start(self, span: Span) -> None:
        """Create an OTel span corresponding to the Agents SDK span."""
        if self._disabled:
            return

        data = span.span_data

        if isinstance(data, AgentSpanData):
            self._start_agent_span(span, data)
        elif isinstance(data, ResponseSpanData):
            self._start_response_span(span, data)
        elif isinstance(data, FunctionSpanData):
            self._start_function_span(span, data)
        elif isinstance(data, HandoffSpanData):
            self._start_handoff_span(span, data)
        elif isinstance(data, GuardrailSpanData):
            self._start_guardrail_span(span, data)
        elif isinstance(data, CustomSpanData):
            self._start_custom_span(span, data)
        elif GenerationSpanData and isinstance(data, GenerationSpanData):
            self._start_generation_span(span, data)
        elif TranscriptionSpanData and isinstance(data, TranscriptionSpanData):
            self._start_generic_span(
                span, "transcription", getattr(data, "name", "transcription")
            )
        elif SpeechSpanData and isinstance(data, SpeechSpanData):
            self._start_generic_span(span, "speech", "speech")
        else:
            self._start_generic_span(span, "", getattr(data, "type", "unknown"))

    def _start_agent_span(self, span: Span, data: AgentSpanData) -> None:
        agent_name = data.name or "agent"
        otel_span = self._tracer.start_span(
            name=f"invoke_agent {agent_name}",
            kind=SpanKind.INTERNAL,
            context=self._get_parent_context(span),
        )
        otel_span.set_attribute("gen_ai.operation.name", "invoke_agent")
        otel_span.set_attribute("gen_ai.agent.name", agent_name)
        self._set_common_attrs(otel_span)

        meta = self._agent_meta.get(agent_name)
        if meta:
            if meta.instructions:
                otel_span.set_attribute(
                    "gen_ai.system_instructions",
                    json.dumps([{"role": "system", "content": meta.instructions}]),
                )
            if meta.tool_defs:
                otel_span.set_attribute(
                    "gen_ai.tool.definitions", json.dumps(meta.tool_defs)
                )
            if meta.model:
                otel_span.set_attribute("gen_ai.request.model", meta.model)

        self._otel_spans[span.span_id] = otel_span
        self._attach_span(span.span_id, otel_span)

    def _start_response_span(self, span: Span, data: ResponseSpanData) -> None:
        otel_span = self._tracer.start_span(
            name="chat",
            kind=SpanKind.CLIENT,
            context=self._get_parent_context(span),
        )
        otel_span.set_attribute("gen_ai.operation.name", "chat")
        self._set_common_attrs(otel_span)

        self._otel_spans[span.span_id] = otel_span
        self._attach_span(span.span_id, otel_span)

    def _start_function_span(self, span: Span, data: FunctionSpanData) -> None:
        tool_name = data.name or "function"
        otel_span = self._tracer.start_span(
            name=f"execute_tool {tool_name}",
            kind=SpanKind.INTERNAL,
            context=self._get_parent_context(span),
        )
        otel_span.set_attribute("gen_ai.operation.name", "execute_tool")
        otel_span.set_attribute("gen_ai.tool.name", tool_name)
        self._set_common_attrs(otel_span)

        self._otel_spans[span.span_id] = otel_span
        self._attach_span(span.span_id, otel_span)

    def _start_handoff_span(self, span: Span, data: HandoffSpanData) -> None:
        from_agent = data.from_agent or ""
        to_agent = data.to_agent or ""
        otel_span = self._tracer.start_span(
            name=f"handoff {from_agent} -> {to_agent}",
            kind=SpanKind.INTERNAL,
            context=self._get_parent_context(span),
        )
        otel_span.set_attribute("gen_ai.operation.name", "handoff")
        self._set_common_attrs(otel_span)

        self._otel_spans[span.span_id] = otel_span

    def _start_guardrail_span(self, span: Span, data: GuardrailSpanData) -> None:
        name = data.name or "guardrail"
        otel_span = self._tracer.start_span(
            name=f"guardrail {name}",
            kind=SpanKind.INTERNAL,
            context=self._get_parent_context(span),
        )
        otel_span.set_attribute("gen_ai.operation.name", "guardrail")
        otel_span.set_attribute("gen_ai.agent.name", name)
        self._set_common_attrs(otel_span)

        self._otel_spans[span.span_id] = otel_span

    def _start_custom_span(self, span: Span, data: CustomSpanData) -> None:
        name = data.name or "custom"
        otel_span = self._tracer.start_span(
            name=f"custom {name}",
            kind=SpanKind.INTERNAL,
            context=self._get_parent_context(span),
        )
        otel_span.set_attribute("gen_ai.operation.name", "custom")
        self._set_common_attrs(otel_span)

        self._otel_spans[span.span_id] = otel_span

    def _start_generation_span(self, span: Span, data: Any) -> None:
        model = getattr(data, "model", "") or ""
        name = f"chat {model}" if model else "chat"
        otel_span = self._tracer.start_span(
            name=name,
            kind=SpanKind.CLIENT,
            context=self._get_parent_context(span),
        )
        otel_span.set_attribute("gen_ai.operation.name", "chat")
        if model:
            otel_span.set_attribute("gen_ai.request.model", model)
        self._set_common_attrs(otel_span)

        self._otel_spans[span.span_id] = otel_span
        self._attach_span(span.span_id, otel_span)

    def _start_generic_span(self, span: Span, operation: str, name: str) -> None:
        otel_span = self._tracer.start_span(
            name=name,
            kind=SpanKind.INTERNAL,
            context=self._get_parent_context(span),
        )
        if operation:
            otel_span.set_attribute("gen_ai.operation.name", operation)
        self._set_common_attrs(otel_span)

        self._otel_spans[span.span_id] = otel_span

    # -- span lifecycle: end -------------------------------------------------

    def on_span_end(self, span: Span) -> None:
        """Set final attributes and end the corresponding OTel span."""
        if self._disabled:
            return

        otel_span = self._otel_spans.pop(span.span_id, None)
        if otel_span is None:
            return

        data = span.span_data

        try:
            if isinstance(data, ResponseSpanData):
                self._end_response_span(otel_span, span, data)
            elif isinstance(data, FunctionSpanData):
                self._end_function_span(otel_span, span, data)
            elif isinstance(data, HandoffSpanData):
                self._end_handoff_span(otel_span, span, data)
            elif isinstance(data, GuardrailSpanData):
                self._end_guardrail_span(otel_span, span, data)
            elif isinstance(data, CustomSpanData):
                self._end_custom_span(otel_span, span, data)
            elif GenerationSpanData and isinstance(data, GenerationSpanData):
                self._end_generation_span(otel_span, span, data)

            if span.error:
                msg = getattr(span.error, "message", str(span.error))
                otel_span.set_status(StatusCode.ERROR, msg)
        except Exception:
            logger.debug("Error setting span attributes", exc_info=True)
        finally:
            self._detach_span(span.span_id)
            otel_span.end()

    def _end_response_span(
        self, otel_span: trace.Span, span: Span, data: ResponseSpanData
    ) -> None:
        response = data.response
        if response is None:
            return

        model = str(getattr(response, "model", "") or "")
        if model:
            otel_span.set_attribute("gen_ai.request.model", model)
            otel_span.set_attribute("gen_ai.response.model", model)
            otel_span.update_name(f"chat {model}")

        resp_id = str(getattr(response, "id", "") or "")
        if resp_id:
            otel_span.set_attribute("gen_ai.response.id", resp_id)

        usage = getattr(response, "usage", None)
        if usage:
            input_t = getattr(usage, "input_tokens", 0) or 0
            output_t = getattr(usage, "output_tokens", 0) or 0
            total_t = getattr(usage, "total_tokens", 0) or 0
            otel_span.set_attribute("gen_ai.usage.input_tokens", input_t)
            otel_span.set_attribute("gen_ai.usage.output_tokens", output_t)
            if total_t:
                otel_span.set_attribute("gen_ai.usage.total_tokens", total_t)

            details = getattr(usage, "output_tokens_details", None)
            if details:
                reasoning_t = getattr(details, "reasoning_tokens", 0) or 0
                if reasoning_t:
                    otel_span.set_attribute(
                        "gen_ai.usage.reasoning_tokens", reasoning_t
                    )

        input_json = _serialize_input(data.input)
        if input_json:
            otel_span.set_attribute("gen_ai.input.messages", input_json)

        output_json = _serialize_output(response)
        if output_json:
            otel_span.set_attribute("gen_ai.output.messages", output_json)

        status = getattr(response, "status", "")
        if status:
            otel_span.set_attribute("gen_ai.response.finish_reasons", [str(status)])

        if self._capture_media:
            self._capture_response_media(otel_span, response)

    def _end_function_span(
        self, otel_span: trace.Span, span: Span, data: FunctionSpanData
    ) -> None:
        if data.input is not None:
            otel_span.set_attribute("gen_ai.tool.call.arguments", str(data.input))
        if data.output is not None:
            otel_span.set_attribute("gen_ai.tool.call.result", str(data.output))

        mcp = getattr(data, "mcp_data", None)
        if mcp:
            otel_span.set_attribute("gen_ai.tool.type", "mcp")

    def _end_handoff_span(
        self, otel_span: trace.Span, span: Span, data: HandoffSpanData
    ) -> None:
        if data.from_agent:
            otel_span.set_attribute("gen_ai.agent.name", data.from_agent)
        if data.to_agent:
            otel_span.set_attribute("weave.handoff.to_agent", data.to_agent)

    def _end_guardrail_span(
        self, otel_span: trace.Span, span: Span, data: GuardrailSpanData
    ) -> None:
        otel_span.set_attribute("weave.guardrail.triggered", data.triggered)

    def _end_custom_span(
        self, otel_span: trace.Span, span: Span, data: CustomSpanData
    ) -> None:
        for key, val in (data.data or {}).items():
            try:
                if isinstance(val, (str, int, float, bool)):
                    otel_span.set_attribute(f"custom.{key}", val)
                else:
                    otel_span.set_attribute(f"custom.{key}", json.dumps(val))
            except Exception:
                pass

    def _end_generation_span(
        self, otel_span: trace.Span, span: Span, data: Any
    ) -> None:
        model = getattr(data, "model", "") or ""
        if model:
            otel_span.set_attribute("gen_ai.request.model", model)
            otel_span.set_attribute("gen_ai.response.model", model)
            otel_span.update_name(f"chat {model}")

        usage = getattr(data, "usage", None)
        if usage and isinstance(usage, dict):
            for k, v in usage.items():
                if isinstance(v, (int, float)):
                    otel_span.set_attribute(f"gen_ai.usage.{k}", v)

        raw_input = getattr(data, "input", None)
        if raw_input is not None:
            input_json = _serialize_input(raw_input)
            if input_json:
                otel_span.set_attribute("gen_ai.input.messages", input_json)

        raw_output = getattr(data, "output", None)
        if raw_output is not None:
            try:
                otel_span.set_attribute(
                    "gen_ai.output.messages",
                    json.dumps(
                        raw_output
                        if isinstance(raw_output, (list, dict))
                        else [{"role": "assistant", "content": str(raw_output)}]
                    ),
                )
            except Exception:
                pass

    # -- media capture -------------------------------------------------------

    def _capture_response_media(self, otel_span: trace.Span, response: Any) -> None:
        """Auto-capture images from image_generation_call output items."""
        output = getattr(response, "output", None)
        if not output:
            return

        images = _extract_images_from_output(output)
        if not images:
            return

        try:
            from weave.otel import log_content

            ctx = trace.set_span_in_context(otel_span)
            token = otel_context.attach(ctx)
            try:
                for i, img_bytes in enumerate(images):
                    key = (
                        f"generated_image_{i}" if len(images) > 1 else "generated_image"
                    )
                    log_content(
                        img_bytes, key=key, media_type="image/png", role="output"
                    )
            finally:
                otel_context.detach(token)
        except ImportError:
            logger.debug("weave.otel.log_content not available for media capture")
        except Exception:
            logger.debug("Failed to capture response media", exc_info=True)

    # -- lifecycle -----------------------------------------------------------

    def shutdown(self) -> None:
        """Clean up internal state."""
        self._otel_spans.clear()
        for token in self._otel_tokens.values():
            try:
                otel_context.detach(token)  # type: ignore[arg-type]
            except Exception:
                pass
        self._otel_tokens.clear()

    def force_flush(self) -> None:
        """No-op — OTel span export is handled by the TracerProvider."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def instrument(
    provider: TracerProvider,
    *,
    agents: list[Agent] | None = None,
    conversation: str | None = None,
    conversation_id: str | None = None,
    capture_media: bool = True,
    capture_reasoning: bool = True,
    capture_compaction: bool = True,
) -> WeaveOTelProcessor:
    """Instrument the OpenAI Agents SDK to emit OTel spans with GenAI semantic conventions.

    One call replaces ``OpenAIAgentsInstrumentor``, ``SystemPromptInjector``,
    ``ToolDefinitionsInjector``, ``ConversationIdInjector``,
    ``patch_openai_reasoning``, and ``patch_openai_compaction``.

    Args:
        provider: The OTel ``TracerProvider`` to create spans with.
        agents: Root agent(s) for automatic metadata discovery.  When
            provided, system prompts and tool definitions are extracted
            from ``Agent.instructions``, ``Agent.tools``, and
            ``Agent.handoffs`` recursively.
        conversation: Human-readable conversation name for the UI.
            Also generates a UUID conversation_id automatically.
        conversation_id: Explicit conversation ID.  When omitted, a
            UUID is generated if *conversation* is set.
        capture_media: Auto-capture images from ``image_generation_call``
            response output items via ``weave.otel.log_content``.
        capture_reasoning: Monkey-patch ``openai.Responses.create`` to
            capture ``reasoning_tokens`` on the active span.
        capture_compaction: Monkey-patch ``OpenAIResponsesCompactionSession``
            to emit ``weave.compaction.*`` attributes.

    Returns:
        The registered ``WeaveOTelProcessor`` (can be passed to
        ``uninstrument()`` for cleanup).

    Examples:
        >>> from weave.otel import setup_tracing
        >>> from weave.otel.instrumentors.openai_agents import instrument
        >>> provider = setup_tracing(project="demo", genai_endpoint="...")
        >>> instrument(provider, agents=[my_agent], conversation="trip")
    """
    global _active_processor  # noqa: PLW0603

    agent_meta: dict[str, _AgentMeta] = {}
    if agents:
        agent_meta = _discover_agents(agents)

    conv_id = conversation_id or (str(uuid.uuid4()) if conversation else "")
    conv_name = conversation or ""

    tracer = provider.get_tracer("weave.otel.instrumentors.openai_agents")

    processor = WeaveOTelProcessor(
        tracer=tracer,
        agent_meta=agent_meta,
        conversation_id=conv_id,
        conversation_name=conv_name,
        capture_media=capture_media,
    )

    add_trace_processor(processor)
    _active_processor = processor

    if capture_reasoning:
        try:
            from weave.otel.processors import patch_openai_reasoning

            patch_openai_reasoning()
        except Exception:
            logger.debug("Failed to apply reasoning token patch", exc_info=True)

    if capture_compaction:
        try:
            from weave.otel.compaction import patch_openai_compaction

            patch_openai_compaction()
        except Exception:
            logger.debug("Failed to apply compaction patch", exc_info=True)

    if capture_media:
        try:
            from weave.otel.patches import patch_all

            patch_all()
        except Exception:
            logger.debug("Failed to apply media capture patches", exc_info=True)

    if conv_name and conv_id:
        _write_conversation_annotation(conv_id, conv_name)

    return processor


def uninstrument(processor: WeaveOTelProcessor | None = None) -> None:
    """Disable the Weave OTel processor for OpenAI Agents.

    Args:
        processor: The processor returned by ``instrument()``.  When
            omitted, disables the most recently created processor.

    Examples:
        >>> proc = instrument(provider, agents=[agent])
        >>> uninstrument(proc)
    """
    global _active_processor  # noqa: PLW0603

    target = processor or _active_processor
    if target is not None:
        target._disabled = True

    if target is _active_processor:
        _active_processor = None

    try:
        from weave.otel.processors import unpatch_openai_reasoning

        unpatch_openai_reasoning()
    except Exception:
        pass

    try:
        from weave.otel.compaction import unpatch_openai_compaction

        unpatch_openai_compaction()
    except Exception:
        pass

    try:
        from weave.otel.patches import unpatch_all

        unpatch_all()
    except Exception:
        pass


def _write_conversation_annotation(conv_id: str, conv_name: str) -> None:
    """Write conversation name as an entity annotation (fire-and-forget)."""
    import os
    import threading

    def _post() -> None:
        try:
            import requests as http_requests

            endpoint = os.environ.get("WF_TRACE_SERVER_URL", "")
            if not endpoint:
                return
            api_key = os.environ.get("WANDB_API_KEY", "")
            entity = os.environ.get("WANDB_ENTITY", "")
            project = os.environ.get("WANDB_PROJECT", "")
            if not entity or not project:
                return

            url = f"{endpoint}/genai/annotations/upsert"
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if api_key:
                headers["wandb-api-key"] = api_key
            payload = {
                "project_id": f"{entity}/{project}",
                "annotations": [
                    {
                        "entity_type": "conversation",
                        "entity_id": conv_id,
                        "namespace": "display",
                        "key": "name",
                        "string_value": conv_name,
                        "value_type": "string",
                        "source": "sdk",
                    }
                ],
            }
            http_requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_post, daemon=True).start()
