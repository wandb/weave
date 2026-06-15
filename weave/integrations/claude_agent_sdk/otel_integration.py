"""Weave OTel tracing for the Claude Agent SDK.

Emits OpenTelemetry GenAI spans to Weave's Agents tab; the sibling
``claude_agent_sdk_integration.py`` emits legacy Weave calls instead. The
dispatcher selects this variant when ``WEAVE_USE_OTEL_V2`` is set.

Each ``query()`` call / ``ClaudeSDKClient`` turn becomes an ``invoke_agent``
span, with a child ``chat`` span per model response and an ``execute_tool``
span per tool call. The SDK reports token usage only on the final
``ResultMessage``, so it is attached to the last ``chat`` span.
"""

from __future__ import annotations

import importlib
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.trace import StatusCode

from weave.integrations.integration_metadata import library_integration
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)
from weave.session.types import Message, Reasoning, ToolCallPart, Usage
from weave.trace.autopatch import IntegrationSettings
from weave.trace.settings import should_disable_weave

logger = logging.getLogger(__name__)

_TRACER_NAME = "weave.claude_agent_sdk"
_AGENT_NAME = "claude_agent_sdk"
_PROVIDER_NAME = "anthropic"

_claude_agent_sdk_otel_patcher: MultiPatcher | None = None

# Integration provenance, flattened once for OTel span attributes (scalars only).
_INTEGRATION_OTEL_ATTRS = library_integration("claude_agent_sdk").as_otel_attributes()


@dataclass(frozen=True, slots=True)
class _AssistantOutput:
    """Parsed content of one assistant message.

    ``message`` is the chat span's output message, ``text`` the plain text
    (used as the turn's final result), and ``reasoning`` any thinking content.
    """

    message: Message
    text: str
    reasoning: Reasoning


@dataclass(frozen=True, slots=True)
class _PendingChat:
    """A chat span whose end is deferred until the aggregate usage is known.

    ``attrs`` is mutated in place (usage keys added) before the span is ended.
    """

    span: Any
    attrs: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _OpenTool:
    """An in-flight execute_tool span awaiting its tool_result.

    ``arguments`` is the JSON-encoded tool input, captured when the tool_use
    block is seen so it can be attached to the span at its tool_result.
    """

    span: Any
    name: str
    arguments: str


def _tracer() -> Any:
    return otel_trace.get_tracer(_TRACER_NAME)


def _usage_from_result(usage: dict[str, Any] | None) -> Usage:
    """Build a Usage from a ResultMessage's aggregate usage dict."""
    raw = usage or {}
    return Usage(
        input_tokens=int(raw.get("input_tokens", 0) or 0),
        output_tokens=int(raw.get("output_tokens", 0) or 0),
        cache_creation_input_tokens=int(raw.get("cache_creation_input_tokens", 0) or 0),
        cache_read_input_tokens=int(raw.get("cache_read_input_tokens", 0) or 0),
    )


def _assistant_output_message(
    msg: AssistantMessage, buffered_thinking: list[str]
) -> _AssistantOutput:
    """Build the chat span's output from an assistant message.

    ``buffered_thinking`` holds thinking text from preceding thinking-only
    assistant messages so it folds into this response's reasoning rather than
    splitting into its own chat span.
    """
    text_chunks: list[str] = []
    thinking_chunks: list[str] = list(buffered_thinking)
    tool_calls: list[ToolCallPart] = []
    for block in msg.content:
        if isinstance(block, TextBlock):
            text_chunks.append(block.text)
        elif isinstance(block, ThinkingBlock):
            thinking_chunks.append(block.thinking)
        elif isinstance(block, ToolUseBlock):
            tool_calls.append(
                ToolCallPart(id=block.id, name=block.name, arguments=block.input)
            )
    text = "\n".join(text_chunks)
    reasoning = Reasoning(
        content="\n".join(chunk for chunk in thinking_chunks if chunk)
    )
    message = Message.assistant(text=text, tool_calls=tool_calls or None)
    return _AssistantOutput(message=message, text=text, reasoning=reasoning)


@dataclass(slots=True)
class _TurnState:
    """Mutable per-turn accumulator (one invoke_agent span and its children).

    Not frozen: it accumulates as the message stream is consumed. Scope is one
    turn, owned by ``_trace_turn``.
    """

    user_prompt: str | None
    conversation_id: str = ""
    model: str = ""
    final_text: str = ""
    is_error: bool = False
    accumulated: list[Message] = field(default_factory=list)
    pending_thinking: list[str] = field(default_factory=list)
    # The most recent chat span, whose end is deferred so the aggregate usage
    # from ResultMessage can be attached before it closes.
    pending_chat: _PendingChat | None = None
    # tool_use_id -> in-flight execute_tool span.
    open_tool_spans: dict[str, _OpenTool] = field(default_factory=dict)


