from __future__ import annotations

import dataclasses
import importlib
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from weave.integrations.claude_agent_sdk.display_utils import (
    tool_use_display_name,
    turn_display_name,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.context.weave_client_context import get_weave_client

logger = logging.getLogger(__name__)

_claude_agent_sdk_patcher: MultiPatcher | None = None


# ── Shared helpers ───────────────────────────────────────────────────


def _serialize_msg(msg: Any) -> dict[str, Any]:
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        UserMessage,
    )

    d = dataclasses.asdict(msg)
    if isinstance(msg, UserMessage):
        d["role"] = "user"
    elif isinstance(msg, AssistantMessage):
        d["role"] = "assistant"
    elif isinstance(msg, SystemMessage):
        d["role"] = "system"
    elif isinstance(msg, ResultMessage):
        d["role"] = "result"
    return d


# ── Inline message processor ────────────────────────────────────────


def _process_message_inline(
    msg: Any,
    wc: Any,
    root_call: Any,
    state: dict[str, Any],
) -> None:
    """Process a single streamed message, creating/finishing child calls
    in real time so that started_at/ended_at reflect actual latency.

    ``state`` keys:
      - pending_thinking: buffered ThinkingBlock objects
      - open_tool_calls: dict[tool_use_id, Call]
      - response_start_time: datetime when we started waiting for a response
      - accumulated_messages: list of serialized messages (shared history)
      - root_model: first model name seen
    """
    from claude_agent_sdk import (
        AssistantMessage,
        SystemMessage,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    pending_thinking = state["pending_thinking"]
    open_tool_calls = state["open_tool_calls"]
    accumulated = state["accumulated_messages"]

    def _is_thinking_only(m: Any) -> bool:
        return isinstance(m, AssistantMessage) and all(
            isinstance(b, ThinkingBlock) for b in m.content
        )

    # Buffer thinking-only assistant messages
    if _is_thinking_only(msg):
        pending_thinking.extend(msg.content)
        return

    if isinstance(msg, AssistantMessage):
        if state["root_model"] is None and msg.model:
            state["root_model"] = msg.model

        # Merge buffered thinking
        if pending_thinking:
            msg = AssistantMessage(
                content=list(pending_thinking) + list(msg.content),
                model=msg.model,
                parent_tool_use_id=msg.parent_tool_use_id,
                error=msg.error,
            )
            pending_thinking.clear()

        serialized = _serialize_msg(msg)
        history = list(accumulated)
        accumulated.append(serialized)

        tool_uses = [b for b in msg.content if isinstance(b, ToolUseBlock)]

        # Open tool calls
        for tool_block in tool_uses:
            tool_call = wc.create_call(
                op=f"claude_agent_sdk.tool_use.{tool_block.name}",
                inputs={"message": serialized},
                display_name=tool_use_display_name(tool_block.name, tool_block.input),
                parent=root_call,
                attributes={"kind": "tool"},
                use_stack=False,
            )
            open_tool_calls[tool_block.id] = tool_call

    elif isinstance(msg, UserMessage):
        accumulated.append(_serialize_msg(msg))

        # Finish matching tool calls
        content = msg.content if isinstance(msg.content, list) else []
        for block in content:
            if (
                isinstance(block, ToolResultBlock)
                and block.tool_use_id in open_tool_calls
            ):
                tool_call = open_tool_calls.pop(block.tool_use_id)
                wc.finish_call(tool_call, output=dataclasses.asdict(block))

        # Model will respond next — record the start time
        state["response_start_time"] = datetime.now(tz=timezone.utc)

    else:
        # SystemMessage or other types
        accumulated.append(_serialize_msg(msg))
        # Insert user prompt into history after the SystemMessage
        if isinstance(msg, SystemMessage) and state["user_prompt"] is not None:
            accumulated.append({"role": "user", "content": state["user_prompt"]})


def _finalize_stream(
    wc: Any,
    root_call: Any,
    state: dict[str, Any],
    result_msg: Any,
) -> None:
    """Close any open calls and finish the root call."""
    for tc in state["open_tool_calls"].values():
        wc.finish_call(tc, output={})
    state["open_tool_calls"].clear()

    root_output: dict[str, Any] = {
        "status": "completed",
        "messages": state["accumulated_messages"],
    }
    if state["root_model"]:
        root_output["model"] = state["root_model"]

    exception = None
    if result_msg is not None:
        if result_msg.usage:
            root_output["usage"] = result_msg.usage
            # Set summary directly so usage propagates even when tool
            # call children exist (children path skips output-based summary).
            if state["root_model"]:
                root_call.summary = {
                    "usage": {
                        state["root_model"]: {
                            "requests": 1,
                            **result_msg.usage,
                        }
                    }
                }
        if result_msg.total_cost_usd is not None:
            root_output["total_cost_usd"] = result_msg.total_cost_usd
        root_output["duration_ms"] = result_msg.duration_ms
        root_output["num_turns"] = result_msg.num_turns
        if result_msg.result is not None:
            root_output["result"] = result_msg.result
        if result_msg.is_error:
            root_output["status"] = "error"
            exception = Exception(result_msg.result or "Conversation ended with error")

    wc.finish_call(root_call, output=root_output, exception=exception)


def _make_initial_state(user_prompt: str | None = None) -> dict[str, Any]:
    return {
        "pending_thinking": [],
        "open_tool_calls": {},
        "response_start_time": None,
        "accumulated_messages": [],
        "root_model": None,
        "user_prompt": user_prompt,
    }


def _resolve_thread_id() -> tuple[str, bool]:
    """Return (thread_id, already_set).

    If a thread_id is already in context, reuse it.  Otherwise generate
    one in the form ``claude-session-YYYY-MM-DD-HH-MM-SS``.
    """
    from weave.trace.context import call_context

    existing = call_context.get_thread_id()
    if existing is not None:
        return existing, True
    now = datetime.now(tz=timezone.utc)
    return f"claude-session-{now.strftime('%Y-%m-%d-%H-%M-%S')}", False


# ── Patchers ─────────────────────────────────────────────────────────


def _patched_process_query_wrapper(settings: IntegrationSettings) -> Any:
    """Wrap ``InternalClient.process_query`` — the async generator that
    both ``query()`` and ``ClaudeSDKClient`` ultimately delegate to.
    """

    def wrapper(original_process_query: Any) -> Any:
        @wraps(original_process_query)
        async def wrapped_process_query(
            self_client: Any,
            prompt: Any,
            options: Any,
            transport: Any = None,
        ) -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage

            from weave.trace.context import call_context

            wc = get_weave_client()
            if wc is None:
                async for msg in original_process_query(
                    self_client,
                    prompt=prompt,
                    options=options,
                    transport=transport,
                ):
                    yield msg
                return

            user_prompt = prompt if isinstance(prompt, str) else None
            root_inputs: dict[str, Any] = {}
            if user_prompt is not None:
                root_inputs["prompt"] = user_prompt

            thread_id, _ = _resolve_thread_id()

            with call_context.set_thread_id(thread_id):
                root_call = wc.create_call(
                    op="claude_agent_sdk.query",
                    inputs=root_inputs,
                    display_name=turn_display_name(user_prompt),
                    attributes={"kind": "agent"},
                    use_stack=False,
                )

                state = _make_initial_state(user_prompt)
                state["response_start_time"] = datetime.now(tz=timezone.utc)

                result_msg = None
                try:
                    async for msg in original_process_query(
                        self_client,
                        prompt=prompt,
                        options=options,
                        transport=transport,
                    ):
                        if isinstance(msg, ResultMessage):
                            result_msg = msg
                        else:
                            _process_message_inline(msg, wc, root_call, state)
                        yield msg
                finally:
                    _finalize_stream(wc, root_call, state, result_msg)

        return wrapped_process_query

    return wrapper


def _patched_init_wrapper(settings: IntegrationSettings) -> Any:
    """Wrap ``ClaudeSDKClient.__init__`` to create a session-level parent
    call that spans the client lifetime, with each turn as a child.
    """

    def wrapper(original_init: Any) -> Any:
        @wraps(original_init)
        def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)

            self._weave_turn_counter: int = 0
            self._weave_thread_id: str | None = None

            original_query = self.query
            original_receive_response = self.receive_response

            user_prompt_holder: list[str | None] = [None]

            @wraps(original_query)
            async def wrapped_query(prompt: Any, session_id: str = "default") -> None:
                if isinstance(prompt, str):
                    user_prompt_holder[0] = prompt
                else:
                    user_prompt_holder[0] = None
                return await original_query(prompt, session_id=session_id)

            @wraps(original_receive_response)
            async def wrapped_receive_response() -> AsyncIterator[Any]:
                from claude_agent_sdk import ResultMessage

                from weave.trace.context import call_context

                wc = get_weave_client()
                if wc is None:
                    async for msg in original_receive_response():
                        yield msg
                    return

                user_prompt = user_prompt_holder[0]
                self._weave_turn_counter += 1

                turn_inputs: dict[str, Any] = {}
                if user_prompt is not None:
                    turn_inputs["prompt"] = user_prompt

                if self._weave_thread_id is None:
                    thread_id, _ = _resolve_thread_id()
                    self._weave_thread_id = thread_id

                with call_context.set_thread_id(self._weave_thread_id):
                    turn_call = wc.create_call(
                        op="claude_agent_sdk.turn",
                        inputs=turn_inputs,
                        display_name=turn_display_name(user_prompt),
                        attributes={"kind": "agent"},
                        use_stack=False,
                    )

                    state = _make_initial_state(user_prompt)
                    state["response_start_time"] = datetime.now(tz=timezone.utc)

                    result_msg = None
                    try:
                        async for msg in original_receive_response():
                            if isinstance(msg, ResultMessage):
                                result_msg = msg
                            else:
                                _process_message_inline(msg, wc, turn_call, state)
                            yield msg
                    finally:
                        _finalize_stream(wc, turn_call, state, result_msg)

            self.query = wrapped_query
            self.receive_response = wrapped_receive_response

        return patched_init

    return wrapper


def get_claude_agent_sdk_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _claude_agent_sdk_patcher  # noqa: PLW0603
    if _claude_agent_sdk_patcher is not None:
        return _claude_agent_sdk_patcher

    _claude_agent_sdk_patcher = MultiPatcher(
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

    return _claude_agent_sdk_patcher
