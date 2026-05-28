"""OTel-emitting wrappers for the Claude Agent SDK.

Wraps the public SDK surface — ``query()`` and three ``ClaudeSDKClient``
methods — and emits OpenTelemetry spans following Weave's ``gen_ai``
semantic conventions:

- One ``invoke_agent`` root span per ``query()`` or
  ``receive_response()`` call. Carries the user prompt as
  ``gen_ai.input.messages`` and the assistant's full trajectory
  (text + tool_use blocks across every turn) as
  ``gen_ai.output.messages``. The terminal ``ResultMessage`` populates
  ``gen_ai.usage.*`` and total cost.
- ``execute_tool`` child spans driven by SDK ``PreToolUse`` /
  ``PostToolUse`` / ``PostToolUseFailure`` hooks injected into the
  caller's ``ClaudeAgentOptions``. Hooks give real per-tool latency that
  message-content parsing can't (both blocks arrive after execution).
- ``invoke_agent`` subagent spans for messages carrying
  ``parent_tool_use_id``, nested under the spawning tool span.

The structure mirrors the Arize openinference reference; the attribute
schema is Weave's ``gen_ai`` semconv superset (built via
``weave.session.session_otel``).
"""

from __future__ import annotations

import copy
import importlib
import logging
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import suppress
from contextvars import ContextVar
from functools import wraps
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Span, StatusCode

from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
)
from weave.session.types import (
    Message,
    TextPart,
    ToolCallPart,
    ToolCallResponsePart,
)
from weave.trace.autopatch import IntegrationSettings

logger = logging.getLogger(__name__)

_TRACER_NAME = "weave.claude_agent_sdk"
_WEAVE_ATTR_PREFIX = "weave.claude_agent_sdk"
_PROVIDER_NAME = "anthropic"

# Per-instance attribute names threading state across the
# ``ClaudeSDKClient`` lifecycle. The hook is injected once into
# ``options`` on first ``connect()`` / ``query()`` and reused for every
# subsequent ``receive_response()`` via the delegating tracker.
_LAST_PROMPT_ATTR = "_weave_last_prompt"
_HOOKS_INJECTED_ATTR = "_weave_hooks_injected"
_DELEGATING_TRACKER_ATTR = "_weave_delegating_tracker"

# Marker set by the ``ClaudeSDKClient.receive_response`` wrapper for the
# duration of one turn. The shared ``InternalClient.process_query``
# wrapper (which both ``query()`` and the client flow go through)
# consults this to know whether to open its own root spans (the
# query() case — flag is False) or just pass messages through (the
# ClaudeSDKClient case — flag is True; the client wrapper already
# opened the spans).
#
# Patching ``process_query`` (rather than the module-level
# ``query()`` function) is what makes the query() flow work
# regardless of import order: ``from claude_agent_sdk import query``
# captures a stale reference to the unwrapped function if the user
# imports before calling ``weave.init``. Patching the underlying
# class method survives import order because method lookups go
# through the class via the descriptor protocol on every call.
_in_client_flow: ContextVar[bool] = ContextVar(
    "_weave_claude_in_client_flow", default=False
)


# ── Generic helpers ────────────────────────────────────────────────


def _tracer() -> Any:
    return otel_trace.get_tracer(_TRACER_NAME)


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from a dict-like, dataclass, or pydantic object."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _set_attrs(span: Span, attrs: Mapping[str, Any]) -> None:
    """Apply attributes to an OTel span, skipping None / empty strings."""
    for key, val in attrs.items():
        if val is None:
            continue
        if isinstance(val, str) and not val:
            continue
        span.set_attribute(key, val)


# ── SDK type lookup (lazy, cached) ─────────────────────────────────


# Cached lookup of the SDK's typed message & block classes. The SDK
# turns wire-format dicts into typed dataclasses before they reach our
# wrappers, and those typed objects discriminate by class — they do NOT
# carry a ``type`` attribute. So predicates must check ``isinstance``
# first, then fall back to dict-form ``type`` for cassettes / raw
# replay paths. Empty dict acts as a "SDK not importable" sentinel so
# we don't re-pay the ImportError each call.
_sdk_type_cache: dict[str, type | None] | None = None


def _sdk_types() -> dict[str, type | None]:
    """Resolve typed SDK message/block classes, caching the lookup."""
    global _sdk_type_cache  # noqa: PLW0603
    if _sdk_type_cache is not None:
        return _sdk_type_cache
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            SystemMessage,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
            UserMessage,
        )
    except ImportError:
        _sdk_type_cache = {}
        return _sdk_type_cache

    # ``ThinkingBlock`` arrived in later SDK builds — make it optional.
    thinking_block: type | None = None
    try:
        from claude_agent_sdk import ThinkingBlock as _ThinkingBlock

        thinking_block = _ThinkingBlock
    except ImportError:
        thinking_block = None

    _sdk_type_cache = {
        "AssistantMessage": AssistantMessage,
        "UserMessage": UserMessage,
        "SystemMessage": SystemMessage,
        "ResultMessage": ResultMessage,
        "TextBlock": TextBlock,
        "ToolUseBlock": ToolUseBlock,
        "ToolResultBlock": ToolResultBlock,
        "ThinkingBlock": thinking_block,
    }
    return _sdk_type_cache


def _isinstance_sdk(value: Any, type_key: str) -> bool:
    """Return True if ``value`` is a known typed SDK instance for ``type_key``."""
    sdk_type = _sdk_types().get(type_key)
    return sdk_type is not None and isinstance(value, sdk_type)


