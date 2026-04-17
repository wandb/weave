"""Weave OTel instrumentor for the Claude Agent SDK.

The Claude Agent SDK has no built-in OTel tracing and no TracingProcessor
interface.  This instrumentor monkey-patches ``InternalClient.process_query``
— the core async generator that both ``query()`` and ``ClaudeSDKClient``
delegate to — to emit OTel spans with GenAI semantic convention attributes.

Usage::

    from weave.otel import setup_tracing
    from weave.otel.instrumentors.claude_agent_sdk import instrument

    provider = setup_tracing(project="my-project", genai_endpoint="...")
    instrument(provider, conversation="coding-session")

    # Use the SDK normally — spans are emitted automatically
    async for msg in query(prompt="Hello", options=options):
        print(msg)

Dependencies:
    - ``claude-agent-sdk`` (the Claude Agent SDK)
    - ``opentelemetry-sdk``
"""

from __future__ import annotations

import dataclasses
import json
import logging
import uuid
from collections.abc import AsyncIterator
from functools import wraps
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import SpanKind, StatusCode

logger = logging.getLogger(__name__)

_original_process_query: Any = None
_original_client_init: Any = None
_tracer: trace.Tracer | None = None
_conversation_id: str = ""
_conversation_name: str = ""


# ---------------------------------------------------------------------------
# Message processing -> OTel span attributes
# ---------------------------------------------------------------------------


def _serialize_block_content(block: Any) -> str:
    """Extract text content from a content block."""
    if hasattr(block, "text"):
        return block.text
    if hasattr(block, "thinking"):
        return block.thinking
    return str(block)


def _process_messages_to_otel(
    root_span: trace.Span,
    tracer: trace.Tracer,
    msg: Any,
    state: dict[str, Any],
) -> None:
    """Process a single streamed message, managing OTel child spans.

    Mirrors the logic in the Weave-native integration's
    ``_process_message_inline`` but targets OTel spans.
    """
    # Lazy imports to avoid import-time dependency
    from claude_agent_sdk import (
        AssistantMessage,
        SystemMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    pending_thinking: list[Any] = state["pending_thinking"]
    open_tools: dict[str, tuple[trace.Span, object]] = state["open_tool_spans"]
    output_messages: list[dict[str, Any]] = state["output_messages"]

    def _is_thinking_only(m: Any) -> bool:
        return isinstance(m, AssistantMessage) and all(
            isinstance(b, ThinkingBlock) for b in m.content
        )

    if _is_thinking_only(msg):
        pending_thinking.extend(msg.content)
        return

    if isinstance(msg, AssistantMessage):
        if state["model"] is None and msg.model:
            state["model"] = msg.model

        all_blocks = list(pending_thinking) + list(msg.content) if pending_thinking else list(msg.content)
        if pending_thinking:
            pending_thinking.clear()

        thinking_blocks = [b for b in all_blocks if isinstance(b, ThinkingBlock)]
        text_blocks = [b for b in all_blocks if isinstance(b, TextBlock)]
        tool_uses = [b for b in all_blocks if isinstance(b, ToolUseBlock)]

        if thinking_blocks:
            thinking_text = "\n".join(b.thinking for b in thinking_blocks)
            output_messages.append(
                {
                    "role": "assistant",
                    "parts": [{"type": "reasoning", "content": thinking_text}],
                }
            )

        if text_blocks:
            text_content = "\n".join(b.text for b in text_blocks)
            output_messages.append({"role": "assistant", "content": text_content})

        for tool_block in tool_uses:
            tool_name = tool_block.name
            tool_input = tool_block.input
            output_messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": tool_name,
                            "arguments": json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input),
                            "id": tool_block.id,
                        }
                    ],
                }
            )

            parent_ctx = trace.set_span_in_context(root_span)
            tool_span = tracer.start_span(
                name=f"execute_tool {tool_name}",
                kind=SpanKind.INTERNAL,
                context=parent_ctx,
            )
            tool_span.set_attribute("gen_ai.operation.name", "execute_tool")
            tool_span.set_attribute("gen_ai.tool.name", tool_name)
            tool_span.set_attribute(
                "gen_ai.tool.call.arguments",
                json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input),
            )
            tool_span.set_attribute("gen_ai.provider.name", "anthropic")
            if _conversation_id:
                tool_span.set_attribute("gen_ai.conversation.id", _conversation_id)
            if _conversation_name:
                tool_span.set_attribute("gen_ai.conversation.name", _conversation_name)

            ctx = trace.set_span_in_context(tool_span)
            token = otel_context.attach(ctx)
            open_tools[tool_block.id] = (tool_span, token)

    elif isinstance(msg, UserMessage):
        content = msg.content if isinstance(msg.content, list) else []
        for block in content:
            if isinstance(block, ToolResultBlock) and block.tool_use_id in open_tools:
                tool_span, token = open_tools.pop(block.tool_use_id)
                try:
                    result_str = ""
                    if hasattr(block, "content"):
                        if isinstance(block.content, str):
                            result_str = block.content
                        elif isinstance(block.content, list):
                            parts = []
                            for p in block.content:
                                if hasattr(p, "text"):
                                    parts.append(p.text)
                                else:
                                    parts.append(str(p))
                            result_str = "\n".join(parts)
                        else:
                            result_str = str(block.content)
                    tool_span.set_attribute("gen_ai.tool.call.result", result_str)
                finally:
                    otel_context.detach(token)  # type: ignore[arg-type]
                    tool_span.end()

    elif isinstance(msg, SystemMessage):
        system_text = ""
        if hasattr(msg, "content") and isinstance(msg.content, str):
            system_text = msg.content
        elif hasattr(msg, "content") and isinstance(msg.content, list):
            parts = []
            for p in msg.content:
                if hasattr(p, "text"):
                    parts.append(p.text)
                elif isinstance(p, str):
                    parts.append(p)
            system_text = "\n".join(parts)
        if system_text:
            root_span.set_attribute(
                "gen_ai.system_instructions",
                json.dumps([{"role": "system", "content": system_text}]),
            )


