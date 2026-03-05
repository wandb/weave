"""Weave integration for the Claude Agent SDK (claude_agent_sdk).

Patches ClaudeSDKClient to create:
- One root "Session" call per client lifecycle (created on first query)
- Child calls for each receive_response(), named by the first few words of the response

Also patches the top-level query() function for one-shot usage.
"""

from __future__ import annotations

import importlib
from functools import wraps
from typing import Any

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_claude_agent_sdk_patcher: MultiPatcher | NoOpPatcher | None = None

# Key used to store weave state on the client instance
_WEAVE_STATE_ATTR = "_weave_session_state"


def _get_response_display_name(messages: list[Any], max_words: int = 8) -> str:
    """Extract the first few words of the assistant's response text for display."""
    from claude_agent_sdk.types import AssistantMessage, TextBlock

    for msg in messages:
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text:
                    words = block.text.split()[:max_words]
                    name = " ".join(words)
                    if len(block.text.split()) > max_words:
                        name += "..."
                    return name
    return "Response"


def _extract_result_data(messages: list[Any]) -> dict[str, Any]:
    """Extract model and usage from collected messages."""
    from claude_agent_sdk.types import AssistantMessage, ResultMessage

    model = None
    usage = None
    total_cost_usd = None
    duration_ms = None
    num_turns = None
    result_text = None

    for msg in messages:
        if isinstance(msg, AssistantMessage) and msg.model:
            model = msg.model
        if isinstance(msg, ResultMessage):
            usage = msg.usage
            total_cost_usd = msg.total_cost_usd
            duration_ms = msg.duration_ms
            num_turns = msg.num_turns
            result_text = msg.result

    output: dict[str, Any] = {}
    if model is not None:
        output["model"] = model
    if usage is not None:
        output["usage"] = usage
    if total_cost_usd is not None:
        output["total_cost_usd"] = total_cost_usd
    if duration_ms is not None:
        output["duration_ms"] = duration_ms
    if num_turns is not None:
        output["num_turns"] = num_turns
    if result_text is not None:
        output["result"] = result_text

    return output


def _serialize_options(options: Any) -> dict[str, Any]:
    """Serialize ClaudeAgentOptions to a dict, keeping only serializable fields."""
    if options is None:
        return {}
    from dataclasses import asdict

    try:
        d = asdict(options)
        for key in [
            "can_use_tool",
            "hooks",
            "debug_stderr",
            "stderr",
            "mcp_servers",
        ]:
            d.pop(key, None)
        return d
    except Exception:
        return {}


def _ensure_session_call(client: Any) -> dict[str, Any] | None:
    """Ensure a root session call exists on the client. Returns the weave state dict."""
    from weave.trace.context import call_context
    from weave.trace.context.weave_client_context import get_weave_client

    wc = get_weave_client()
    if wc is None:
        return None

    state = getattr(client, _WEAVE_STATE_ATTR, None)
    if state is not None:
        return state

    inputs: dict[str, Any] = {}
    if hasattr(client, "options"):
        inputs["options"] = _serialize_options(client.options)

    session_call = wc.create_call(
        op="claude_agent_sdk.session",
        inputs=inputs,
        parent=call_context.get_current_call(),
        display_name="Session",
    )

    state = {"session_call": session_call, "wc": wc}
    object.__setattr__(client, _WEAVE_STATE_ATTR, state)
    return state


def _finish_session_call(client: Any) -> None:
    """Finish the root session call if it exists."""
    state = getattr(client, _WEAVE_STATE_ATTR, None)
    if state is None:
        return

    wc = state["wc"]
    session_call = state["session_call"]
    wc.finish_call(session_call, output={"status": "completed"})

    try:
        object.__setattr__(client, _WEAVE_STATE_ATTR, None)
    except Exception:
        pass