# ── SDK message helpers ────────────────────────────────────────────


def _extract_message_content(message: Any) -> list[Any] | None:
    """Pull a content-list off a Claude Agent SDK message.

    Typed messages (AssistantMessage/UserMessage) expose ``content``
    directly; raw dicts wrap it inside ``message.content``. Both are
    accepted.
    """
    content = _get_field(message, "content")
    if isinstance(content, list):
        return content
    inner = _get_field(message, "message")
    content = _get_field(inner, "content")
    return content if isinstance(content, list) else None


def _is_text_block(block: Any) -> bool:
    if _isinstance_sdk(block, "TextBlock"):
        return True
    return _get_field(block, "type") == "text"


def _is_tool_use_block(block: Any) -> bool:
    if _isinstance_sdk(block, "ToolUseBlock"):
        return True
    return _get_field(block, "type") == "tool_use"


def _is_tool_result_block(block: Any) -> bool:
    if _isinstance_sdk(block, "ToolResultBlock"):
        return True
    if _get_field(block, "type") == "tool_result":
        return True
    # Older SDK builds emit tool_result without an explicit type field.
    return _get_field(block, "tool_use_id") is not None


def _is_system_init_message(msg: Any) -> bool:
    if _isinstance_sdk(msg, "SystemMessage"):
        return _get_field(msg, "subtype") == "init"
    return (
        _get_field(msg, "type") == "system" and _get_field(msg, "subtype") == "init"
    )


def _is_result_message(msg: Any) -> bool:
    if _isinstance_sdk(msg, "ResultMessage"):
        return True
    if _get_field(msg, "type") == "result":
        return True
    return _get_field(msg, "usage") is not None and _get_field(msg, "subtype") in {
        "result",
        "success",
    }


def _is_assistant_message(msg: Any) -> bool:
    if _isinstance_sdk(msg, "AssistantMessage"):
        return True
    return _get_field(msg, "type") == "assistant"


def _is_user_message(msg: Any) -> bool:
    if _isinstance_sdk(msg, "UserMessage"):
        return True
    return _get_field(msg, "type") == "user"


def _extract_model_name(msg: Any) -> str | None:
    """Locate the model name across the SDK's message shapes."""
    raw = _get_field(msg, "model")
    if raw:
        return str(raw)
    inner = _get_field(msg, "message")
    raw = _get_field(inner, "model")
    if raw:
        return str(raw)
    usage = _get_field(msg, "modelUsage") or _get_field(msg, "model_usage")
    if isinstance(usage, Mapping) and usage:
        return str(next(iter(usage.keys())))
    return None


def _coerce_usage(usage: Any) -> Mapping[str, Any]:
    if isinstance(usage, Mapping):
        return usage
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
        "cache_creation_input_tokens": getattr(
            usage, "cache_creation_input_tokens", None
        ),
    }


def _session_id(msg: Any) -> str | None:
    sid = _get_field(msg, "session_id")
    if sid:
        return str(sid)
    data = _get_field(msg, "data", {}) or {}
    sid = _get_field(data, "session_id")
    return str(sid) if sid else None


# ── Prompt → input messages conversion ─────────────────────────────


def _user_input_messages(prompt: Any) -> list[Message]:
    """Build the input-messages list from the caller's ``prompt`` arg."""
    if prompt is None:
        return []
    if isinstance(prompt, str):
        return [Message.user(prompt)]
    if isinstance(prompt, list):
        out: list[Message] = []
        for entry in prompt:
            if isinstance(entry, Mapping):
                role = str(entry.get("role") or "user")
                content = entry.get("content")
                if isinstance(content, str):
                    out.append(Message(role=role, content=content))
        return out
    return []


def _assistant_message_to_genai(msg: Any) -> Message | None:
    """Convert a Claude Agent SDK assistant message into a gen_ai Message."""
    content = _extract_message_content(msg)
    if not content:
        return None
    parts: list[Any] = []
    for block in content:
        if _is_text_block(block):
            text = _get_field(block, "text")
            if text:
                parts.append(TextPart(content=str(text)))
        elif _is_tool_use_block(block):
            parts.append(
                ToolCallPart(
                    id=str(_get_field(block, "id") or ""),
                    name=str(_get_field(block, "name") or ""),
                    arguments=_get_field(block, "input") or {},
                )
            )
    if not parts:
        return None
    return Message(role="assistant", parts=parts)


def _user_tool_result_messages(msg: Any) -> list[Message]:
    """Convert a user message of tool_result blocks into gen_ai messages."""
    content = _extract_message_content(msg)
    if not content:
        return []
    out: list[Message] = []
    for block in content:
        if _is_tool_result_block(block):
            out.append(
                Message(
                    role="tool",
                    parts=[
                        ToolCallResponsePart(
                            id=str(_get_field(block, "tool_use_id") or ""),
                            response=_get_field(block, "content"),
                        )
                    ],
                )
            )
    return out


# ── Hook injection (PreToolUse / PostToolUse / PostToolUseFailure) ────


