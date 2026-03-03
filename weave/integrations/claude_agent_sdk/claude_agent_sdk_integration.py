from __future__ import annotations

import dataclasses
import importlib
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from functools import wraps
from typing import Any

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.context.weave_client_context import get_weave_client

logger = logging.getLogger(__name__)

_claude_agent_sdk_patcher: MultiPatcher | None = None


def _process_conversation(
    messages: list[Any],
    user_prompt: str | None,
) -> None:
    wc = get_weave_client()
    if wc is None:
        return

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

    if not messages:
        return

    # Extract ResultMessage for metadata
    result_msg = None
    for msg in messages:
        if isinstance(msg, ResultMessage):
            result_msg = msg
            break

    # Build root call inputs
    root_inputs: dict[str, Any] = {}
    if user_prompt is not None:
        root_inputs["prompt"] = user_prompt

    # Create root "conversation" call
    root_call = wc.create_call(
        op=f"claude-session-{str(datetime.now())}",
        inputs=root_inputs,
        attributes={"kind": "agent"},
        use_stack=False,
    )

    # Track tool results by tool_use_id for matching
    tool_results: dict[str, Any] = {}

    # First pass: collect tool results from all message types
    for msg in messages:
        content = None
        if isinstance(msg, UserMessage) and isinstance(msg.content, list):
            content = msg.content
        elif isinstance(msg, AssistantMessage):
            content = msg.content
        if content:
            for block in content:
                if isinstance(block, ToolResultBlock):
                    tool_results[block.tool_use_id] = block

    def _serialize_msg(msg: Any) -> dict[str, Any]:
        """Serialize a dataclass message, preserving all fields."""
        d = dataclasses.asdict(msg)
        # Tag with role based on type
        if isinstance(msg, UserMessage):
            d["role"] = "user"
        elif isinstance(msg, AssistantMessage):
            d["role"] = "assistant"
        elif isinstance(msg, SystemMessage):
            d["role"] = "system"
        elif isinstance(msg, ResultMessage):
            d["role"] = "result"
        return d

    # Second pass: create child calls and build full messages list
    accumulated_messages: list[dict[str, Any]] = []

    for msg in messages:
        # Serialize every message into the accumulated list
        accumulated_messages.append(_serialize_msg(msg))

        # Additionally create child calls for assistant messages
        if not isinstance(msg, AssistantMessage):
            continue

        serialized_msg = _serialize_msg(msg)

        text_parts = []
        thinking_parts = []
        tool_uses = []
        for block in msg.content:
            if isinstance(block, ThinkingBlock):
                thinking_parts.append(block.thinking)
            elif isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                tool_uses.append(block)

        # Create tool child calls
        for tool_block in tool_uses:
            tool_call = wc.create_call(
                op=f"claude_agent_sdk.tool_use.{tool_block.name}",
                inputs={"message": serialized_msg},
                parent=root_call,
                attributes={"kind": "tool"},
                use_stack=False,
            )
            tool_output: dict[str, Any] = {}
            if tool_block.id in tool_results:
                result_block = tool_results[tool_block.id]
                tool_output = dataclasses.asdict(result_block)
            wc.finish_call(tool_call, output=tool_output)

        # Create LLM response child call if there is text or thinking content
        if text_parts or thinking_parts:
            llm_call = wc.create_call(
                op="claude_agent_sdk.response",
                inputs={"message": serialized_msg},
                parent=root_call,
                attributes={"kind": "llm"},
                use_stack=False,
            )
            wc.finish_call(llm_call, output=serialized_msg)

    # Build root output
    root_output: dict[str, Any] = {
        "status": "completed",
        "messages": accumulated_messages,
    }
    if result_msg is not None:
        if result_msg.usage:
            root_output["usage"] = result_msg.usage
        if result_msg.total_cost_usd is not None:
            root_output["total_cost_usd"] = result_msg.total_cost_usd
        root_output["duration_ms"] = result_msg.duration_ms
        root_output["num_turns"] = result_msg.num_turns
        if result_msg.result is not None:
            root_output["result"] = result_msg.result
        if result_msg.is_error:
            root_output["status"] = "error"

    exception = None
    if result_msg is not None and result_msg.is_error:
        exception = Exception(result_msg.result or "Conversation ended with error")

    if exception:
        wc.finish_call(root_call, output=root_output, exception=exception)
    else:
        wc.finish_call(root_call, output=root_output)


def _patched_init_wrapper(
    settings: IntegrationSettings,
) -> Any:
    def wrapper(original_init: Any) -> Any:
        @wraps(original_init)
        def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)

            # Store original methods
            original_query = self.query
            original_receive_response = self.receive_response

            # State for this instance
            user_prompt_holder: list[str | None] = [None]

            @wraps(original_query)
            async def wrapped_query(
                prompt: Any, session_id: str = "default"
            ) -> None:
                # Capture prompt if it's a string
                if isinstance(prompt, str):
                    user_prompt_holder[0] = prompt
                else:
                    user_prompt_holder[0] = None
                return await original_query(prompt, session_id=session_id)

            @wraps(original_receive_response)
            async def wrapped_receive_response() -> AsyncIterator[Any]:
                accumulated: list[Any] = []
                async for msg in original_receive_response():
                    accumulated.append(msg)
                    yield msg
                # After iteration completes, process the conversation
                _process_conversation(accumulated, user_prompt_holder[0])

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
                lambda: importlib.import_module("claude_agent_sdk"),
                "ClaudeSDKClient.__init__",
                _patched_init_wrapper(settings),
            ),
        ]
    )

    return _claude_agent_sdk_patcher