def _flush_pending_chat(state: _TurnState, *, usage: Usage | None = None) -> None:
    """Set attrs (optionally usage) on the deferred chat span and end it."""
    pending = state.pending_chat
    if pending is None:
        return
    attrs = pending.attrs
    if usage is not None:
        if usage.input_tokens:
            attrs["gen_ai.usage.input_tokens"] = usage.input_tokens
        if usage.output_tokens:
            attrs["gen_ai.usage.output_tokens"] = usage.output_tokens
        if usage.cache_creation_input_tokens:
            attrs["gen_ai.usage.cache_creation.input_tokens"] = (
                usage.cache_creation_input_tokens
            )
        if usage.cache_read_input_tokens:
            attrs["gen_ai.usage.cache_read.input_tokens"] = (
                usage.cache_read_input_tokens
            )
    for key, value in attrs.items():
        pending.span.set_attribute(key, value)
    pending.span.end()
    state.pending_chat = None


def _process_message(msg: Any, tracer: Any, state: _TurnState) -> None:
    """Handle one streamed message, creating/closing child spans as needed."""
    if isinstance(msg, SystemMessage):
        session_id = (msg.data or {}).get("session_id")
        if session_id:
            state.conversation_id = session_id
        return

    if isinstance(msg, AssistantMessage):
        # Buffer thinking-only messages so extended-thinking deltas fold into
        # the next response's chat span rather than spawning an empty one.
        if all(isinstance(b, ThinkingBlock) for b in msg.content) and msg.content:
            state.pending_thinking.extend(b.thinking for b in msg.content)
            return

        # A new response means the previous chat span is done (no usage — only
        # the final one carries the aggregate usage).
        _flush_pending_chat(state)
        if msg.model:
            state.model = msg.model

        output = _assistant_output_message(msg, state.pending_thinking)
        state.pending_thinking.clear()
        if output.text:
            state.final_text = output.text

        chat = tracer.start_span(f"chat {msg.model or ''}".rstrip())
        chat_attrs = llm_attributes(
            model=msg.model or "",
            provider_name=_PROVIDER_NAME,
            conversation_id=state.conversation_id,
            input_messages=list(state.accumulated),
            output_messages=[output.message],
            reasoning=output.reasoning if output.reasoning.content else None,
        )
        chat_attrs.update(_INTEGRATION_OTEL_ATTRS)
        state.pending_chat = _PendingChat(span=chat, attrs=chat_attrs)
        state.accumulated.append(output.message)

        for block in msg.content:
            if isinstance(block, ToolUseBlock):
                tool_span = tracer.start_span(f"execute_tool {block.name}")
                state.open_tool_spans[block.id] = _OpenTool(
                    span=tool_span,
                    name=block.name,
                    arguments=json.dumps(block.input, default=str),
                )
        return

    if isinstance(msg, UserMessage):
        content = msg.content if isinstance(msg.content, list) else []
        for block in content:
            if not isinstance(block, ToolResultBlock):
                continue
            state.accumulated.append(
                Message.tool_result(block.tool_use_id, block.content)
            )
            open_tool = state.open_tool_spans.pop(block.tool_use_id, None)
            if open_tool is None:
                continue
            attrs = execute_tool_attributes(
                tool_name=open_tool.name,
                conversation_id=state.conversation_id,
                tool_call_arguments=open_tool.arguments,
                tool_call_result=str(block.content),
                tool_call_id=block.tool_use_id,
            )
            attrs.update(_INTEGRATION_OTEL_ATTRS)
            for key, value in attrs.items():
                open_tool.span.set_attribute(key, value)
            if block.is_error:
                open_tool.span.set_status(StatusCode.ERROR, "tool reported an error")
            open_tool.span.end()
        return

    if isinstance(msg, ResultMessage):
        _flush_pending_chat(state, usage=_usage_from_result(msg.usage))
        if msg.result:
            state.final_text = msg.result
        if msg.is_error:
            state.is_error = True
        return


def _finalize_turn(root: Any, state: _TurnState) -> None:
    """Close any open child spans and finish the root invoke_agent span."""
    _flush_pending_chat(state)
    for open_tool in state.open_tool_spans.values():
        open_tool.span.end()
    state.open_tool_spans.clear()

    attrs = invoke_agent_attributes(
        agent_name=_AGENT_NAME,
        conversation_id=state.conversation_id,
        provider_name=_PROVIDER_NAME,
        model=state.model,
        input_messages=[Message(role="user", content=state.user_prompt)]
        if state.user_prompt
        else None,
        output_messages=[Message(role="assistant", content=state.final_text)]
        if state.final_text
        else None,
    )
    attrs.update(_INTEGRATION_OTEL_ATTRS)
    for key, value in attrs.items():
        root.set_attribute(key, value)
    if state.is_error:
        root.set_status(StatusCode.ERROR, state.final_text or "agent run failed")
    root.end()