def _make_hook_matcher(callback: Callable[..., Any]) -> Any:
    """Wrap a callback in the SDK's ``HookMatcher`` dataclass.

    The SDK's ``_convert_hooks_to_internal_format`` reads ``hasattr(m,
    "hooks")``, which is true for the dataclass form but not for a plain
    dict. Falls back to a dict only if no compatible dataclass class is
    importable (older SDK builds).
    """
    for module_path, name in (
        ("claude_agent_sdk", "HookMatcher"),
        ("claude_agent_sdk.types", "HookMatcher"),
    ):
        try:
            module = importlib.import_module(module_path)
        except Exception:
            continue
        matcher_type = getattr(module, name, None)
        if matcher_type is None:
            continue
        with suppress(Exception):
            return matcher_type(hooks=[callback])
    return {"hooks": [callback]}


def _make_tool_hook_callbacks(
    tool_tracker: _ToolSpanTrackerBase,
) -> dict[str, list[Any]]:
    """Build the three tool-lifecycle hook matchers the SDK consumes."""

    # The SDK invokes hook callbacks via ``await`` regardless of whether
    # they need to await anything themselves. Declaring them ``async`` is
    # the API contract — RUF029 suppressed for that reason.
    async def pre_tool_use(  # noqa: RUF029
        input_data: Any,
        tool_use_id: Any | None = None,
        context: Any | None = None,
    ) -> dict[str, Any]:
        del context
        with suppress(Exception):
            tool_tracker.start_tool_span(
                _get_field(input_data, "tool_name"),
                _get_field(input_data, "tool_input"),
                tool_use_id or _get_field(input_data, "tool_use_id"),
                _get_field(input_data, "parent_tool_use_id"),
            )
        return {}

    async def post_tool_use(  # noqa: RUF029
        input_data: Any,
        tool_use_id: Any | None = None,
        context: Any | None = None,
    ) -> dict[str, Any]:
        del context
        with suppress(Exception):
            tool_tracker.end_tool_span(
                tool_use_id or _get_field(input_data, "tool_use_id"),
                _get_field(input_data, "tool_response"),
            )
        return {}

    async def post_tool_use_failure(  # noqa: RUF029
        input_data: Any,
        tool_use_id: Any | None = None,
        context: Any | None = None,
    ) -> dict[str, Any]:
        del context
        with suppress(Exception):
            tool_tracker.end_tool_span_with_error(
                tool_use_id or _get_field(input_data, "tool_use_id"),
                _get_field(input_data, "error"),
            )
        return {}

    return {
        "PreToolUse": [_make_hook_matcher(pre_tool_use)],
        "PostToolUse": [_make_hook_matcher(post_tool_use)],
        "PostToolUseFailure": [_make_hook_matcher(post_tool_use_failure)],
    }


def _get_hooks(options: Any) -> Mapping[str, Any] | None:
    if options is None:
        return None
    if isinstance(options, Mapping):
        return options.get("hooks")
    hooks = getattr(options, "hooks", None)
    if isinstance(hooks, Mapping):
        return hooks
    return None


def _set_hooks(options: Any, hooks: Mapping[str, Any]) -> Any:
    """Return a copy of ``options`` with ``hooks`` set, falling back to
    in-place mutation for shapes that don't copy cleanly.
    """
    if isinstance(options, Mapping):
        return {**options, "hooks": hooks}
    try:
        new_options = copy.copy(options)
        new_options.hooks = hooks
    except Exception:
        pass
    else:
        return new_options
    try:
        options.hooks = hooks
    except Exception:
        pass
    return options


def _ensure_options(options: Any) -> Any | None:
    if options is not None:
        return options
    try:
        from claude_agent_sdk.types import ClaudeAgentOptions

        return ClaudeAgentOptions()
    except Exception:
        return None


def _merge_hooks(options: Any, tool_tracker: _ToolSpanTrackerBase) -> Any | None:
    """Layer our tool-lifecycle hooks onto any existing options.hooks.

    Caller-provided hooks for the same event run alongside ours (ours
    appended). Returns the merged options object or ``None`` if neither
    a caller-provided ``options`` nor a default ``ClaudeAgentOptions``
    can be constructed (SDK shape mismatch).
    """
    opts = _ensure_options(options)
    if opts is None:
        return None

    existing = _get_hooks(opts)
    if not isinstance(existing, Mapping):
        existing = {}
    merged: dict[str, Any] = dict(existing)
    for event, matchers in _make_tool_hook_callbacks(tool_tracker).items():
        current = merged.get(event, [])
        if not isinstance(current, list):
            current = [current]
        merged[event] = [*current, *matchers]
    return _set_hooks(opts, merged)


# ── Trackers ───────────────────────────────────────────────────────


class _ToolSpanTrackerBase:
    def start_tool_span(
        self,
        tool_name: Any,
        tool_input: Any,
        tool_use_id: Any,
        parent_tool_use_id: Any = None,
    ) -> None:
        raise NotImplementedError

    def end_tool_span(self, tool_use_id: Any, tool_response: Any) -> None:
        raise NotImplementedError

    def end_tool_span_with_error(self, tool_use_id: Any, error: Any) -> None:
        raise NotImplementedError

    def end_all_in_flight(self) -> None:
        raise NotImplementedError

    def get_in_flight_span(self, tool_use_id: Any) -> Span | None:
        return None

    def get_tool_name(self, tool_use_id: Any) -> str | None:
        return None


