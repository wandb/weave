"""OTel-emitting variant of the Claude Agent SDK integration.

Sibling of ``claude_agent_sdk_integration.py`` (the calls-based variant).
Emits OpenTelemetry spans using GenAI semantic conventions to Weave's
Agents tab — the OTLP traces endpoint configured by ``weave.init()`` via
``_setup_session_tracing``. Mirrors the OpenAI Agents v2 OTel processor.

Span model ("option C"):

    invoke_agent              one per query() call / per ClaudeSDKClient turn
      ├── chat                one per assistant model response. The aggregate
      │                       token usage (only reported on the final
      │                       ResultMessage) is attached to the LAST chat span.
      └── execute_tool        one per tool_use block, closed on its tool_result

Why this shape: the Claude Agent SDK only reports usage/cost in aggregate on
the final ``ResultMessage`` (never per assistant message), so per-call usage
is unknowable. Attributing the aggregate to the final chat span keeps the
token/cost roll-up correct while preserving the turn-by-turn chat structure
the Agents tab is built around. ``total_cost_usd`` has no GenAI semconv field,
so it rides a ``weave.claude_agent_sdk.*`` attribute on the root span.

Trace isolation: by default each turn nests under the ambient OTel context
(``continue_parent_trace`` semantics), so a turn run inside a Weave-traced
application joins that trace. Set ``WEAVE_CLAUDE_AGENT_SDK_ISOLATED_TRACES=1``
to force one isolated trace per turn instead (matching the Session SDK
``Turn`` default). When no ambient span is active the two are identical.

Tool capture is message-stream based (ToolUseBlock -> ToolResultBlock): the
chat span is built from the same stream, so the tool_use blocks are already
in hand — a single source of truth, no ``options.hooks`` mutation, and the
existing replay cassettes drive it unchanged. The SDK's PreToolUse/PostToolUse
hooks would only add tighter tool timing and explicit failure events; that is
a deferred, additive enhancement, not a replacement.
"""

from __future__ import annotations

import dataclasses
import importlib
import logging
import os
from collections.abc import AsyncIterator
from functools import wraps
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.context import Context
from opentelemetry.trace import StatusCode

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

# weave.* attrs for data that has no GenAI semconv home.
_COST_ATTR = "weave.claude_agent_sdk.cost.total_usd"
_NUM_TURNS_ATTR = "weave.claude_agent_sdk.num_turns"
_DURATION_MS_ATTR = "weave.claude_agent_sdk.duration_ms"

# When set to a truthy value, force one isolated OTel trace per turn instead of
# nesting under the ambient context. See the module docstring.
_ISOLATED_TRACES_ENV = "WEAVE_CLAUDE_AGENT_SDK_ISOLATED_TRACES"
_TRUTHY = {"1", "true", "yes", "on"}

_claude_agent_sdk_otel_patcher: MultiPatcher | None = None


def _tracer() -> Any:
    return otel_trace.get_tracer(_TRACER_NAME)


def _isolated_traces() -> bool:
    """Whether each turn should start its own trace (default: no -> ambient)."""
    return os.environ.get(_ISOLATED_TRACES_ENV, "").strip().lower() in _TRUTHY


def _root_context() -> Context | None:
    """Parent context for a turn's root invoke_agent span.

    ``None`` -> use the current (ambient) context so the turn nests under any
    active span. An empty ``Context()`` -> force a brand-new trace root.
    """
    return Context() if _isolated_traces() else None


def _usage_from_result(usage: dict[str, Any] | None) -> Usage:
    """Build a Usage from a ResultMessage's aggregate usage dict."""
    u = usage or {}
    return Usage(
        input_tokens=int(u.get("input_tokens", 0) or 0),
        output_tokens=int(u.get("output_tokens", 0) or 0),
        cache_creation_input_tokens=int(u.get("cache_creation_input_tokens", 0) or 0),
        cache_read_input_tokens=int(u.get("cache_read_input_tokens", 0) or 0),
    )


def _assistant_output_message(
    msg: Any, buffered_thinking: list[str]
) -> tuple[Message, str, Reasoning]:
    """Build the chat span's output Message from an assistant message.

    Returns ``(output_message, plain_text, reasoning)``. ``buffered_thinking``
    holds thinking text from preceding thinking-only assistant messages so it
    folds into this response's reasoning rather than splitting into its own
    chat span.
    """
    from claude_agent_sdk import TextBlock, ThinkingBlock, ToolUseBlock

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
    reasoning = Reasoning(content="\n".join(c for c in thinking_chunks if c))
    out = Message.assistant(text=text, tool_calls=tool_calls or None)
    return out, text, reasoning


