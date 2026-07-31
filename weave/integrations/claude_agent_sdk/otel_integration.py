"""Weave GenAI agent tracing for the Claude Agent SDK.

Uses the Weave Python GenAI agent SDK to emit spans to Weave's Agents tab; the
sibling ``claude_agent_sdk_integration.py`` emits legacy Weave calls instead.
The dispatcher selects this variant when ``WEAVE_USE_OTEL_V2`` is set.

Each ``query()`` call / ``ClaudeSDKClient`` turn becomes an ``invoke_agent``
span, with a child ``chat`` span per model response and an ``execute_tool``
span per tool call. The SDK reports token usage only on the final
``ResultMessage``, so it is attached to the last ``chat`` span.

The Claude Agent SDK has no agent-name concept, so ``invoke_agent`` spans
default to ``claude_agent_sdk``. Users relabel them for a block of work with the
generic ``weave.conversation.agent_name_override(...)`` context manager; the name is
resolved per turn at span creation, so it is robust to (implicit) patch timing
and correct under concurrent async queries.
"""

from __future__ import annotations

import importlib
import json
import logging
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

from weave.conversation import LLM, Conversation, Message, Reasoning, Tool, Turn, Usage
from weave.conversation.agent_context import resolve_agent_name
from weave.conversation.types import (
    BlobPart,
    MessagePart,
    TextPart,
    ToolCallPart,
    UriPart,
)
from weave.integrations.claude_agent_sdk.usage import total_input_tokens
from weave.integrations.integration_metadata import library_integration
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.settings import should_disable_weave

logger = logging.getLogger(__name__)

_DEFAULT_AGENT_NAME = "claude_agent_sdk"
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


def _message_from_prompt(prompt: dict[str, Any]) -> Message | None:
    if prompt.get("type") != "user":
        return None
    raw_message = prompt.get("message")
    if not isinstance(raw_message, dict):
        return None
    content = raw_message.get("content")
    if isinstance(content, str):
        return Message.user(content)
    if not isinstance(content, list):
        return None

    parts: list[MessagePart] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(TextPart(content=block["text"]))
            continue
        if block.get("type") != "image":
            continue
        source = block.get("source")
        if not isinstance(source, dict):
            continue
        if source.get("type") == "base64" and isinstance(source.get("data"), str):
            media_type = source.get("media_type")
            parts.append(
                BlobPart(
                    mime_type=media_type if isinstance(media_type, str) else "",
                    modality="image",
                    content=source["data"],
                )
            )
        elif source.get("type") == "url" and isinstance(source.get("url"), str):
            media_type = source.get("media_type")
            parts.append(
                UriPart(
                    mime_type=media_type if isinstance(media_type, str) else "",
                    modality="image",
                    uri=source["url"],
                )
            )

    if len(parts) == 1 and isinstance(parts[0], TextPart):
        return Message.user(parts[0].content)
    return Message(role="user", parts=parts) if parts else None


async def _track_prompt(
    prompt: AsyncIterable[dict[str, Any]],
    input_messages: list[Message],
) -> AsyncIterator[dict[str, Any]]:
    async for message in prompt:
        try:
            traced_message = _message_from_prompt(message)
            if traced_message is not None:
                input_messages.append(traced_message)
        except Exception:
            logger.exception("claude_agent_sdk input tracing failed")
        yield message