class _ToolSpanTracker(_ToolSpanTrackerBase):
    """In-flight ``execute_tool`` span manager, one per agent invocation.

    Spans are anchored to the agent's root span by default. When a
    parent_tool_use_id resolves to a subagent span (via the supplied
    ``parent_span_resolver``), the new tool nests under that subagent —
    so nested tool→subagent→tool chains show up as a proper tree.
    """

    def __init__(
        self,
        tracer: Any,
        parent_span: Span | None,
        conversation_id: str,
        parent_span_resolver: Callable[[Any], Span | None] | None = None,
    ) -> None:
        self._tracer = tracer
        self._parent_span = parent_span
        self._conversation_id = conversation_id
        self._parent_span_resolver = parent_span_resolver
        self._in_flight: dict[str, Span] = {}
        self._tool_names: dict[str, str] = {}

    @property
    def conversation_id(self) -> str:
        return self._conversation_id

    def set_conversation_id(self, conversation_id: str) -> None:
        self._conversation_id = conversation_id

    def start_tool_span(
        self,
        tool_name: Any,
        tool_input: Any,
        tool_use_id: Any,
        parent_tool_use_id: Any = None,
    ) -> None:
        if not tool_use_id or not tool_name:
            return
        key = str(tool_use_id)
        if key in self._in_flight:
            return

        name_str = str(tool_name)
        # Use ``JSONString`` coercion via Pydantic — pass the raw input
        # through ``execute_tool_attributes`` so the span attribute is
        # the JSON-encoded string the semconv mandates.
        attrs = execute_tool_attributes(
            tool_name=name_str,
            conversation_id=self._conversation_id,
            tool_call_id=key,
            tool_call_arguments=_serialize_tool_payload(tool_input),
        )

        parent_span = self._parent_span
        if parent_tool_use_id and self._parent_span_resolver is not None:
            resolved = self._parent_span_resolver(parent_tool_use_id)
            if resolved is not None:
                parent_span = resolved

        ctx = (
            otel_trace.set_span_in_context(parent_span)
            if parent_span is not None
            else None
        )
        span = self._tracer.start_span(
            f"execute_tool {name_str}",
            context=ctx,
            attributes=attrs,
        )
        self._in_flight[key] = span
        self._tool_names[key] = name_str

    def end_tool_span(self, tool_use_id: Any, tool_response: Any) -> None:
        if tool_use_id is None:
            return
        key = str(tool_use_id)
        span = self._in_flight.pop(key, None)
        self._tool_names.pop(key, None)
        if span is None:
            return
        if tool_response is not None:
            span.set_attribute(
                "gen_ai.tool.call.result", _serialize_tool_payload(tool_response)
            )
        span.set_status(StatusCode.OK)
        span.end()

    def end_tool_span_with_error(self, tool_use_id: Any, error: Any) -> None:
        if tool_use_id is None:
            return
        key = str(tool_use_id)
        span = self._in_flight.pop(key, None)
        self._tool_names.pop(key, None)
        if span is None:
            return
        msg = str(error) if error is not None else "Tool execution error"
        span.record_exception(Exception(msg))
        span.set_status(StatusCode.ERROR, msg)
        span.end()

    def end_all_in_flight(self) -> None:
        for span in self._in_flight.values():
            with suppress(Exception):
                span.set_status(StatusCode.ERROR, "Abandoned")
                span.end()
        self._in_flight.clear()
        self._tool_names.clear()

    def get_in_flight_span(self, tool_use_id: Any) -> Span | None:
        if tool_use_id is None:
            return None
        return self._in_flight.get(str(tool_use_id))

    def get_tool_name(self, tool_use_id: Any) -> str | None:
        if tool_use_id is None:
            return None
        return self._tool_names.get(str(tool_use_id))


class _DelegatingToolSpanTracker(_ToolSpanTrackerBase):
    """Mutable trampoline so client-level hooks track the current call.

    ``ClaudeSDKClient`` keeps a single ``options`` (and so a single set
    of hooks) across many ``receive_response()`` calls. Each call needs
    its own ``_ToolSpanTracker`` anchored to that call's root span.
    The hooks point at this delegator; the wrapper swaps the delegate
    on entry / clears it on exit. Without the delegator the second
    ``receive_response()`` would write tool spans into the first call's
    root.
    """

    def __init__(self) -> None:
        self._delegate: _ToolSpanTracker | None = None

    def set_delegate(self, tracker: _ToolSpanTracker) -> None:
        self._delegate = tracker

    def clear_delegate(self) -> None:
        self._delegate = None

    def start_tool_span(
        self,
        tool_name: Any,
        tool_input: Any,
        tool_use_id: Any,
        parent_tool_use_id: Any = None,
    ) -> None:
        if self._delegate is not None:
            self._delegate.start_tool_span(
                tool_name, tool_input, tool_use_id, parent_tool_use_id
            )

    def end_tool_span(self, tool_use_id: Any, tool_response: Any) -> None:
        if self._delegate is not None:
            self._delegate.end_tool_span(tool_use_id, tool_response)

    def end_tool_span_with_error(self, tool_use_id: Any, error: Any) -> None:
        if self._delegate is not None:
            self._delegate.end_tool_span_with_error(tool_use_id, error)

    def end_all_in_flight(self) -> None:
        if self._delegate is not None:
            self._delegate.end_all_in_flight()

    def get_in_flight_span(self, tool_use_id: Any) -> Span | None:
        if self._delegate is None:
            return None
        return self._delegate.get_in_flight_span(tool_use_id)

    def get_tool_name(self, tool_use_id: Any) -> str | None:
        if self._delegate is None:
            return None
        return self._delegate.get_tool_name(tool_use_id)