def _create_client_query_wrapper(_settings: OpSettings) -> Any:
    """Wrap ClaudeSDKClient.query to initialize the root session on first call."""

    def wrapper(fn: Any) -> Any:
        @wraps(fn)
        async def patched_client_query(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            _ensure_session_call(self_client)
            return await fn(self_client, *args, **kwargs)

        return patched_client_query

    return wrapper


def _create_receive_response_wrapper(_settings: OpSettings) -> Any:
    """Wrap ClaudeSDKClient.receive_response to create child calls under the session."""

    def wrapper(fn: Any) -> Any:
        @wraps(fn)
        async def patched_receive_response(
            self_client: Any, *args: Any, **kwargs: Any
        ) -> Any:
            from weave.trace.context.weave_client_context import get_weave_client

            wc = get_weave_client()
            if wc is None:
                async for msg in fn(self_client, *args, **kwargs):
                    yield msg
                return

            # Ensure root session exists
            state = _ensure_session_call(self_client)
            if state is None:
                async for msg in fn(self_client, *args, **kwargs):
                    yield msg
                return

            session_call = state["session_call"]

            # Create a child call under the session (display_name set after response)
            child_call = wc.create_call(
                op="claude_agent_sdk.response",
                inputs={},
                parent=session_call,
                display_name="Response",
            )

            collected_messages: list[Any] = []
            exception = None
            try:
                async for msg in fn(self_client, *args, **kwargs):
                    collected_messages.append(msg)
                    yield msg
            except Exception as e:
                exception = e
                raise
            finally:
                output = _extract_result_data(collected_messages)
                display_name = _get_response_display_name(collected_messages)
                if exception is not None:
                    output["error"] = str(exception)
                child_call.display_name = display_name
                wc.finish_call(child_call, output=output, exception=exception)

        return patched_receive_response

    return wrapper


def _create_disconnect_wrapper(_settings: OpSettings) -> Any:
    """Wrap ClaudeSDKClient.disconnect to finish the root session call."""

    def wrapper(fn: Any) -> Any:
        @wraps(fn)
        async def patched_disconnect(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            _finish_session_call(self_client)
            return await fn(self_client, *args, **kwargs)

        return patched_disconnect

    return wrapper


def _create_query_wrapper(_settings: OpSettings) -> Any:
    """Wrap the top-level query() function for one-shot usage."""

    def wrapper(fn: Any) -> Any:
        @wraps(fn)
        async def patched_query(*args: Any, **kwargs: Any) -> Any:
            from weave.trace.context import call_context
            from weave.trace.context.weave_client_context import get_weave_client

            wc = get_weave_client()
            if wc is None:
                async for msg in fn(*args, **kwargs):
                    yield msg
                return

            prompt = kwargs.get("prompt")
            options = kwargs.get("options")
            inputs: dict[str, Any] = {}
            if isinstance(prompt, str):
                inputs["prompt"] = prompt
            inputs["options"] = _serialize_options(options)

            call = wc.create_call(
                op="claude_agent_sdk.query",
                inputs=inputs,
                parent=call_context.get_current_call(),
                display_name="Session",
            )

            collected_messages: list[Any] = []
            exception = None
            try:
                async for msg in fn(*args, **kwargs):
                    collected_messages.append(msg)
                    yield msg
            except Exception as e:
                exception = e
                raise
            finally:
                output = _extract_result_data(collected_messages)
                display_name = _get_response_display_name(collected_messages)
                if display_name != "Response":
                    call.display_name = display_name
                if exception is not None:
                    output["error"] = str(exception)
                wc.finish_call(call, output=output, exception=exception)

        return patched_query

    return wrapper


def get_claude_agent_sdk_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _claude_agent_sdk_patcher
    if _claude_agent_sdk_patcher is not None:
        return _claude_agent_sdk_patcher

    base = settings.op_settings

    query_settings = base.model_copy(
        update={
            "name": base.name or "claude_agent_sdk.query",
            "kind": base.kind or "llm",
        }
    )
    client_settings = base.model_copy(
        update={
            "name": base.name or "claude_agent_sdk.session",
        }
    )

    _claude_agent_sdk_patcher = MultiPatcher(
        [
            # Top-level query() function
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk.query"),
                "query",
                _create_query_wrapper(query_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk"),
                "query",
                _create_query_wrapper(query_settings),
            ),
            # ClaudeSDKClient methods
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk.client"),
                "ClaudeSDKClient.query",
                _create_client_query_wrapper(client_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk.client"),
                "ClaudeSDKClient.receive_response",
                _create_receive_response_wrapper(client_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("claude_agent_sdk.client"),
                "ClaudeSDKClient.disconnect",
                _create_disconnect_wrapper(client_settings),
            ),
        ]
    )

    return _claude_agent_sdk_patcher
