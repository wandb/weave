"""Weave integration for Claude Agent SDK.

This module provides automatic tracing of Claude Agent SDK usage, capturing
agent runs as parent calls with child calls for each tool use, and rich
metadata from the ResultMessage (cost, tokens, duration, turns).

The integration works by patching ``claude_agent_sdk.query()`` and
``ClaudeSDKClient.query()`` to wrap the async iterators, and by injecting
PreToolUse/PostToolUse hooks to create child spans for tool calls.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from weave.integrations.patcher import NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import get_weave_client

logger = logging.getLogger(__name__)

_claude_agent_sdk_patcher: ClaudeAgentSDKPatcher | None = None


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get an attribute from a dataclass or dict-like object."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


# Map of tool_use_id -> Call for in-flight tool uses.
_active_tool_calls: dict[str, Any] = {}

# The current parent call for hooks to attach child calls to.
# Hooks fire in a different async context (SDK's anyio task group), so
# call_context.get_current_call() won't find the parent.  We store it
# explicitly instead.
_current_parent_call: Any = None


async def _pre_tool_use_hook(
    hook_input: Any,
    matched: str | None,
    context: Any,
) -> dict[str, Any]:
    """PreToolUse hook that creates a child Weave call for each tool use."""
    wc = get_weave_client()
    if wc is None:
        return {}

    tool_name = hook_input.get("tool_name", "unknown")
    tool_input = hook_input.get("tool_input", {})
    tool_use_id = hook_input.get("tool_use_id", "")

    call = wc.create_call(
        op="claude_agent_sdk.tool_use",
        inputs={
            "tool_name": tool_name,
            "tool_input": tool_input,
        },
        parent=_current_parent_call,
        display_name=tool_name,
        use_stack=False,
    )

    # Store the call so PostToolUse can finish it.
    _active_tool_calls[tool_use_id] = call

    return {}


async def _post_tool_use_hook(
    hook_input: Any,
    matched: str | None,
    context: Any,
) -> dict[str, Any]:
    """PostToolUse hook that finishes the child Weave call for a tool use."""
    wc = get_weave_client()
    if wc is None:
        return {}

    tool_use_id = hook_input.get("tool_use_id", "")
    tool_response = hook_input.get("tool_response")

    call = _active_tool_calls.pop(tool_use_id, None)
    if call is not None:
        wc.finish_call(
            call,
            output={"tool_response": tool_response},
        )

    return {}


def _merge_hooks(
    existing_hooks: dict[str, list[Any]] | None,
) -> dict[str, list[Any]]:
    """Merge our tracing hooks with any user-provided hooks.

    We append our hooks to any existing hook lists rather than replacing them.
    """
    hooks: dict[str, list[Any]] = {}
    if existing_hooks:
        for key, matchers in existing_hooks.items():
            hooks[key] = list(matchers)

    hook_matcher_cls = importlib.import_module("claude_agent_sdk").HookMatcher

    # Add our PreToolUse hook
    pre_matcher = hook_matcher_cls(matcher=None, hooks=[_pre_tool_use_hook])
    hooks.setdefault("PreToolUse", []).append(pre_matcher)

    # Add our PostToolUse hook
    post_matcher = hook_matcher_cls(matcher=None, hooks=[_post_tool_use_hook])
    hooks.setdefault("PostToolUse", []).append(post_matcher)

    return hooks


def _extract_inputs(prompt: Any, options: Any) -> dict[str, Any]:
    """Extract structured inputs from the query arguments."""
    inputs: dict[str, Any] = {}

    if isinstance(prompt, str):
        inputs["prompt"] = prompt
    else:
        inputs["prompt"] = "<async_iterable>"

    if options is not None:
        model = _safe_get(options, "model")
        if model is not None:
            inputs["model"] = model

        system_prompt = _safe_get(options, "system_prompt")
        if isinstance(system_prompt, str):
            inputs["system_prompt"] = system_prompt

        max_turns = _safe_get(options, "max_turns")
        if max_turns is not None:
            inputs["max_turns"] = max_turns

        permission_mode = _safe_get(options, "permission_mode")
        if permission_mode is not None:
            inputs["permission_mode"] = permission_mode

    return inputs


def _extract_output(result_message: Any, accumulated_text: str) -> dict[str, Any]:
    """Extract structured output from the ResultMessage."""
    output: dict[str, Any] = {}

    output["result"] = _safe_get(result_message, "result")
    output["text"] = accumulated_text
    output["is_error"] = _safe_get(result_message, "is_error", False)
    output["num_turns"] = _safe_get(result_message, "num_turns", 0)
    output["session_id"] = _safe_get(result_message, "session_id", "")
    output["duration_ms"] = _safe_get(result_message, "duration_ms", 0)

    usage = _safe_get(result_message, "usage")
    if usage is not None:
        output["usage"] = usage

    total_cost = _safe_get(result_message, "total_cost_usd")
    if total_cost is not None:
        output["total_cost_usd"] = total_cost

    return output


class TracingAsyncIterator:
    """Wraps an AsyncIterator[Message] to create Weave trace spans."""

    def __init__(
        self,
        iterator: AsyncIterator[Any],
        inputs: dict[str, Any],
    ) -> None:
        self._iterator = iterator
        self._inputs = inputs
        self._parent_call: Any = None
        self._accumulated_text: str = ""
        self._started = False

    def __aiter__(self) -> TracingAsyncIterator:
        return self

    async def __anext__(self) -> Any:
        global _current_parent_call
        wc = get_weave_client()

        # Create the parent call on first iteration
        if not self._started:
            self._started = True
            if wc is not None:
                self._parent_call = wc.create_call(
                    op="claude_agent_sdk.query",
                    inputs=self._inputs,
                    parent=call_context.get_current_call(),
                    display_name="Claude Agent",
                    use_stack=False,
                )
                # Publish parent call so hooks (running in a different async
                # context) can attach child calls to it.
                _current_parent_call = self._parent_call

        try:
            message = await self._iterator.__anext__()
        except StopAsyncIteration:
            # Iteration complete — finish the parent call if we haven't
            # received a ResultMessage (shouldn't normally happen).
            if self._parent_call is not None and wc is not None:
                wc.finish_call(
                    self._parent_call,
                    output={"text": self._accumulated_text},
                )
                self._parent_call = None
                _current_parent_call = None
            raise
        except Exception as exc:
            if self._parent_call is not None and wc is not None:
                wc.finish_call(self._parent_call, exception=exc)
                self._parent_call = None
                _current_parent_call = None
            raise

        sdk = importlib.import_module("claude_agent_sdk")

        # Accumulate text from AssistantMessages
        if isinstance(message, sdk.AssistantMessage):
            for block in message.content:
                if isinstance(block, sdk.TextBlock):
                    self._accumulated_text += block.text

        # Finish parent call when ResultMessage arrives
        if isinstance(message, sdk.ResultMessage) and self._parent_call is not None and wc is not None:
            output = _extract_output(message, self._accumulated_text)
            wc.finish_call(self._parent_call, output=output)
            self._parent_call = None
            _current_parent_call = None

        return message


async def _string_to_async_iterable(prompt: str) -> AsyncIterator[dict[str, Any]]:
    """Convert a string prompt to an async iterable of message dicts.

    The SDK's InternalClient.process_query() closes stdin immediately for
    string prompts, which prevents hook callback responses from being sent
    back. By converting to an async iterable, the SDK uses stream_input()
    which keeps stdin open until the first result arrives.
    """
    yield {
        "type": "user",
        "session_id": "",
        "message": {"role": "user", "content": prompt},
        "parent_tool_use_id": None,
    }


def _patch_query(original_fn: Any) -> Any:
    """Create a patched version of ``claude_agent_sdk.query``."""

    async def patched_query(
        *,
        prompt: Any,
        options: Any = None,
        transport: Any = None,
    ) -> AsyncIterator[Any]:
        wc = get_weave_client()
        if wc is None:
            async for msg in original_fn(
                prompt=prompt, options=options, transport=transport
            ):
                yield msg
            return

        # Inject hooks into options
        sdk = importlib.import_module("claude_agent_sdk")
        if options is None:
            options = sdk.ClaudeAgentOptions()

        merged_hooks = _merge_hooks(_safe_get(options, "hooks"))
        options = sdk.ClaudeAgentOptions(
            **{
                **{
                    f.name: getattr(options, f.name)
                    for f in options.__dataclass_fields__.values()
                },
                "hooks": merged_hooks,
            }
        )

        inputs = _extract_inputs(prompt, options)

        # Convert string prompts to async iterables so the SDK keeps stdin
        # open for hook callback responses (see _string_to_async_iterable).
        effective_prompt: Any = prompt
        if isinstance(prompt, str):
            effective_prompt = _string_to_async_iterable(prompt)

        iterator = original_fn(
            prompt=effective_prompt, options=options, transport=transport
        )
        tracing_iter = TracingAsyncIterator(iterator, inputs)

        async for msg in tracing_iter:
            yield msg

    return patched_query


def _patch_client_query(original_fn: Any) -> Any:
    """Create a patched version of ``ClaudeSDKClient.query``."""

    async def patched_query(
        self: Any,
        prompt: Any,
        session_id: str = "default",
    ) -> None:
        wc = get_weave_client()
        if wc is None:
            return await original_fn(self, prompt, session_id)

        # Inject hooks into the client's options if they exist
        sdk = importlib.import_module("claude_agent_sdk")
        if self._options is not None:
            merged_hooks = _merge_hooks(_safe_get(self._options, "hooks"))
            self._options = sdk.ClaudeAgentOptions(
                **{
                    **{
                        f.name: getattr(self._options, f.name)
                        for f in self._options.__dataclass_fields__.values()
                    },
                    "hooks": merged_hooks,
                }
            )

        return await original_fn(self, prompt, session_id)

    return patched_query


def _patch_receive_response(original_fn: Any) -> Any:
    """Create a patched version of ``ClaudeSDKClient.receive_response``."""

    async def patched_receive_response(self: Any) -> AsyncIterator[Any]:
        wc = get_weave_client()
        if wc is None:
            async for msg in original_fn(self):
                yield msg
            return

        inputs = _extract_inputs("<client_query>", self._options)
        iterator = original_fn(self)
        tracing_iter = TracingAsyncIterator(iterator, inputs)

        async for msg in tracing_iter:
            yield msg

    return patched_receive_response


class ClaudeAgentSDKPatcher(Patcher):
    """Patcher for Claude Agent SDK that wraps query functions and injects hooks."""

    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings
        self.patched = False
        self._originals: dict[str, Any] = {}

    def attempt_patch(self) -> bool:
        if self.patched:
            return True

        try:
            sdk = importlib.import_module("claude_agent_sdk")
            query_module = importlib.import_module("claude_agent_sdk.query")
            client_module = importlib.import_module("claude_agent_sdk.client")
        except ImportError:
            return False

        try:
            # Patch the top-level query function
            self._originals["query"] = sdk.query
            self._originals["query_module.query"] = query_module.query
            patched_q = _patch_query(sdk.query)
            sdk.query = patched_q
            query_module.query = patched_q

            # Patch ClaudeSDKClient methods
            client_cls = sdk.ClaudeSDKClient

            self._originals["client.query"] = client_cls.query
            client_cls.query = _patch_client_query(client_cls.query)

            self._originals["client.receive_response"] = client_cls.receive_response
            client_cls.receive_response = _patch_receive_response(
                client_cls.receive_response
            )

            self.patched = True
        except Exception:
            logger.debug("Failed to patch Claude Agent SDK", exc_info=True)
            return False

        return True

    def undo_patch(self) -> bool:
        if not self.patched:
            return True

        try:
            sdk = importlib.import_module("claude_agent_sdk")
            query_module = importlib.import_module("claude_agent_sdk.query")

            if "query" in self._originals:
                sdk.query = self._originals["query"]
            if "query_module.query" in self._originals:
                query_module.query = self._originals["query_module.query"]

            client_cls = sdk.ClaudeSDKClient
            if "client.query" in self._originals:
                client_cls.query = self._originals["client.query"]
            if "client.receive_response" in self._originals:
                client_cls.receive_response = self._originals[
                    "client.receive_response"
                ]

            self._originals.clear()
            self.patched = False
        except Exception:
            logger.debug("Failed to undo Claude Agent SDK patch", exc_info=True)
            return False

        return True


def get_claude_agent_sdk_patcher(
    settings: IntegrationSettings | None = None,
) -> ClaudeAgentSDKPatcher | NoOpPatcher:
    """Get a patcher for Claude Agent SDK integration."""
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _claude_agent_sdk_patcher
    if _claude_agent_sdk_patcher is not None:
        return _claude_agent_sdk_patcher

    _claude_agent_sdk_patcher = ClaudeAgentSDKPatcher(settings)

    return _claude_agent_sdk_patcher
