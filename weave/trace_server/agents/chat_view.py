"""Normalize agent spans into a structured chat / agent trajectory view.

Converts a flat list of `AgentSpanSchema` rows (from the `spans`
table) into a linear sequence of `AgentChatMessage` objects suitable for
rendering an agent conversation UI.

This is a **Weave product feature**, not a semconv concern.  The message types
include Weave-specific concepts that have no OTel GenAI semconv equivalent:

- `agent_start`: agent lifecycle boundary
- `context_compacted`: Weave context compaction events

The normalization handles provider-specific span formats (OpenAI Agents SDK,
Google ADK) and produces a unified output.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from weave.trace_server.agents.constants import (
    MAX_WALK_DEPTH,
    OP_EXECUTE_TOOL,
    OP_INVOKE_AGENT,
)
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import (
    AgentChatMessage,
    AgentSpanSchema,
    AgentTraceChatRes,
)

logger = logging.getLogger(__name__)

_USER_ROLE = "user"
_ASSISTANT_ROLE = "assistant"
_NON_USER_PROMPT_ROLES = {
    _ASSISTANT_ROLE,
    "system",
    "tool",
    "tool_call",
    "tool_result",
}


# ---------------------------------------------------------------------------
# Data types — used in the public API signatures below
# ---------------------------------------------------------------------------


@dataclass
class SpanNode:
    """A span with its children, for tree traversal."""

    span: AgentSpanSchema
    children: list[SpanNode] = field(default_factory=list)


@dataclass(frozen=True)
class TokenTotals:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    reasoning_content: str | None


def _datetime_sort_seconds(dt: datetime | None) -> float:
    if dt is None:
        return 0.0
    return dt.timestamp()


def _span_sort_key(span: AgentSpanSchema) -> tuple[bool, float, bool, float, str]:
    """Ordering key for deterministic chronological span sorts.

    `started_at` is non-null from ClickHouse but can be None in in-memory
    callers and tests. The `is None` first element groups nulls last
    without forcing a datetime.min fallback. When spans share a start time,
    prefer the later-ended span first so enclosing spans sort before shorter
    children; span_id is only the final deterministic tiebreaker.
    """
    return (
        span.started_at is None,
        _datetime_sort_seconds(span.started_at),
        span.ended_at is None,
        -_datetime_sort_seconds(span.ended_at),
        span.span_id,
    )


def _root_sort_key(span: AgentSpanSchema) -> tuple[bool, datetime | None, str]:
    """Prefer spans that ended latest when a trace has no single root."""
    return (span.ended_at is not None, span.ended_at, span.span_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_trace_chat(
    spans: list[AgentSpanSchema],
    trace_id: str,
) -> AgentTraceChatRes:
    """Build the full chat response for a trace."""
    messages = build_chat_messages(spans)

    root_span_name: str | None = None
    provider: str | None = None
    total_duration_ms: int | None = None

    if spans:
        root = _select_root_span(spans)
        root_span_name = root.agent_name or root.span_name
        provider = root.provider_name
        # `total_duration_ms` == root span wall-clock duration
        # (`root.ended_at - root.started_at`). Under OTel convention the
        # root encloses its children, so this is the elapsed time for the
        # whole turn — not a sum of child durations (which would double
        # count overlapping subagents / parallel tool calls).
        total_duration_ms = _compute_duration_ms(root.started_at, root.ended_at)

    return AgentTraceChatRes(
        trace_id=trace_id,
        root_span_name=root_span_name,
        provider=provider,
        total_duration_ms=total_duration_ms,
        messages=messages,
    )


def build_chat_messages(spans: list[AgentSpanSchema]) -> list[AgentChatMessage]:
    """Convert a list of agent spans into a linear chat trajectory.

    Build steps:

    1. Build a parent-child tree from the flat span list (`build_span_tree`).
    2. Emit a single `user_message` at the front, sourced from the first
       `invoke_agent` span's `input_messages` (falling back to any span with
       a usable user prompt; see `_find_user_prompt`).
    3. Walk each root in `started_at` order. The walk is a preorder
       traversal: emit lifecycle markers as we descend, recurse into
       children, then emit trailing messages (agent response, compaction)
       on the way back up.

    The walk emits, in order:

    - `agent_start` when we enter an `invoke_agent` span that names an agent.
    - `tool_call` for each `execute_tool` span.
    - `assistant_message` for the final assistant text in each subtree — either
      from a descendant LLM span (`chat` / `generate_content`), or from the
      `invoke_agent` span itself if no descendant emitted one. This avoids
      double-rendering when SDKs (e.g. OpenAI Agents SDK, Google ADK) mirror
      the final response onto both the parent `invoke_agent` and its inner
      LLM call.
    - `context_compacted` when a compaction event rides on an `invoke_agent`
      span.

    Subagents are not flattened into separate turns. They are traversed in
    place, inherit the nearest enclosing agent name when their own span omits
    one, and can still emit their own lifecycle/tool/assistant messages.
    """
    if not spans:
        return []

    tree = build_span_tree(spans)
    messages: list[AgentChatMessage] = []

    if user_message := _find_user_message(spans):
        messages.append(user_message)

    def _walk(node: SpanNode, nearest_agent: str = "", _depth: int = 0) -> bool:
        """Preorder-walk one subtree, appending to the enclosing `messages`.

        Returns True iff this subtree emitted at least one `assistant_message`.
        An enclosing `invoke_agent` uses that signal to decide whether to
        emit its own mirrored response: if any descendant already did, the
        parent stays quiet to avoid showing the same text twice.

        `nearest_agent` carries the name of the closest enclosing
        `invoke_agent` so descendants inherit it when they have no
        `agent_name` of their own.
        """
        if _depth > MAX_WALK_DEPTH:
            logger.warning(
                "span tree walk truncated at depth %d (trace_id=%s, span_id=%s)",
                _depth,
                node.span.trace_id,
                node.span.span_id,
            )
            return False
        span = node.span
        op = span.operation_name
        agent_name = span.agent_name or nearest_agent

        # ---- invoke_agent ----
        if op == OP_INVOKE_AGENT:
            span_name = span.span_name or ""
            name = (
                span.agent_name
                or nearest_agent
                or span_name.removeprefix(f"{OP_INVOKE_AGENT} ")
            )

            if span.agent_name:
                messages.append(
                    AgentChatMessage(
                        type="agent_start",
                        span_id=span.span_id,
                        agent_name=span.agent_name,
                        model=span.request_model,
                        status=span.status_code,
                        system_instructions="\n".join(span.system_instructions)
                        if span.system_instructions
                        else "",
                        tool_definitions=span.tool_definitions or "",
                        started_at=span.started_at,
                    )
                )
            else:
                # `gen_ai.agent.name` is a recommended (not required)
                # attribute, so some producers omit it. We still walk the
                # subtree but don't emit an `agent_start` divider because
                # there's nothing meaningful to label it with.
                logger.debug(
                    "invoke_agent span without agent_name (span_id=%s)",
                    span.span_id,
                )

            emitted_in_subtree = False
            for child in node.children:
                if _walk(child, name, _depth + 1):
                    emitted_in_subtree = True

            # Only emit from the invoke_agent itself if no descendant LLM
            # span already produced an `assistant_message`. This is the
            # mirroring guard described in the function docstring.
            if not emitted_in_subtree:
                msg = _emit_assistant_message(span, name, aggregate_node=node)
                if msg:
                    messages.append(msg)
                    emitted_in_subtree = True

            if span.compaction_summary or (span.compaction_items_before or 0) > 0:
                messages.append(
                    AgentChatMessage(
                        type="context_compacted",
                        span_id=span.span_id,
                        agent_name=name,
                        compaction_summary=span.compaction_summary,
                        compaction_items_before=span.compaction_items_before,
                        compaction_items_after=span.compaction_items_after,
                        started_at=span.started_at,
                    )
                )
            return emitted_in_subtree

        # ---- execute_tool ----
        if op == OP_EXECUTE_TOOL:
            span_name = span.span_name or ""
            tool_name = span.tool_name or span_name.removeprefix(f"{OP_EXECUTE_TOOL} ")
            messages.append(
                AgentChatMessage(
                    type="tool_call",
                    span_id=span.span_id,
                    agent_name=span.agent_name or nearest_agent,
                    tool_name=tool_name,
                    tool_arguments=span.tool_call_arguments,
                    tool_result=span.tool_call_result,
                    duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
                    started_at=span.started_at,
                    status=span.status_code,
                    content_refs=_content_refs(span),
                )
            )
            emitted_in_subtree = False
            for child in node.children:
                if _walk(child, nearest_agent, _depth + 1):
                    emitted_in_subtree = True
            return emitted_in_subtree

        # ---- chat / generate_content / unknown: walk children, maybe emit ----
        emitted_in_subtree = False
        for child in node.children:
            if _walk(child, agent_name, _depth + 1):
                emitted_in_subtree = True

        msg = _emit_assistant_message(span, agent_name)
        if msg:
            messages.append(msg)
            emitted_in_subtree = True
        return emitted_in_subtree

    for root in tree:
        _walk(root)

    return messages


def build_span_tree(spans: list[AgentSpanSchema]) -> list[SpanNode]:
    """Build a parent-child tree from flat spans, sorted by start time."""
    node_map = {s.span_id: SpanNode(span=s) for s in spans}
    roots: list[SpanNode] = []

    for span in spans:
        node = node_map[span.span_id]
        if span.parent_span_id:
            if parent := node_map.get(span.parent_span_id):
                parent.children.append(node)
            else:
                # Orphan: parent is referenced but not in the input set
                # (filtered out, dropped, or in a different ingest batch).
                # Promote to a synthetic root so the subtree still renders
                # rather than getting silently dropped.
                roots.append(node)
        else:
            roots.append(node)

    def _sort(nodes: list[SpanNode]) -> None:
        nodes.sort(key=lambda n: _span_sort_key(n.span))
        for n in nodes:
            _sort(n.children)

    _sort(roots)
    return roots


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _select_root_span(spans: list[AgentSpanSchema]) -> AgentSpanSchema:
    """Select the trace root span.

    A well-formed trace has exactly one span with no parent. If the input is
    partial or malformed, use the latest-ended span so the wrapper metadata
    still reflects the most enclosing-looking span available.
    """
    roots = [s for s in spans if not s.parent_span_id]
    if len(roots) == 1:
        return roots[0]

    logger.warning(
        "expected exactly one root span, found %d (trace_ids=%r)",
        len(roots),
        sorted({s.trace_id for s in spans}),
    )
    return max(spans, key=_root_sort_key)


def _message_role(message: NormalizedMessage | dict[str, Any]) -> str:
    if isinstance(message, NormalizedMessage):
        return message.role
    return str(message.get("role") or "")


def _message_content(message: NormalizedMessage | dict[str, Any]) -> str:
    if isinstance(message, NormalizedMessage):
        return message.content
    return str(message.get("content") or "")


def _filter_message_texts(
    messages: list[NormalizedMessage],
    *,
    include_roles: set[str] | None = None,
    exclude_roles: set[str] | None = None,
) -> list[str]:
    """Return non-empty message content matching role include/exclude filters."""
    texts: list[str] = []
    for message in messages:
        role = _message_role(message)
        content = _message_content(message)
        if not content:
            continue
        if include_roles is not None and role not in include_roles:
            continue
        if exclude_roles is not None and role in exclude_roles:
            continue
        texts.append(content)
    return texts


def _extract_user_text(
    messages: list[NormalizedMessage], *, last_only: bool = False
) -> str:
    """Extract user text from normalized input_messages.

    First pass: entries tagged `role == "user"`. Fallback pass: entries
    that could plausibly be the user prompt: provider-specific or empty-role
    messages. We intentionally exclude assistant, system, and tool roles so
    those do not render as a user prompt.
    """
    if not messages:
        return ""
    texts = _filter_message_texts(messages, include_roles={_USER_ROLE})
    if not texts:
        texts = _filter_message_texts(messages, exclude_roles=_NON_USER_PROMPT_ROLES)
        if texts:
            logger.debug(
                "no role=user input messages; falling back to unknown/provider roles (roles=%r)",
                [_message_role(m) for m in messages],
            )
    if last_only and texts:
        return texts[-1]
    return "\n\n".join(texts)


def _extract_non_user_output_text(messages: list[NormalizedMessage]) -> str:
    """Extract renderable output text from normalized output_messages.

    Output arrays are expected to contain assistant messages, but some SDKs
    include provider-specific roles. The only role we deliberately exclude is
    `user`, which should not be rendered as an assistant response.
    """
    if not messages:
        return ""
    texts = _filter_message_texts(messages, exclude_roles={_USER_ROLE})
    return "\n\n".join(texts)


def _compute_duration_ms(
    started_at: datetime | str | None, ended_at: datetime | str | None
) -> int:
    """Return elapsed milliseconds, or 0 when either timestamp is missing."""
    if not started_at or not ended_at:
        return 0
    try:
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if isinstance(ended_at, str):
            ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        delta = ended_at - started_at
        return max(0, int(delta.total_seconds() * 1000))
    except Exception:
        logger.exception(
            "failed to compute duration from started_at=%r ended_at=%r",
            started_at,
            ended_at,
        )
        return 0


def _content_refs(span: AgentSpanSchema) -> list[str]:
    """Return opaque content handles for UI-side attachment rendering."""
    return [str(r) for r in (span.content_refs or []) if r]


def _sum_descendant_tokens(node: SpanNode) -> TokenTotals:
    """Sum input, output, and reasoning tokens across a subtree."""
    input_t = node.span.input_tokens or 0
    output_t = node.span.output_tokens or 0
    reasoning_t = node.span.reasoning_tokens or 0
    reasoning_text = node.span.reasoning_content
    for child in node.children:
        child_totals = _sum_descendant_tokens(child)
        input_t += child_totals.input_tokens
        output_t += child_totals.output_tokens
        reasoning_t += child_totals.reasoning_tokens
        if child_totals.reasoning_content and not reasoning_text:
            reasoning_text = child_totals.reasoning_content
    return TokenTotals(input_t, output_t, reasoning_t, reasoning_text)


def _find_user_message(spans: list[AgentSpanSchema]) -> AgentChatMessage | None:
    """Find the user prompt for this trace.

    Priority order: invoke_agent spans first, then anything else, with
    started_at tiebreaking inside each group. Returns the first span whose
    `input_messages` yields user text, already shaped as an API message.
    """
    prioritized = sorted(
        spans,
        key=lambda s: (s.operation_name != OP_INVOKE_AGENT, _span_sort_key(s)),
    )
    for s in prioritized:
        msgs = s.input_messages or []
        if not msgs:
            continue
        text = _extract_user_text(msgs, last_only=True)
        if text:
            return AgentChatMessage(
                type="user_message",
                text=text,
                agent_name="User",
                started_at=s.started_at,
                content_refs=_content_refs(s),
            )
    return None


def _emit_assistant_message(
    span: AgentSpanSchema,
    agent_name: str,
    *,
    aggregate_node: SpanNode | None = None,
) -> AgentChatMessage | None:
    """Build an assistant_message from a span's output_messages, or None if empty."""
    if not span.output_messages:
        return None
    text = _extract_non_user_output_text(span.output_messages)
    if not text:
        return None

    if aggregate_node:
        totals = _sum_descendant_tokens(aggregate_node)
    else:
        totals = TokenTotals(
            input_tokens=span.input_tokens or 0,
            output_tokens=span.output_tokens or 0,
            reasoning_tokens=span.reasoning_tokens or 0,
            reasoning_content=span.reasoning_content,
        )

    return AgentChatMessage(
        type="assistant_message",
        span_id=span.span_id,
        agent_name=agent_name,
        model=span.response_model or span.request_model,
        text=text,
        reasoning_content=totals.reasoning_content,
        reasoning_tokens=totals.reasoning_tokens,
        input_tokens=totals.input_tokens or span.input_tokens,
        output_tokens=totals.output_tokens or span.output_tokens,
        duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
        started_at=span.started_at,
        status=span.status_code,
        content_refs=_content_refs(span),
    )