def _finalize_root_span(
    root_span: trace.Span,
    state: dict[str, Any],
    result_msg: Any,
    prompt: Any,
) -> None:
    """Set final attributes on the root span and end it."""
    user_prompt = prompt if isinstance(prompt, str) else None
    if user_prompt:
        root_span.set_attribute(
            "gen_ai.input.messages",
            json.dumps([{"role": "user", "content": user_prompt}]),
        )

    if state["output_messages"]:
        root_span.set_attribute(
            "gen_ai.output.messages", json.dumps(state["output_messages"])
        )

    model = state.get("model")
    if model:
        root_span.set_attribute("gen_ai.request.model", model)
        root_span.set_attribute("gen_ai.response.model", model)
        root_span.update_name(f"invoke_agent claude ({model})")

    if result_msg is not None:
        usage = getattr(result_msg, "usage", None)
        if usage and isinstance(usage, dict):
            input_t = usage.get("input_tokens", 0) or 0
            output_t = usage.get("output_tokens", 0) or 0
            if input_t:
                root_span.set_attribute("gen_ai.usage.input_tokens", input_t)
            if output_t:
                root_span.set_attribute("gen_ai.usage.output_tokens", output_t)
            cache_read = usage.get("cache_read_input_tokens", 0) or 0
            cache_create = usage.get("cache_creation_input_tokens", 0) or 0
            if cache_read:
                root_span.set_attribute("gen_ai.usage.cache_read_input_tokens", cache_read)
            if cache_create:
                root_span.set_attribute("gen_ai.usage.cache_creation_input_tokens", cache_create)

        is_error = getattr(result_msg, "is_error", False)
        if is_error:
            error_text = getattr(result_msg, "result", "") or "error"
            root_span.set_status(StatusCode.ERROR, str(error_text))
            root_span.set_attribute("gen_ai.response.finish_reasons", ["error"])
        else:
            root_span.set_attribute("gen_ai.response.finish_reasons", ["completed"])

        num_turns = getattr(result_msg, "num_turns", None)
        if num_turns is not None:
            root_span.set_attribute("weave.claude.num_turns", num_turns)

        cost = getattr(result_msg, "total_cost_usd", None)
        if cost is not None:
            root_span.set_attribute("weave.claude.total_cost_usd", cost)

    for tool_use_id, (tool_span, token) in state["open_tool_spans"].items():
        try:
            otel_context.detach(token)  # type: ignore[arg-type]
            tool_span.end()
        except Exception:
            pass
    state["open_tool_spans"].clear()