@dataclasses.dataclass
class _TurnState:
    """Mutable per-turn accumulator (one invoke_agent span and its children).

    Intentionally not frozen: it accumulates as the message stream is consumed.
    Scope is one turn, owned by ``_trace_turn``.
    """

    user_prompt: str | None
    conversation_id: str = ""
    model: str = ""
    final_text: str = ""
    is_error: bool = False
    accumulated: list[Message] = dataclasses.field(default_factory=list)
    pending_thinking: list[str] = dataclasses.field(default_factory=list)
    # (otel_span, attrs) for the most recent chat span, whose end is deferred so
    # the aggregate usage from ResultMessage can be attached before it closes.
    pending_chat: tuple[Any, dict[str, Any]] | None = None
    # tool_use_id -> (otel_span, tool_name) for in-flight execute_tool spans.
    open_tool_spans: dict[str, tuple[Any, str]] = dataclasses.field(
        default_factory=dict
    )


def _flush_pending_chat(state: _TurnState, *, usage: Usage | None = None) -> None:
    """Set attrs (optionally usage) on the deferred chat span and end it."""
    if state.pending_chat is None:
        return
    span, attrs = state.pending_chat
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
    for k, v in attrs.items():
        span.set_attribute(k, v)
    span.end()
    state.pending_chat = None


def _process_message(msg: Any, tracer: Any, state: _TurnState) -> None:
    """Handle one streamed message, creating/closing child spans as needed."""
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

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

        out_msg, text, reasoning = _assistant_output_message(
            msg, state.pending_thinking
        )
        state.pending_thinking.clear()
        if text:
            state.final_text = text

        chat = tracer.start_span(f"chat {msg.model or ''}".rstrip())
        chat_attrs = llm_attributes(
            model=msg.model or "",
            provider_name=_PROVIDER_NAME,
            conversation_id=state.conversation_id,
            input_messages=list(state.accumulated),
            output_messages=[out_msg],
            reasoning=reasoning if reasoning.content else None,
        )
        state.pending_chat = (chat, chat_attrs)
        state.accumulated.append(out_msg)

        for block in msg.content:
            if isinstance(block, ToolUseBlock):
                tool_span = tracer.start_span(f"execute_tool {block.name}")
                state.open_tool_spans[block.id] = (tool_span, block.name)
        return

    if isinstance(msg, UserMessage):
        content = msg.content if isinstance(msg.content, list) else []
        for block in content:
            if not isinstance(block, ToolResultBlock):
                continue
            state.accumulated.append(
                Message.tool_result(block.tool_use_id, block.content)
            )
            entry = state.open_tool_spans.pop(block.tool_use_id, None)
            if entry is None:
                continue
            tool_span, tool_name = entry
            attrs = execute_tool_attributes(
                tool_name=tool_name,
                conversation_id=state.conversation_id,
                tool_call_result=str(block.content),
                tool_call_id=block.tool_use_id,
            )
            for k, v in attrs.items():
                tool_span.set_attribute(k, v)
            if block.is_error:
                tool_span.set_status(StatusCode.ERROR, "tool reported an error")
            tool_span.end()
        return

    if isinstance(msg, ResultMessage):
        _flush_pending_chat(state, usage=_usage_from_result(msg.usage))
        if msg.result:
            state.final_text = msg.result
        if msg.is_error:
            state.is_error = True
        return


def _finalize_turn(root: Any, state: _TurnState, result_msg: Any) -> None:
    """Close any open child spans and finish the root invoke_agent span."""
    _flush_pending_chat(state)
    for tool_span, _name in state.open_tool_spans.values():
        tool_span.end()
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
    if result_msg is not None:
        if result_msg.total_cost_usd is not None:
            attrs[_COST_ATTR] = result_msg.total_cost_usd
        if result_msg.num_turns is not None:
            attrs[_NUM_TURNS_ATTR] = result_msg.num_turns
        if result_msg.duration_ms is not None:
            attrs[_DURATION_MS_ATTR] = result_msg.duration_ms
    for k, v in attrs.items():
        root.set_attribute(k, v)
    if state.is_error:
        root.set_status(StatusCode.ERROR, state.final_text or "agent run failed")
    root.end()


async def _trace_turn(
    messages: AsyncIterator[Any],
    *,
    user_prompt: str | None,
    conversation_id_holder: list[str] | None = None,
) -> AsyncIterator[Any]:
    """Wrap a message stream, emitting the option-C span tree for one turn.

    ``conversation_id_holder`` carries the SDK ``session_id`` across turns of a
    single ``ClaudeSDKClient``: the ``system/init`` message (which holds the
    session_id) is only sent on the first turn, so later turns must inherit it.
    """
    from claude_agent_sdk import ResultMessage

    tracer = _tracer()
    root = tracer.start_span("invoke_agent " + _AGENT_NAME, context=_root_context())
    token = otel_context.attach(otel_trace.set_span_in_context(root))
    state = _TurnState(user_prompt=user_prompt)
    if conversation_id_holder and conversation_id_holder[0]:
        state.conversation_id = conversation_id_holder[0]
    result_msg = None
    try:
        async for msg in messages:
            if isinstance(msg, ResultMessage):
                result_msg = msg
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
        _finalize_turn(root, state, result_msg)
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
