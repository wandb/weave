"""Weave GenAI agent tracing for the Claude Agent SDK.

Uses the Weave Python GenAI agent SDK to emit spans to Weave's Agents tab; the
sibling ``claude_agent_sdk_integration.py`` emits legacy Weave calls instead.
The dispatcher selects this variant when ``WEAVE_USE_OTEL_V2`` is set.

String queries and ``ClaudeSDKClient.receive_response()`` calls each emit one
``invoke_agent`` turn. A standalone ``query()`` driven by an async prompt
iterable can return several results, so that path emits one turn per
``ResultMessage``. Each turn has a child ``chat`` span per model response and an
``execute_tool`` span per tool call. The SDK reports token usage only on a
turn's final ``ResultMessage``, so it is attached to the last ``chat`` span.

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
from collections import deque
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

from weave.conversation import (
    LLM,
    Conversation,
    Message,
    Reasoning,
    SubAgent,
    Tool,
    Turn,
    Usage,
)
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
_SUBAGENT_TOOL_NAMES = {"Agent", "Task"}
_TASK_STATUS_ATTRIBUTE = "claude_agent_sdk.task.status"
_TASK_ERROR_STATUSES = {"failed", "stopped"}

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
class _PendingTurnInput:
    messages: list[Message]
    started_at: datetime


def _text_turn_input(prompt: str) -> _PendingTurnInput:
    return _PendingTurnInput(
        messages=[Message.user(prompt)],
        started_at=datetime.now(timezone.utc),
    )


@dataclass(slots=True)
class _InputTracker:
    """FIFO queue of user inputs, one entry per turn the SDK will answer."""

    pending: deque[_PendingTurnInput] = field(default_factory=deque)
    buffered: list[Message] = field(default_factory=list)
    buffered_started_at: datetime | None = None

    @classmethod
    def from_prompt(cls, prompt: Any) -> _InputTracker:
        tracker = cls()
        if isinstance(prompt, str):
            tracker.pending.append(_text_turn_input(prompt))
        return tracker

    def record(self, prompt: dict[str, Any]) -> None:
        message = _message_from_prompt(prompt)
        if message is None:
            return
        if self.buffered_started_at is None:
            self.buffered_started_at = datetime.now(timezone.utc)
        self.buffered.append(message)
        # ``shouldQuery: False`` means the SDK keeps collecting input instead of
        # answering, so those messages belong to the next turn's input.
        if prompt.get("shouldQuery") is not False:
            self.pending.append(
                _PendingTurnInput(
                    messages=self.buffered,
                    started_at=self.buffered_started_at,
                )
            )
            self.buffered = []
            self.buffered_started_at = None

    def take(self) -> _PendingTurnInput:
        if self.pending:
            return self.pending.popleft()
        if self.buffered:
            pending = _PendingTurnInput(
                messages=self.buffered,
                started_at=self.buffered_started_at or datetime.now(timezone.utc),
            )
            self.buffered = []
            self.buffered_started_at = None
            return pending
        return _PendingTurnInput(
            messages=[],
            started_at=datetime.now(timezone.utc),
        )

    def has_pending_turn(self) -> bool:
        """Return whether a submitted input still expects an SDK result."""
        return bool(self.pending)


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


async def _track_async_prompt(
    prompt: AsyncIterable[dict[str, Any]],
    tracker: _InputTracker,
) -> AsyncIterator[dict[str, Any]]:
    async for message in prompt:
        try:
            tracker.record(message)
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
                ToolCallPart(
                    id=block.id,
                    name=block.name,
                    arguments=json.dumps(
                        block.input,
                        ensure_ascii=False,
                        default=str,
                    ),
                )
            )
    text = "\n".join(text_chunks)
    reasoning = Reasoning(
        content="\n".join(chunk for chunk in thinking_chunks if chunk)
    )
    message = Message.assistant(text=text, tool_calls=tool_calls or None)
    return _AssistantOutput(message=message, text=text, reasoning=reasoning)


def _tool_result_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text = "\n".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if text:
            return text
    return json.dumps(content, ensure_ascii=False, default=str)


def _async_launch_payload(content: Any) -> dict[str, Any] | None:
    candidates = content if isinstance(content, list) else [content]
    for candidate in candidates:
        payload = candidate
        if isinstance(candidate, dict) and candidate.get("type") == "text":
            payload = candidate.get("text")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(payload, dict) and payload.get("status") == "async_launched":
            return payload
    return None


def _nonempty_string(value: Any) -> str:
    return value if isinstance(value, str) and value else ""


_SpanParent = Turn | SubAgent


@dataclass(slots=True)
class _OpenSubagent:
    span: SubAgent
    background: bool = False


@dataclass(slots=True)
class _TurnState:
    """Mutable per-turn accumulator (one invoke_agent span and its children).

    Not frozen: it accumulates as the message stream is consumed. Its scope is
    one turn, regardless of which query adapter owns that turn.
    """

    conversation: Conversation
    turn: Turn
    model: str = ""
    final_text: str = ""
    is_error: bool = False
    accumulated: dict[str | None, list[Message]] = field(default_factory=dict)
    pending_thinking: dict[str | None, list[str]] = field(default_factory=dict)
    pending_chat: LLM | None = None
    open_tools: dict[str, Tool] = field(default_factory=dict)
    open_subagents: dict[str, _OpenSubagent] = field(default_factory=dict)
    task_tool_use_ids: dict[str, str] = field(default_factory=dict)


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


def _start_subagent(
    block: ToolUseBlock,
    parent: _SpanParent,
    state: _TurnState,
) -> None:
    raw_input = block.input if isinstance(block.input, dict) else {}
    name = next(
        (
            value
            for key in ("subagent_type", "name")
            if isinstance(value := raw_input.get(key), str) and value
        ),
        "subagent",
    )
    model = raw_input.get("model")
    description = raw_input.get("description")
    prompt = raw_input.get("prompt")
    subagent = parent.start_subagent(
        name=name,
        model=model if isinstance(model, str) else "",
    )
    subagent.record(
        agent_description=description if isinstance(description, str) else None,
        input_messages=[Message.user(prompt)]
        if isinstance(prompt, str) and prompt
        else [],
        tool_name=block.name,
        tool_call_id=block.id,
        tool_call_arguments=json.dumps(
            block.input,
            ensure_ascii=False,
            default=str,
        ),
    )
    # Parallel delegations finish in completion order, not launch order.
    subagent.start(set_current=False)
    state.open_subagents[block.id] = _OpenSubagent(
        span=subagent,
        background=raw_input.get("run_in_background") is True,
    )


def _span_parent(msg: AssistantMessage, state: _TurnState) -> _SpanParent:
    parent_tool_use_id = msg.parent_tool_use_id
    if parent_tool_use_id is None:
        return state.turn
    open_subagent = state.open_subagents.get(parent_tool_use_id)
    if open_subagent is None:
        subagent = state.turn.start_subagent(
            name="subagent",
            model=msg.model or "",
        )
        subagent.start(set_current=False)
        subagent.set_attributes({"gen_ai.tool.call.id": parent_tool_use_id})
        state.open_subagents[parent_tool_use_id] = _OpenSubagent(span=subagent)
    elif msg.model:
        subagent = open_subagent.span
        subagent.record(model=msg.model)
    else:
        subagent = open_subagent.span
    return subagent


def _task_tool_use_id(data: dict[str, Any], state: _TurnState) -> str:
    task_id = _nonempty_string(data.get("task_id"))
    tool_use_id = _nonempty_string(data.get("tool_use_id"))
    if task_id and tool_use_id:
        state.task_tool_use_ids[task_id] = tool_use_id
    elif task_id:
        tool_use_id = state.task_tool_use_ids.get(task_id, "")
    return tool_use_id


def _record_task_identity(data: dict[str, Any], state: _TurnState) -> None:
    task_id = _nonempty_string(data.get("task_id"))
    tool_use_id = _task_tool_use_id(data, state)
    if not tool_use_id:
        return
    open_subagent = state.open_subagents.get(tool_use_id)
    if open_subagent is None:
        return
    open_subagent.background = True
    if task_id:
        open_subagent.span.record(agent_id=task_id)


def _discard_task_mappings(tool_use_id: str, state: _TurnState) -> None:
    state.task_tool_use_ids = {
        task_id: mapped_tool_use_id
        for task_id, mapped_tool_use_id in state.task_tool_use_ids.items()
        if mapped_tool_use_id != tool_use_id
    }


def _finish_task_notification(data: dict[str, Any], state: _TurnState) -> None:
    task_id = _nonempty_string(data.get("task_id"))
    tool_use_id = _task_tool_use_id(data, state)
    if not tool_use_id:
        return
    open_subagent = state.open_subagents.get(tool_use_id)
    if open_subagent is None:
        return

    _flush_pending_chat(state)
    summary = _nonempty_string(data.get("summary"))
    status = _nonempty_string(data.get("status"))
    open_subagent.span.record(
        agent_id=task_id or None,
        output_messages=[Message.assistant(summary)] if summary else [],
        tool_call_result=summary,
    )
    if status:
        open_subagent.span.set_attributes({_TASK_STATUS_ATTRIBUTE: status})
    if status in _TASK_ERROR_STATUSES:
        open_subagent.span.record_error(RuntimeError(f"background subagent {status}"))
    open_subagent.span.end()
    del state.open_subagents[tool_use_id]
    _discard_task_mappings(tool_use_id, state)


def _process_system_message(msg: SystemMessage, state: _TurnState) -> str | None:
    data = msg.data if isinstance(msg.data, dict) else {}
    session_id = _nonempty_string(data.get("session_id"))
    if session_id:
        state.conversation.conversation_id = session_id

    if msg.subtype in {"task_started", "task_progress"}:
        _record_task_identity(data, state)
    elif msg.subtype == "task_notification":
        _finish_task_notification(data, state)
    return session_id or None


def _record_background_launch(
    tool_use_id: str,
    payload: dict[str, Any] | None,
    state: _TurnState,
) -> None:
    open_subagent = state.open_subagents.get(tool_use_id)
    if open_subagent is None:
        return
    open_subagent.background = True
    if payload is None:
        return
    task_id = next(
        (
            value
            for key in ("agentId", "taskId", "task_id")
            if (value := _nonempty_string(payload.get(key)))
        ),
        "",
    )
    if task_id:
        state.task_tool_use_ids[task_id] = tool_use_id
        open_subagent.span.record(agent_id=task_id)


def _process_message(msg: Any, state: _TurnState) -> str | None:
    """Handle one streamed message and return a newly observed SDK session ID."""
    if isinstance(msg, SystemMessage):
        return _process_system_message(msg, state)

    if isinstance(msg, AssistantMessage):
        parent_tool_use_id = msg.parent_tool_use_id
        # Buffer thinking-only messages so extended-thinking deltas fold into
        # the next response's chat span rather than spawning an empty one.
        thinking_blocks = [
            block for block in msg.content if isinstance(block, ThinkingBlock)
        ]
        if thinking_blocks and len(thinking_blocks) == len(msg.content):
            state.pending_thinking.setdefault(parent_tool_use_id, []).extend(
                block.thinking for block in thinking_blocks
            )
            return None

        # A new response means the previous chat span is done (no usage — only
        # the final one carries the aggregate usage).
        _flush_pending_chat(state)
        if parent_tool_use_id is None and msg.model:
            state.model = msg.model

        output = _assistant_output_message(
            msg,
            state.pending_thinking.pop(parent_tool_use_id, []),
        )
        if parent_tool_use_id is None and output.text:
            state.final_text = output.text

        parent = _span_parent(msg, state)
        chat = parent.start_llm(
            model=msg.model or "",
            provider_name=_PROVIDER_NAME,
        )
        state.pending_chat = chat
        accumulated = state.accumulated.setdefault(parent_tool_use_id, [])
        chat.record(
            input_messages=list(accumulated),
            output_messages=[output.message],
            reasoning=output.reasoning if output.reasoning.content else None,
        )
        accumulated.append(output.message)

        for block in msg.content:
            if isinstance(block, ToolUseBlock):
                if block.name in _SUBAGENT_TOOL_NAMES:
                    _start_subagent(block, parent, state)
                    continue
                tool = parent.start_tool(
                    name=block.name,
                    arguments=json.dumps(block.input, default=str),
                    tool_call_id=block.id,
                )
                tool.started_at = datetime.now(timezone.utc)
                state.open_tools[block.id] = tool
        return None

    if isinstance(msg, UserMessage):
        content = msg.content if isinstance(msg.content, list) else []
        accumulated = state.accumulated.setdefault(msg.parent_tool_use_id, [])
        for block in content:
            if not isinstance(block, ToolResultBlock):
                continue
            result_text = _tool_result_text(block.content)
            accumulated.append(Message.tool_result(block.tool_use_id, result_text))
            open_subagent = state.open_subagents.get(block.tool_use_id)
            if open_subagent is not None:
                launch_payload = _async_launch_payload(block.content)
                if not block.is_error and (
                    open_subagent.background or launch_payload is not None
                ):
                    _record_background_launch(
                        block.tool_use_id,
                        launch_payload,
                        state,
                    )
                    continue
                open_subagent.span.record(
                    output_messages=[Message.assistant(result_text)]
                    if result_text
                    else [],
                    tool_call_result=result_text,
                )
                if block.is_error:
                    open_subagent.span.record_error(
                        RuntimeError("subagent reported an error")
                    )
                open_subagent.span.end()
                del state.open_subagents[block.tool_use_id]
                _discard_task_mappings(block.tool_use_id, state)
                continue
            open_tool = state.open_tools.get(block.tool_use_id)
            if open_tool is None:
                continue
            del state.open_tools[block.tool_use_id]
            with open_tool:
                open_tool.result = result_text
                if block.is_error:
                    open_tool.record_error(RuntimeError("tool reported an error"))
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
    for open_subagent in state.open_subagents.values():
        open_subagent.span.end()
    state.open_subagents.clear()
    state.task_tool_use_ids.clear()

    state.turn.record(
        model=state.model,
        output_messages=[Message(role="assistant", content=state.final_text)]
        if state.final_text
        else None,
    )
    if state.is_error:
        state.turn.record_error(RuntimeError(state.final_text or "agent run failed"))


def _start_tracked_turn(
    conversation: Conversation, turn_input: _PendingTurnInput
) -> Turn:
    # Resolve per turn so an ``agent_name_override(...)`` block that spans only
    # part of the stream labels only the turns inside it.
    turn = conversation.start_turn(agent_name=resolve_agent_name(_DEFAULT_AGENT_NAME))
    turn.started_at = turn_input.started_at
    turn.record(messages=turn_input.messages)
    return turn


def _process_message_for_turn(
    msg: Any,
    state: _TurnState,
    conversation_id_holder: list[str] | None = None,
) -> None:
    """Record one SDK message without allowing tracing to break the stream."""
    try:
        session_id = _process_message(msg, state)
        if conversation_id_holder is not None and session_id:
            conversation_id_holder[0] = session_id
    except Exception:
        logger.exception("claude_agent_sdk GenAI span processing failed")


async def _trace_single_turn(
    messages: AsyncIterator[Any],
    *,
    turn_input: _PendingTurnInput,
    conversation_id_holder: list[str] | None = None,
) -> AsyncIterator[Any]:
    """Trace a stream whose public API contract permits exactly one result.

    ``conversation_id_holder`` carries the SDK ``session_id`` across turns of a
    single ``ClaudeSDKClient``: the ``system/init`` message (which holds the
    session_id) is only sent on the first turn, so later turns must inherit it.
    """
    message_iterator = aiter(messages)
    conversation_id = (
        conversation_id_holder[0] if conversation_id_holder is not None else ""
    )
    with Conversation(
        conversation_id=conversation_id,
        agent_name=_DEFAULT_AGENT_NAME,
        continue_parent_trace=True,
        attributes=_INTEGRATION_OTEL_ATTRS,
    ) as conversation:
        turn = _start_tracked_turn(conversation, turn_input)
        with turn:
            state = _TurnState(conversation=conversation, turn=turn)
            try:
                async for msg in message_iterator:
                    _process_message_for_turn(
                        msg,
                        state,
                        conversation_id_holder,
                    )
                    yield msg
                    if isinstance(msg, ResultMessage):
                        break
            finally:
                _finalize_turn(state)

    # A ResultMessage completes the one allowed turn. Continue forwarding any
    # teardown messages or errors without retroactively changing that turn.
    async for msg in message_iterator:
        yield msg


async def _trace_async_iterable_query(
    messages: AsyncIterator[Any],
    *,
    inputs: _InputTracker,
) -> AsyncIterator[Any]:
    """Trace every result produced by a standalone async-iterable query.

    Unlike the single-turn APIs, this output stream may contain several
    ``ResultMessage`` boundaries. Looking ahead between turns keeps transport
    failures after a completed result out of that completed turn while still
    assigning failures to an already-submitted next input.
    """
    with Conversation(
        conversation_id="",
        agent_name=_DEFAULT_AGENT_NAME,
        continue_parent_trace=True,
        attributes=_INTEGRATION_OTEL_ATTRS,
    ) as conversation:
        message_iterator = aiter(messages)
        deferred_init_messages: list[Any] = []
        while True:
            try:
                next_message = await anext(message_iterator)
            except StopAsyncIteration:
                return
            except BaseException:
                if not inputs.has_pending_turn():
                    raise
                turn = _start_tracked_turn(conversation, inputs.take())
                with turn:
                    state = _TurnState(conversation=conversation, turn=turn)
                    try:
                        for msg in deferred_init_messages:
                            _process_message_for_turn(msg, state)
                        raise
                    finally:
                        _finalize_turn(state)

            # Input tracking happens before the SDK writes each prompt, but the
            # bootstrap init can arrive before the first prompt is consumed.
            if not inputs.has_pending_turn():
                if (
                    isinstance(next_message, SystemMessage)
                    and next_message.subtype == "init"
                ):
                    deferred_init_messages.append(next_message)
                yield next_message
                continue

            turn = _start_tracked_turn(conversation, inputs.take())
            with turn:
                state = _TurnState(conversation=conversation, turn=turn)
                try:
                    for msg in deferred_init_messages:
                        _process_message_for_turn(msg, state)
                    deferred_init_messages.clear()
                    while True:
                        msg = next_message
                        _process_message_for_turn(msg, state)
                        yield msg
                        if isinstance(msg, ResultMessage):
                            break
                        try:
                            next_message = await anext(message_iterator)
                        except StopAsyncIteration:
                            return
                finally:
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

            if isinstance(prompt, str):
                inner = original_process_query(
                    self_client,
                    prompt=prompt,
                    options=options,
                    transport=transport,
                )
                async for msg in _trace_single_turn(
                    inner,
                    turn_input=_text_turn_input(prompt),
                ):
                    yield msg
                return

            inputs = _InputTracker()
            inner = original_process_query(
                self_client,
                prompt=_track_async_prompt(prompt, inputs),
                options=options,
                transport=transport,
            )
            async for msg in _trace_async_iterable_query(inner, inputs=inputs):
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
            input_tracker_holder: list[_InputTracker] = [_InputTracker()]
            # Persists the SDK session_id across turns: system/init is only sent
            # on the first turn, so later turns inherit the conversation id here.
            conversation_id_holder: list[str] = [""]

            @wraps(original_query)
            async def wrapped_query(prompt: Any, session_id: str = "default") -> None:
                inputs = _InputTracker.from_prompt(prompt)
                input_tracker_holder[0] = inputs
                traced_prompt = (
                    prompt
                    if isinstance(prompt, str)
                    else _track_async_prompt(prompt, inputs)
                )
                return await original_query(traced_prompt, session_id=session_id)

            @wraps(original_receive_response)
            async def wrapped_receive_response() -> AsyncIterator[Any]:
                inner = original_receive_response()
                if should_disable_weave():
                    async for msg in inner:
                        yield msg
                    return
                async for msg in _trace_single_turn(
                    inner,
                    turn_input=input_tracker_holder[0].take(),
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