# ---------------------------------------------------------------------------
# Monkey-patch wrapper
# ---------------------------------------------------------------------------


def _make_patched_process_query(original: Any) -> Any:
    """Create the patched ``process_query`` async generator."""

    @wraps(original)
    async def patched_process_query(
        self_client: Any,
        prompt: Any,
        options: Any,
        transport: Any = None,
    ) -> AsyncIterator[Any]:
        from claude_agent_sdk import ResultMessage

        if _tracer is None:
            async for msg in original(
                self_client, prompt=prompt, options=options, transport=transport
            ):
                yield msg
            return

        root_span = _tracer.start_span(
            name="invoke_agent claude",
            kind=SpanKind.CLIENT,
        )
        root_span.set_attribute("gen_ai.operation.name", "invoke_agent")
        root_span.set_attribute("gen_ai.agent.name", "claude")
        root_span.set_attribute("gen_ai.provider.name", "anthropic")

        if _conversation_id:
            root_span.set_attribute("gen_ai.conversation.id", _conversation_id)
        if _conversation_name:
            root_span.set_attribute("gen_ai.conversation.name", _conversation_name)

        system_prompt = getattr(options, "system_prompt", None) if options else None
        if system_prompt:
            root_span.set_attribute(
                "gen_ai.system_instructions",
                json.dumps([{"role": "system", "content": system_prompt}]),
            )

        allowed_tools = getattr(options, "allowed_tools", None) if options else None
        if allowed_tools:
            tool_defs = [
                {"type": "function", "name": t} for t in allowed_tools
            ]
            root_span.set_attribute("gen_ai.tool.definitions", json.dumps(tool_defs))

        ctx = trace.set_span_in_context(root_span)
        token = otel_context.attach(ctx)

        state: dict[str, Any] = {
            "pending_thinking": [],
            "open_tool_spans": {},
            "output_messages": [],
            "model": None,
        }

        result_msg = None
        try:
            async for msg in original(
                self_client, prompt=prompt, options=options, transport=transport
            ):
                if isinstance(msg, ResultMessage):
                    result_msg = msg
                else:
                    _process_messages_to_otel(root_span, _tracer, msg, state)
                yield msg
        except Exception as exc:
            root_span.set_status(StatusCode.ERROR, str(exc))
            raise
        finally:
            _finalize_root_span(root_span, state, result_msg, prompt)
            otel_context.detach(token)
            root_span.end()

    return patched_process_query