class _SubagentState:
    """Mutable per-subagent accumulator owned by ``_SubagentSpanTracker``."""

    def __init__(self, span: Span) -> None:
        self.span = span
        self.has_error = False
        self.output_messages: list[Message] = []
        self.usage: dict[str, Any] = {}
        self.cost: float | None = None
        self.model: str | None = None
        self.session_id: str | None = None


class _SubagentSpanTracker:
    """Maintains ``invoke_agent`` spans for tool-spawned subagents.

    SDK messages carrying ``parent_tool_use_id`` belong to a child agent
    whose lifetime is bracketed by the tool span. We synthesize one
    ``invoke_agent`` span per unique ``parent_tool_use_id`` and accumulate
    its output messages / usage like the root tracker does.
    """

    def __init__(
        self,
        tracer: Any,
        root_span: Span | None,
        tool_tracker: _ToolSpanTracker,
        conversation_id: str,
    ) -> None:
        self._tracer = tracer
        self._root_span = root_span
        self._tool_tracker = tool_tracker
        self._conversation_id = conversation_id
        self._in_flight: dict[str, _SubagentState] = {}

    def set_conversation_id(self, conversation_id: str) -> None:
        self._conversation_id = conversation_id

    def get_or_create(self, parent_tool_use_id: Any) -> _SubagentState:
        key = str(parent_tool_use_id)
        state = self._in_flight.get(key)
        if state is not None:
            return state
        tool_name = self._tool_tracker.get_tool_name(parent_tool_use_id)
        parent_span = (
            self._tool_tracker.get_in_flight_span(parent_tool_use_id)
            or self._root_span
        )
        ctx = (
            otel_trace.set_span_in_context(parent_span)
            if parent_span is not None
            else None
        )
        span = self._tracer.start_span(
            f"invoke_agent {tool_name or 'Subagent'}",
            context=ctx,
            attributes=invoke_agent_attributes(
                agent_name=tool_name or "Subagent",
                conversation_id=self._conversation_id,
                provider_name=_PROVIDER_NAME,
            ),
        )
        state = _SubagentState(span)
        self._in_flight[key] = state
        return state

    def process_message(self, message: Any) -> bool:
        parent_tool_use_id = _get_field(message, "parent_tool_use_id")
        if not parent_tool_use_id:
            return False
        state = self.get_or_create(parent_tool_use_id)

        if _is_system_init_message(message):
            if model := _extract_model_name(message):
                state.model = model
            if sid := _session_id(message):
                state.session_id = sid
            return True

        if _is_result_message(message):
            usage = _coerce_usage(_get_field(message, "usage"))
            if usage:
                state.usage = dict(usage)
            if cost := _safe_float(_get_field(message, "total_cost_usd")):
                state.cost = cost
            if model := _extract_model_name(message):
                state.model = model
            if _get_field(message, "is_error"):
                state.has_error = True
            self._finish(parent_tool_use_id)
            return True

        if _is_assistant_message(message):
            out_msg = _assistant_message_to_genai(message)
            if out_msg is not None:
                state.output_messages.append(out_msg)
        return True

    def _finish(self, parent_tool_use_id: Any) -> None:
        key = str(parent_tool_use_id)
        state = self._in_flight.pop(key, None)
        if state is None:
            return
        try:
            attrs = invoke_agent_attributes(
                agent_name=self._tool_tracker.get_tool_name(parent_tool_use_id)
                or "Subagent",
                conversation_id=self._conversation_id,
                provider_name=_PROVIDER_NAME,
                model=state.model or "",
                output_messages=state.output_messages,
            )
            _set_attrs(state.span, attrs)
            _set_usage_attrs(state.span, state.usage)
            if state.cost is not None:
                state.span.set_attribute(
                    f"{_WEAVE_ATTR_PREFIX}.total_cost_usd", state.cost
                )
            if state.session_id:
                state.span.set_attribute("gen_ai.response.id", state.session_id)
            if not state.has_error and state.span.is_recording():
                state.span.set_status(StatusCode.OK)
        finally:
            state.span.end()

    def end_all(self) -> None:
        for key in list(self._in_flight.keys()):
            self._finish(key)


# ── Span attribute helpers ─────────────────────────────────────────


