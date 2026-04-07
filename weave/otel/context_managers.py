"""OTel-emitting context managers for GenAI observability.

Tier 2 SDK: explicit context managers that emit OTel spans with the correct
GenAI semantic convention attributes. Users declare semantics directly — no
decorator magic.

All context managers emit standard OTel spans via the active TracerProvider.
They compose naturally with Tier 1 auto-instrumentations (same OTel context
propagation) and produce identical rows in genai_spans.

Examples:
    Basic agent with chat and tool::

        import weave

        with weave.agent("my-agent", version="1.0") as a:
            with weave.chat(model="gpt-4") as c:
                c.input_messages([{"role": "user", "content": "Hello"}])
                response = my_llm_call(...)
                c.output_message(response)
                c.usage(input_tokens=10, output_tokens=5)

            with weave.tool("get_weather") as t:
                t.arguments({"city": "Tokyo"})
                result = get_weather("Tokyo")
                t.result(result)

    Conversation tracking::

        with weave.agent("bot", conversation_id="session-1"):
            with weave.chat(model="gpt-4") as c:
                ...
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

_TRACER_NAME = "weave.agents"


def _get_tracer() -> Any:
    """Get or create a tracer from the global TracerProvider."""
    from opentelemetry import trace

    return trace.get_tracer(_TRACER_NAME)


def _set_baggage(key: str, value: str) -> Any:
    """Set a W3C Baggage entry in the current context."""
    from opentelemetry import baggage, context

    ctx = baggage.set_baggage(key, value)
    token = context.attach(ctx)
    return token


@contextmanager
def agent(
    name: str,
    *,
    version: str = "",
    conversation_id: str = "",
    description: str = "",
    system_instructions: list[str] | None = None,
    tool_definitions: str = "",
) -> Generator[AgentSpan, None, None]:
    """Create an invoke_agent span with baggage propagation.

    Sets agent_name/agent_version as W3C Baggage so all child spans
    (including those from auto-instrumentors) inherit these attributes
    via BaggageSpanProcessor.

    Args:
        name: Agent name (gen_ai.agent.name).
        version: Agent version (gen_ai.agent.version).
        conversation_id: Links this invocation to a conversation.
        description: Agent description.
        system_instructions: System prompts for this agent.
        tool_definitions: JSON string of available tool definitions.
    """
    from opentelemetry import baggage, context, trace

    tracer = _get_tracer()
    tokens: list[Any] = []

    # Set baggage for propagation to child spans
    ctx = baggage.set_baggage("gen_ai.agent.name", name)
    tokens.append(context.attach(ctx))
    if version:
        ctx = baggage.set_baggage("gen_ai.agent.version", version)
        tokens.append(context.attach(ctx))
    if conversation_id:
        ctx = baggage.set_baggage("gen_ai.conversation.id", conversation_id)
        tokens.append(context.attach(ctx))

    span_name = f"invoke_agent {name}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.agent.name", name)
        if version:
            span.set_attribute("gen_ai.agent.version", version)
        if description:
            span.set_attribute("gen_ai.agent.description", description)
        if conversation_id:
            span.set_attribute("gen_ai.conversation.id", conversation_id)
        if system_instructions:
            span.set_attribute(
                "gen_ai.system_instructions",
                json.dumps(
                    [{"role": "system", "content": s} for s in system_instructions]
                ),
            )
        if tool_definitions:
            span.set_attribute("gen_ai.tool.definitions", tool_definitions)

        agent_span = AgentSpan(span)
        try:
            yield agent_span
            span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            for token in reversed(tokens):
                context.detach(token)


@contextmanager
def chat(
    *,
    model: str = "",
    provider: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Generator[ChatSpan, None, None]:
    """Create a chat (LLM call) span.

    Args:
        model: Model name (gen_ai.request.model).
        provider: Provider name (gen_ai.system).
        temperature: Request temperature.
        max_tokens: Max tokens for the response.
    """
    from opentelemetry import trace

    tracer = _get_tracer()
    span_name = f"chat {model}" if model else "chat"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        if model:
            span.set_attribute("gen_ai.request.model", model)
        if provider:
            span.set_attribute("gen_ai.system", provider)
        if temperature is not None:
            span.set_attribute("gen_ai.request.temperature", temperature)
        if max_tokens is not None:
            span.set_attribute("gen_ai.request.max_tokens", max_tokens)

        chat_span = ChatSpan(span)
        try:
            yield chat_span
            span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@contextmanager
def tool(
    name: str,
    *,
    tool_type: str = "",
    tool_call_id: str = "",
) -> Generator[ToolSpan, None, None]:
    """Create an execute_tool span.

    Args:
        name: Tool name (gen_ai.tool.name).
        tool_type: Tool type (function, mcp, etc).
        tool_call_id: ID linking this execution to a tool_call in a chat response.
    """
    from opentelemetry import trace

    tracer = _get_tracer()
    span_name = f"execute_tool {name}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", name)
        if tool_type:
            span.set_attribute("gen_ai.tool.type", tool_type)
        if tool_call_id:
            span.set_attribute("gen_ai.tool.call.id", tool_call_id)

        tool_span = ToolSpan(span)
        try:
            yield tool_span
            span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


# ---------------------------------------------------------------------------
# Span wrappers — provide typed methods for setting GenAI attributes
# ---------------------------------------------------------------------------


class _BaseSpan:
    """Base wrapper around an OTel span with helper methods."""

    def __init__(self, span: Any) -> None:
        self._span = span

    @property
    def span_id(self) -> str:
        ctx = self._span.get_span_context()
        return format(ctx.span_id, "016x") if ctx else ""

    @property
    def trace_id(self) -> str:
        ctx = self._span.get_span_context()
        return format(ctx.trace_id, "032x") if ctx else ""

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def dataset_row_ref(self, ref: str) -> None:
        """Link this span to a dataset row via object_refs."""
        existing = self._span.attributes.get("weave.object_refs", [])
        refs = list(existing) + [ref]
        self._span.set_attribute("weave.object_refs", refs)


class AgentSpan(_BaseSpan):
    """Wrapper for an invoke_agent span."""

    pass


class ChatSpan(_BaseSpan):
    """Wrapper for a chat (LLM call) span."""

    def input_messages(self, messages: list[dict[str, Any]]) -> None:
        """Set input messages on the span."""
        self._span.set_attribute("gen_ai.input.messages", json.dumps(messages))

    def output_message(self, message: dict[str, Any] | str) -> None:
        """Set the output message on the span."""
        if isinstance(message, str):
            message = {"role": "assistant", "content": message}
        self._span.set_attribute("gen_ai.output.messages", json.dumps([message]))

    def usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        """Set token usage on the span."""
        if input_tokens:
            self._span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        if output_tokens:
            self._span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        if reasoning_tokens:
            self._span.set_attribute("gen_ai.usage.reasoning_tokens", reasoning_tokens)
        if total_tokens:
            self._span.set_attribute("llm.usage.total_tokens", total_tokens)

    def finish_reason(self, reason: str) -> None:
        """Set the finish reason (stop, length, tool_call, etc)."""
        self._span.set_attribute("gen_ai.response.finish_reasons", [reason])

    def response_model(self, model: str) -> None:
        """Set the actual model used in the response (may differ from request)."""
        self._span.set_attribute("gen_ai.response.model", model)


class ToolSpan(_BaseSpan):
    """Wrapper for an execute_tool span."""

    def arguments(self, args: dict[str, Any] | str) -> None:
        """Set tool call arguments."""
        if isinstance(args, dict):
            args = json.dumps(args)
        self._span.set_attribute("gen_ai.tool.call.arguments", args)

    def result(self, result: Any) -> None:
        """Set tool call result."""
        if not isinstance(result, str):
            result = json.dumps(result)
        self._span.set_attribute("gen_ai.tool.call.result", result)