def _make_patched_client_init(original_init: Any) -> Any:
    """Patch ``ClaudeSDKClient.__init__`` to wrap ``receive_response()``.

    ``ClaudeSDKClient`` has its own internal async iteration that does NOT
    go through ``InternalClient.process_query``.  We wrap
    ``receive_response()`` on each instance to create OTel spans for
    multi-turn conversations.
    """

    @wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)

        original_receive_response = self.receive_response
        original_query = self.query
        user_prompt_holder: list[str | None] = [None]

        @wraps(original_query)
        async def wrapped_query(prompt: Any, session_id: str = "default") -> None:
            user_prompt_holder[0] = prompt if isinstance(prompt, str) else None
            return await original_query(prompt, session_id=session_id)

        @wraps(original_receive_response)
        async def wrapped_receive_response() -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage

            if _tracer is None:
                async for msg in original_receive_response():
                    yield msg
                return

            user_prompt = user_prompt_holder[0]

            root_span = _tracer.start_span(
                name="invoke_agent claude",
                kind=SpanKind.CLIENT,
            )
            root_span.set_attribute("gen_ai.operation.name", "invoke_agent")
            root_span.set_attribute("gen_ai.agent.name", "claude")
            root_span.set_attribute("gen_ai.provider.name", "anthropic")

            if _conversation_id:
                root_span.set_attribute("gen_ai.conversation.id", _conversation_id)
            if _conversation_name:
                root_span.set_attribute(
                    "gen_ai.conversation.name", _conversation_name
                )

            options = getattr(self, "_options", None) or getattr(self, "options", None)
            if options:
                sys_prompt = getattr(options, "system_prompt", None)
                if sys_prompt:
                    root_span.set_attribute(
                        "gen_ai.system_instructions",
                        json.dumps([{"role": "system", "content": sys_prompt}]),
                    )
                allowed = getattr(options, "allowed_tools", None)
                if allowed:
                    root_span.set_attribute(
                        "gen_ai.tool.definitions",
                        json.dumps([{"type": "function", "name": t} for t in allowed]),
                    )

            if user_prompt:
                root_span.set_attribute(
                    "gen_ai.input.messages",
                    json.dumps([{"role": "user", "content": user_prompt}]),
                )

            ctx = trace.set_span_in_context(root_span)
            token = otel_context.attach(ctx)

            state: dict[str, Any] = {
                "pending_thinking": [],
                "open_tool_spans": {},
                "output_messages": [],
                "model": None,
            }

            result_msg = None
            try:
                async for msg in original_receive_response():
                    if isinstance(msg, ResultMessage):
                        result_msg = msg
                    else:
                        _process_messages_to_otel(root_span, _tracer, msg, state)
                    yield msg
            except Exception as exc:
                root_span.set_status(StatusCode.ERROR, str(exc))
                raise
            finally:
                _finalize_root_span(root_span, state, result_msg, user_prompt)
                otel_context.detach(token)
                root_span.end()

        self.query = wrapped_query
        self.receive_response = wrapped_receive_response

    return patched_init


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def instrument(
    provider: TracerProvider,
    *,
    conversation: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """Instrument the Claude Agent SDK to emit OTel spans with GenAI semantic conventions.

    Monkey-patches ``InternalClient.process_query`` — the core async
    generator that both ``query()`` and ``ClaudeSDKClient`` delegate
    to — so that every agent invocation produces a properly attributed
    OTel span tree.

    Unlike the OpenAI and Google ADK instrumentors, there is no ``agents``
    parameter.  The Claude Agent SDK configures agents via
    ``ClaudeAgentOptions`` at call time, so system prompts and allowed
    tools are extracted from the ``options`` parameter inside the patched
    generator.

    Args:
        provider: The OTel ``TracerProvider`` to create spans with.
        conversation: Human-readable conversation name for the UI.
            Also generates a UUID conversation_id automatically.
        conversation_id: Explicit conversation ID.  When omitted, a
            UUID is generated if *conversation* is set.

    Examples:
        >>> from weave.otel import setup_tracing
        >>> from weave.otel.instrumentors.claude_agent_sdk import instrument
        >>> provider = setup_tracing(project="demo", genai_endpoint="...")
        >>> instrument(provider, conversation="coding-session")
    """
    global _original_process_query, _original_client_init, _tracer, _conversation_id, _conversation_name  # noqa: PLW0603

    _tracer = provider.get_tracer("weave.otel.instrumentors.claude_agent_sdk")
    _conversation_id = conversation_id or (str(uuid.uuid4()) if conversation else "")
    _conversation_name = conversation or ""

    import claude_agent_sdk
    import claude_agent_sdk._internal.client as _client_module

    _original_process_query = _client_module.InternalClient.process_query
    _client_module.InternalClient.process_query = _make_patched_process_query(
        _original_process_query
    )

    _original_client_init = claude_agent_sdk.ClaudeSDKClient.__init__
    claude_agent_sdk.ClaudeSDKClient.__init__ = _make_patched_client_init(
        _original_client_init
    )

    if _conversation_name and _conversation_id:
        _write_conversation_annotation(_conversation_id, _conversation_name)


def uninstrument() -> None:
    """Restore the original ``InternalClient.process_query``.

    Examples:
        >>> instrument(provider, conversation="session")
        >>> uninstrument()
    """
    global _original_process_query, _original_client_init, _tracer  # noqa: PLW0603

    if _original_process_query is not None:
        try:
            import claude_agent_sdk._internal.client as _client_module

            _client_module.InternalClient.process_query = _original_process_query
        except Exception:
            pass
        _original_process_query = None

    if _original_client_init is not None:
        try:
            import claude_agent_sdk

            claude_agent_sdk.ClaudeSDKClient.__init__ = _original_client_init
        except Exception:
            pass
        _original_client_init = None

    _tracer = None


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