def _serialize_tool_payload(value: Any) -> str:
    """Render a tool input/result for ``gen_ai.tool.call.{arguments,result}``.

    String passthrough; everything else JSON-encodes. Mirrors the
    semconv requirement that both attributes be plain strings.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    import json

    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _set_usage_attrs(span: Span, usage: Mapping[str, Any]) -> None:
    """Stamp ``gen_ai.usage.*`` and the cache-tokens fields onto ``span``."""
    if not usage:
        return
    if (n := _safe_int(usage.get("input_tokens"))) is not None:
        span.set_attribute("gen_ai.usage.input_tokens", n)
    if (n := _safe_int(usage.get("output_tokens"))) is not None:
        span.set_attribute("gen_ai.usage.output_tokens", n)
    if (n := _safe_int(usage.get("cache_read_input_tokens"))) is not None:
        span.set_attribute("gen_ai.usage.cache_read.input_tokens", n)
    cache_write = usage.get("cache_creation_input_tokens")
    if cache_write is None:
        cache_write = usage.get("cache_write_input_tokens")
    if (n := _safe_int(cache_write)) is not None:
        span.set_attribute("gen_ai.usage.cache_creation.input_tokens", n)


# ── Root-call iteration state ──────────────────────────────────────


class _RootCallState:
    """Per-call accumulator handed to ``_run_agent_call``.

    Holds the input messages (frozen at call entry from the prompt
    argument), the output messages (one per assistant message that does
    NOT belong to a subagent), and the terminal stats from the
    ``result`` message. Serialized into ``gen_ai.*`` attributes on the
    root span at finalization time.
    """

    def __init__(self, input_messages: list[Message]) -> None:
        self.input_messages = input_messages
        self.output_messages: list[Message] = []
        self.tool_result_messages: list[Message] = []
        self.usage: dict[str, Any] = {}
        self.cost: float | None = None
        self.model: str | None = None
        self.session_id: str | None = None
        self.result_text: str | None = None
        self.has_error = False


def _process_root_message(
    msg: Any,
    state: _RootCallState,
    tool_tracker: _ToolSpanTracker,
    subagent_tracker: _SubagentSpanTracker,
) -> None:
    """Route an SDK message to whichever accumulator owns it.

    Messages tagged with ``parent_tool_use_id`` are routed into the
    subagent tracker. Everything else updates the root state.
    """
    if subagent_tracker.process_message(msg):
        # Subagent messages still need to drive the tool tracker so
        # that tool_use blocks issued *by* a subagent get matching
        # execute_tool spans (nested under the subagent's invoke_agent).
        _update_tool_spans_from_message(msg, tool_tracker)
        return

    if _is_system_init_message(msg):
        if state.session_id is None:
            state.session_id = _session_id(msg)
        if state.model is None:
            state.model = _extract_model_name(msg)
        return

    if _is_result_message(msg):
        usage = _coerce_usage(_get_field(msg, "usage"))
        if usage:
            state.usage = dict(usage)
        if cost := _safe_float(_get_field(msg, "total_cost_usd")):
            state.cost = cost
        if (result := _get_field(msg, "result")) is not None:
            state.result_text = str(result)
        if model := _extract_model_name(msg):
            state.model = model
        if _get_field(msg, "is_error"):
            state.has_error = True
        return

    if _is_assistant_message(msg):
        if state.model is None and (model := _extract_model_name(msg)):
            state.model = model
        out_msg = _assistant_message_to_genai(msg)
        if out_msg is not None:
            state.output_messages.append(out_msg)
        _update_tool_spans_from_message(msg, tool_tracker)
        return

    if _is_user_message(msg):
        tool_results = _user_tool_result_messages(msg)
        if tool_results:
            state.tool_result_messages.extend(tool_results)
        _update_tool_spans_from_message(msg, tool_tracker)


def _update_tool_spans_from_message(
    msg: Any, tool_tracker: _ToolSpanTracker
) -> None:
    """Fallback tool-span maintenance from message blocks alone.

    The hook path is preferred (real latency), but we mirror the
    content-driven path so tool span attribution is correct when hooks
    are unavailable (older SDK, hook injection failed).
    """
    parent_tool_use_id = _get_field(msg, "parent_tool_use_id")
    content = _extract_message_content(msg)
    if content is None:
        return
    for block in content:
        if _is_tool_use_block(block):
            tool_tracker.start_tool_span(
                _get_field(block, "name"),
                _get_field(block, "input"),
                _get_field(block, "id"),
                parent_tool_use_id,
            )
        elif _is_tool_result_block(block):
            if _get_field(block, "is_error"):
                tool_tracker.end_tool_span_with_error(
                    _get_field(block, "tool_use_id"), "Tool execution error"
                )
            else:
                tool_tracker.end_tool_span(
                    _get_field(block, "tool_use_id"),
                    _get_field(block, "content"),
                )


def _finalize_root_span(
    span: Span, state: _RootCallState, conversation_id: str
) -> None:
    """Stamp the accumulated state onto the root invoke_agent span."""
    attrs = invoke_agent_attributes(
        agent_name="ClaudeAgentSDK",
        conversation_id=conversation_id,
        provider_name=_PROVIDER_NAME,
        model=state.model or "",
        input_messages=state.input_messages,
        output_messages=state.output_messages,
    )
    _set_attrs(span, attrs)
    _set_usage_attrs(span, state.usage)
    if state.cost is not None:
        span.set_attribute(f"{_WEAVE_ATTR_PREFIX}.total_cost_usd", state.cost)
    if state.session_id:
        span.set_attribute("gen_ai.response.id", state.session_id)
    if state.result_text is not None:
        span.set_attribute(f"{_WEAVE_ATTR_PREFIX}.result", state.result_text)


# ── Wrappers ───────────────────────────────────────────────────────


def _get_or_create_delegating_tracker(instance: Any) -> _DelegatingToolSpanTracker:
    delegating = getattr(instance, _DELEGATING_TRACKER_ATTR, None)
    if delegating is None:
        delegating = _DelegatingToolSpanTracker()
        with suppress(Exception):
            setattr(instance, _DELEGATING_TRACKER_ATTR, delegating)
    return delegating


def _ensure_client_hooks(
    instance: Any, delegating_tracker: _DelegatingToolSpanTracker
) -> bool:
    """Inject our hooks into ``instance.options`` exactly once.

    The delegating tracker is what the hooks call back into; the
    receive_response wrapper swaps the live ``_ToolSpanTracker``
    delegate per call.
    """
    if getattr(instance, _HOOKS_INJECTED_ATTR, False):
        return True
    options = getattr(instance, "options", None)
    merged = _merge_hooks(options, delegating_tracker)
    if merged is None:
        return False
    try:
        instance.options = merged
        setattr(instance, _HOOKS_INJECTED_ATTR, True)
    except Exception:
        return False
    return True


def _apply_options(
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    options: Any,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Inject the merged options back into the wrapped call args."""
    new_kwargs = dict(kwargs)
    if "options" in new_kwargs or len(args) < 2:
        new_kwargs["options"] = options
        return args, new_kwargs
    new_args = list(args)
    if len(new_args) > 1:
        new_args[1] = options
    return tuple(new_args), new_kwargs