def _usage_from_result(usage: dict[str, Any] | None) -> Usage:
    """Build a Usage from a ResultMessage's aggregate usage dict."""
    raw = usage or {}
    return Usage(
        input_tokens=total_input_tokens(raw),
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

    conversation: Conversation
    turn: Turn
    model: str = ""
    final_text: str = ""
    is_error: bool = False
    accumulated: list[Message] = field(default_factory=list)
    pending_thinking: list[str] = field(default_factory=list)
    pending_chat: LLM | None = None
    open_tools: dict[str, Tool] = field(default_factory=dict)


def _flush_pending_chat(state: _TurnState, *, usage: Usage | None = None) -> None:
    """Record optional aggregate usage on the deferred chat and end it."""
    pending = state.pending_chat
    if pending is None:
        return
    try:
        with pending:
            if usage is not None:
                pending.record(usage=usage)
    finally:
        state.pending_chat = None


def _process_message(msg: Any, state: _TurnState) -> str | None:
    """Handle one streamed message and return a newly observed SDK session ID."""
    if isinstance(msg, SystemMessage):
        session_id = (msg.data or {}).get("session_id")
        if isinstance(session_id, str) and session_id:
            state.conversation.conversation_id = session_id
            return session_id
        return None

    if isinstance(msg, AssistantMessage):
        # Buffer thinking-only messages so extended-thinking deltas fold into
        # the next response's chat span rather than spawning an empty one.
        if all(isinstance(b, ThinkingBlock) for b in msg.content) and msg.content:
            state.pending_thinking.extend(b.thinking for b in msg.content)
            return None

        # A new response means the previous chat span is done (no usage — only
        # the final one carries the aggregate usage).
        _flush_pending_chat(state)
        if msg.model:
            state.model = msg.model

        output = _assistant_output_message(msg, state.pending_thinking)
        state.pending_thinking.clear()
        if output.text:
            state.final_text = output.text

        chat = state.turn.start_llm(
            model=msg.model or "",
            provider_name=_PROVIDER_NAME,
        )
        state.pending_chat = chat
        chat.record(
            input_messages=list(state.accumulated),
            output_messages=[output.message],
            reasoning=output.reasoning if output.reasoning.content else None,
        )
        state.accumulated.append(output.message)

        for block in msg.content:
            if isinstance(block, ToolUseBlock):
                tool = state.turn.start_tool(
                    name=block.name,
                    arguments=json.dumps(block.input, default=str),
                    tool_call_id=block.id,
                )
                tool.started_at = datetime.now(timezone.utc)
                state.open_tools[block.id] = tool
        return None

    if isinstance(msg, UserMessage):
        content = msg.content if isinstance(msg.content, list) else []
        for block in content:
            if not isinstance(block, ToolResultBlock):
                continue
            state.accumulated.append(
                Message.tool_result(block.tool_use_id, block.content)
            )
            open_tool = state.open_tools.get(block.tool_use_id)
            if open_tool is None:
                continue
            del state.open_tools[block.tool_use_id]
            with open_tool:
                open_tool.result = str(block.content)
                if block.is_error:
                    open_tool._record_otel_error(  # pyright: ignore[reportPrivateUsage]
                        RuntimeError("tool reported an error")
                    )
        return None

    if isinstance(msg, ResultMessage):
        _flush_pending_chat(state, usage=_usage_from_result(msg.usage))
        if msg.result:
            state.final_text = msg.result
        if msg.is_error:
            state.is_error = True
        return None

    return None


def _finalize_turn(state: _TurnState) -> None:
    """Close open children and record terminal fields on the turn."""
    _flush_pending_chat(state)
    for tool in state.open_tools.values():
        with tool:
            pass
    state.open_tools.clear()

    state.turn.record(
        model=state.model,
        output_messages=[Message(role="assistant", content=state.final_text)]
        if state.final_text
        else None,
    )
    if state.is_error:
        state.turn._record_otel_error(  # pyright: ignore[reportPrivateUsage]
            RuntimeError(state.final_text or "agent run failed")
        )


async def _trace_turn(
    messages: AsyncIterator[Any],
    *,
    input_messages: list[Message],
    conversation_id_holder: list[str] | None = None,
) -> AsyncIterator[Any]:
    """Wrap a message stream, emitting the span tree for one turn.

    ``conversation_id_holder`` carries the SDK ``session_id`` across turns of a
    single ``ClaudeSDKClient``: the ``system/init`` message (which holds the
    session_id) is only sent on the first turn, so later turns must inherit it.
    """
    agent_name = resolve_agent_name(_DEFAULT_AGENT_NAME)
    conversation_id = (
        conversation_id_holder[0] if conversation_id_holder is not None else ""
    )
    with Conversation(
        conversation_id=conversation_id,
        agent_name=agent_name,
        continue_parent_trace=True,
        attributes=_INTEGRATION_OTEL_ATTRS,
    ) as conversation:
        with conversation.start_turn() as turn:
            state = _TurnState(
                conversation=conversation,
                turn=turn,
            )
            try:
                async for msg in messages:
                    try:
                        session_id = _process_message(msg, state)
                        if conversation_id_holder is not None and session_id:
                            conversation_id_holder[0] = session_id
                    except Exception:
                        # Never let span bookkeeping break the user's stream.
                        logger.exception(
                            "claude_agent_sdk GenAI span processing failed"
                        )
                    yield msg
            finally:
                state.turn.record(messages=list(input_messages))
                _finalize_turn(state)


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
            if should_disable_weave():
                inner = original_process_query(
                    self_client, prompt=prompt, options=options, transport=transport
                )
                async for msg in inner:
                    yield msg
                return

            input_messages = [Message.user(prompt)] if isinstance(prompt, str) else []
            traced_prompt = (
                prompt
                if isinstance(prompt, str)
                else _track_prompt(prompt, input_messages)
            )
            inner = original_process_query(
                self_client,
                prompt=traced_prompt,
                options=options,
                transport=transport,
            )
            async for msg in _trace_turn(inner, input_messages=input_messages):
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
            input_messages_holder: list[list[Message]] = [[]]
            # Persists the SDK session_id across turns: system/init is only sent
            # on the first turn, so later turns inherit the conversation id here.
            conversation_id_holder: list[str] = [""]

            @wraps(original_query)
            async def wrapped_query(prompt: Any, session_id: str = "default") -> None:
                input_messages = (
                    [Message.user(prompt)] if isinstance(prompt, str) else []
                )
                input_messages_holder[0] = input_messages
                traced_prompt = (
                    prompt
                    if isinstance(prompt, str)
                    else _track_prompt(prompt, input_messages)
                )
                return await original_query(traced_prompt, session_id=session_id)

            @wraps(original_receive_response)
            async def wrapped_receive_response() -> AsyncIterator[Any]:
                inner = original_receive_response()
                if should_disable_weave():
                    async for msg in inner:
                        yield msg
                    return
                async for msg in _trace_turn(
                    inner,
                    input_messages=input_messages_holder[0],
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