async def _trace_turn(
    messages: AsyncIterator[Any],
    *,
    user_prompt: str | None,
    conversation_id_holder: list[str] | None = None,
) -> AsyncIterator[Any]:
    """Wrap a message stream, emitting the span tree for one turn.

    ``conversation_id_holder`` carries the SDK ``session_id`` across turns of a
    single ``ClaudeSDKClient``: the ``system/init`` message (which holds the
    session_id) is only sent on the first turn, so later turns must inherit it.
    """
    tracer = _tracer()
    root = tracer.start_span(f"invoke_agent {_AGENT_NAME}")
    token = otel_context.attach(otel_trace.set_span_in_context(root))
    state = _TurnState(user_prompt=user_prompt)
    if conversation_id_holder is not None and conversation_id_holder[0]:
        state.conversation_id = conversation_id_holder[0]
    try:
        async for msg in messages:
            try:
                _process_message(msg, tracer, state)
                if conversation_id_holder is not None and state.conversation_id:
                    conversation_id_holder[0] = state.conversation_id
            except Exception:
                # Never let span bookkeeping break the user's stream.
                logger.exception("claude_agent_sdk OTel span processing failed")
            yield msg
    except Exception as exc:
        root.set_status(StatusCode.ERROR, str(exc))
        root.record_exception(exc)
        raise
    finally:
        _finalize_turn(root, state)
        otel_context.detach(token)


def _patched_process_query_wrapper(settings: IntegrationSettings) -> Any:
    """Wrap ``InternalClient.process_query`` (the async-gen behind ``query()``)."""

    def wrapper(original_process_query: Any) -> Any:
        @wraps(original_process_query)
        async def wrapped_process_query(
            self_client: Any,
            prompt: Any,
            options: Any,
            transport: Any = None,
        ) -> AsyncIterator[Any]:
            inner = original_process_query(
                self_client, prompt=prompt, options=options, transport=transport
            )
            if should_disable_weave():
                async for msg in inner:
                    yield msg
                return
            user_prompt = prompt if isinstance(prompt, str) else None
            async for msg in _trace_turn(inner, user_prompt=user_prompt):
                yield msg

        return wrapped_process_query

    return wrapper


def _patched_init_wrapper(settings: IntegrationSettings) -> Any:
    """Wrap ``ClaudeSDKClient.__init__`` to trace each ``receive_response`` turn.

    ``ClaudeSDKClient`` builds its own ``Query`` and does NOT route through
    ``InternalClient.process_query``, so this is the only place the multi-turn
    client path is observed — no double-counting with the ``query()`` wrapper.
    """

    def wrapper(original_init: Any) -> Any:
        @wraps(original_init)
        def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)

            original_query = self.query
            original_receive_response = self.receive_response
            # One-element holder so wrapped_query can hand the prompt to the
            # next receive_response() turn.
            user_prompt_holder: list[str | None] = [None]
            # Persists the SDK session_id across turns: system/init is only sent
            # on the first turn, so later turns inherit the conversation id here.
            conversation_id_holder: list[str] = [""]

            @wraps(original_query)
            async def wrapped_query(prompt: Any, session_id: str = "default") -> None:
                user_prompt_holder[0] = prompt if isinstance(prompt, str) else None
                return await original_query(prompt, session_id=session_id)

            @wraps(original_receive_response)
            async def wrapped_receive_response() -> AsyncIterator[Any]:
                inner = original_receive_response()
                if should_disable_weave():
                    async for msg in inner:
                        yield msg
                    return
                async for msg in _trace_turn(
                    inner,
                    user_prompt=user_prompt_holder[0],
                    conversation_id_holder=conversation_id_holder,
                ):
                    yield msg

            self.query = wrapped_query
            self.receive_response = wrapped_receive_response

        return patched_init

    return wrapper


def get_claude_agent_sdk_otel_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _claude_agent_sdk_otel_patcher  # noqa: PLW0603
    if _claude_agent_sdk_otel_patcher is not None:
        return _claude_agent_sdk_otel_patcher

    _claude_agent_sdk_otel_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk._internal.client"),
                "InternalClient.process_query",
                _patched_process_query_wrapper(settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk"),
                "ClaudeSDKClient.__init__",
                _patched_init_wrapper(settings),
            ),
        ]
    )

    return _claude_agent_sdk_otel_patcher