def _extract_prompt_and_options(
    args: tuple[Any, ...], kwargs: Mapping[str, Any]
) -> tuple[Any, Any]:
    prompt = kwargs.get("prompt") if kwargs else None
    options = kwargs.get("options") if kwargs else None
    if prompt is None and args:
        prompt = args[0]
    if options is None and len(args) > 1:
        options = args[1]
    return prompt, options


async def _run_agent_call(
    *,
    span_name: str,
    prompt: Any,
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    inject_hooks: bool,
    delegating_tracker: _DelegatingToolSpanTracker | None,
    parent_span: Span | None = None,
) -> AsyncIterator[Any]:
    """Drive an SDK async generator inside a root invoke_agent span.

    ``inject_hooks=True`` (used by the top-level ``query()`` wrapper)
    builds a fresh ``_ToolSpanTracker`` and threads it into the SDK's
    ``options.hooks``. ``inject_hooks=False`` (used by
    ``ClaudeSDKClient.receive_response``) reuses the delegating tracker
    set up at client-level — the hooks were injected on first
    ``connect()``/``query()`` and now just need their delegate pointed
    at this call's tracker.

    ``parent_span`` is the optional conversation-container span the
    invoke_agent should nest under. ``make_query_wrapper`` passes one in
    so the single-shot ``query()`` flow has a real parent trace; the
    inner invoke_agent's ``gen_ai.conversation.id`` is also written
    onto ``parent_span`` once we learn the session id from the SDK.
    """
    input_messages = _user_input_messages(prompt)
    parent_ctx = (
        otel_trace.set_span_in_context(parent_span)
        if parent_span is not None
        else None
    )
    span = _tracer().start_span(
        span_name,
        context=parent_ctx,
        attributes=invoke_agent_attributes(
            agent_name="ClaudeAgentSDK",
            provider_name=_PROVIDER_NAME,
            input_messages=input_messages,
        ),
    )
    # NOTE: we intentionally do NOT call ``otel_context.attach`` to
    # promote ``span`` to the current OTel context. Async-generator
    # finalization can run on a different ``contextvars.Context`` than
    # the one where ``attach`` ran (GC-driven cleanup after the
    # consumer ``break``s out of an ``async for``), in which case
    # ``detach`` raises ``ValueError: was created in a different
    # Context`` — and OTel logs that as an ``exception`` regardless of
    # what we wrap around the detach call.
    #
    # All child spans we create (tool / subagent) pass ``context=`` to
    # ``start_span`` explicitly using ``set_span_in_context(parent)``,
    # so parent linkage is preserved without relying on the
    # current-span pointer.

    state = _RootCallState(input_messages)
    subagent_tracker: _SubagentSpanTracker | None = None

    def _resolve_parent(parent_tool_use_id: Any) -> Span | None:
        if subagent_tracker is None:
            return None
        return subagent_tracker.get_or_create(parent_tool_use_id).span

    tool_tracker = _ToolSpanTracker(
        _tracer(),
        span,
        conversation_id="",  # populated lazily once session_id arrives
        parent_span_resolver=_resolve_parent,
    )
    subagent_tracker = _SubagentSpanTracker(
        _tracer(), span, tool_tracker, conversation_id=""
    )

    call_args = args
    call_kwargs = dict(kwargs)
    if inject_hooks:
        prompt_arg, options_arg = _extract_prompt_and_options(args, kwargs)
        del prompt_arg
        merged = _merge_hooks(options_arg, tool_tracker)
        if merged is not None:
            call_args, call_kwargs = _apply_options(args, kwargs, merged)
    elif delegating_tracker is not None:
        delegating_tracker.set_delegate(tool_tracker)

    try:
        async for msg in original(*call_args, **call_kwargs):
            _process_root_message(msg, state, tool_tracker, subagent_tracker)
            # Propagate conversation_id onto the tool/subagent trackers
            # the first time we see a session_id, so tool spans created
            # under this root carry the correct ``gen_ai.conversation.id``.
            # Also stamp it onto the outer conversation span (if any).
            if state.session_id and not tool_tracker.conversation_id:
                tool_tracker.set_conversation_id(state.session_id)
                subagent_tracker.set_conversation_id(state.session_id)
                if parent_span is not None:
                    parent_span.set_attribute(
                        "gen_ai.conversation.id", state.session_id
                    )
            yield msg
    except Exception as exc:
        span.record_exception(exc)
        span.set_status(StatusCode.ERROR, f"{type(exc).__name__}: {exc}")
        state.has_error = True
        raise
    finally:
        tool_tracker.end_all_in_flight()
        subagent_tracker.end_all()
        if not inject_hooks and delegating_tracker is not None:
            delegating_tracker.clear_delegate()
        try:
            _finalize_root_span(span, state, state.session_id or "")
            if not state.has_error and span.is_recording():
                span.set_status(StatusCode.OK)
        finally:
            span.end()


def make_process_query_wrapper(
    settings: IntegrationSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap ``claude_agent_sdk._internal.client.InternalClient.process_query``.

    ``process_query`` is the single async generator that both the
    module-level ``query()`` function and ``ClaudeSDKClient.receive_response()``
    delegate to. Patching it at the class level lets one wrapper cover
    both entry points AND survive Python's import-order semantics for
    module-level functions (``from claude_agent_sdk import query``
    captures a stale reference to the unwrapped function if the user
    imports before ``weave.init`` runs).

    When called from the ``ClaudeSDKClient`` flow (``_in_client_flow``
    is True), the client's ``receive_response`` wrapper has already
    opened the invoke_agent span — this wrapper just yields messages
    through. Otherwise (the single-shot ``query()`` flow) it opens an
    outer "Conversation" container span + an inner invoke_agent, so
    one-off ``query()`` traces show a parent and aren't isolated leaves.
    """
    del settings  # currently no per-wrapper settings used

    def make_wrapper(original: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(original)
        async def wrapped(
            self_client: Any,
            prompt: Any,
            options: Any,
            transport: Any = None,
        ) -> AsyncIterator[Any]:
            if _in_client_flow.get():
                # ClaudeSDKClient.receive_response wrapper is upstream
                # and already opened our spans. Pass the SDK messages
                # through untouched so we don't double-wrap.
                async for msg in original(
                    self_client, prompt=prompt, options=options, transport=transport
                ):
                    yield msg
                return

            # query() flow — open conversation + invoke_agent.
            conv_span = _tracer().start_span(
                "ClaudeAgentSDK Conversation",
                attributes={
                    "gen_ai.agent.name": "ClaudeAgentSDK",
                    "gen_ai.provider.name": _PROVIDER_NAME,
                },
            )

            async def _bound_original(*_a: Any, **kw: Any) -> AsyncIterator[Any]:
                # ``_run_agent_call`` may rewrite the ``options`` kwarg
                # to inject our tool hooks; pick that up if present and
                # otherwise fall back to the caller-supplied options.
                merged_options = kw.get("options", options)
                async for msg in original(
                    self_client,
                    prompt=prompt,
                    options=merged_options,
                    transport=transport,
                ):
                    yield msg

            try:
                async for msg in _run_agent_call(
                    span_name="invoke_agent ClaudeAgentSDK.query",
                    prompt=prompt,
                    original=_bound_original,
                    args=(),
                    kwargs={"prompt": prompt, "options": options},
                    inject_hooks=True,
                    delegating_tracker=None,
                    parent_span=conv_span,
                ):
                    yield msg
            finally:
                if conv_span.is_recording():
                    conv_span.set_status(StatusCode.OK)
                conv_span.end()

        return wrapped

    return make_wrapper


def make_client_connect_wrapper(
    settings: IntegrationSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap ``ClaudeSDKClient.connect`` — record the initial prompt and
    inject hooks once per client instance.
    """
    del settings

    def make_wrapper(original: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(original)
        async def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            prompt = kwargs.get("prompt") if kwargs else (args[0] if args else None)
            if prompt is not None:
                with suppress(Exception):
                    setattr(self, _LAST_PROMPT_ATTR, prompt)
            delegating = _get_or_create_delegating_tracker(self)
            _ensure_client_hooks(self, delegating)
            return await original(self, *args, **kwargs)

        return wrapped

    return make_wrapper


def make_client_query_wrapper(
    settings: IntegrationSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap ``ClaudeSDKClient.query`` — record the prompt for the next
    ``receive_response()`` to consume.

    ``query()`` doesn't open a span itself; the span belongs to the
    matching ``receive_response()``.
    """
    del settings

    def make_wrapper(original: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(original)
        async def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            prompt = kwargs.get("prompt") if kwargs else (args[0] if args else None)
            with suppress(Exception):
                setattr(self, _LAST_PROMPT_ATTR, prompt)
            delegating = _get_or_create_delegating_tracker(self)
            _ensure_client_hooks(self, delegating)
            return await original(self, *args, **kwargs)

        return wrapped

    return make_wrapper


def make_client_receive_response_wrapper(
    settings: IntegrationSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap ``ClaudeSDKClient.receive_response`` — one invoke_agent span
    per response turn, with tool hooks delegated to the per-call tracker.

    Sets the ``_in_client_flow`` contextvar so the shared
    ``InternalClient.process_query`` wrapper (which iterates inside
    ``original``) knows to skip its own span creation — we own the
    invoke_agent here.
    """
    del settings

    def make_wrapper(original: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(original)
        async def wrapped(self: Any, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            prompt = getattr(self, _LAST_PROMPT_ATTR, None)
            delegating = _get_or_create_delegating_tracker(self)
            # Hooks should already have been injected on connect()/query();
            # call ensure() defensively for clients that skipped both.
            _ensure_client_hooks(self, delegating)

            async def _bound_original(*a: Any, **kw: Any) -> AsyncIterator[Any]:
                async for msg in original(self, *a, **kw):
                    yield msg

            token = _in_client_flow.set(True)
            try:
                async for msg in _run_agent_call(
                    span_name="invoke_agent ClaudeSDKClient.receive_response",
                    prompt=prompt,
                    original=_bound_original,
                    args=args,
                    kwargs=kwargs,
                    inject_hooks=False,
                    delegating_tracker=delegating,
                ):
                    yield msg
            finally:
                _in_client_flow.reset(token)

        return wrapped

    return make_wrapper
