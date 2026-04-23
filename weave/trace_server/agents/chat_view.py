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
from typing import Any, NamedTuple

from weave.trace_server.agents.constants import MAX_WALK_DEPTH, OP_INVOKE_AGENT
from weave.trace_server.agents.types import (
    AgentChatMessage,
    AgentSpanSchema,
    AgentTraceChatRes,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types — used in the public API signatures below
# ---------------------------------------------------------------------------


class UserPrompt(NamedTuple):
    text: str
    started_at: str
    content_refs: list[str]


@dataclass
class SpanNode:
    """A span with its children, for tree traversal."""

    span: AgentSpanSchema
    children: list[SpanNode] = field(default_factory=list)


def _span_sort_key(span: AgentSpanSchema) -> tuple[bool, datetime | None, str]:
    """Ordering key for deterministic chronological span sorts.

    `started_at` is non-null from ClickHouse but can be None in in-memory
    callers and tests. The `is None` first element groups nulls last
    without forcing a datetime.min fallback (which would mix tz-aware
    and naive values). span_id tiebreaks equal timestamps.
    """
    return (span.started_at is None, span.started_at, span.span_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_trace_chat(
    spans: list[AgentSpanSchema],
    trace_id: str,
) -> AgentTraceChatRes:
    """Build the full chat response for a trace."""
    messages = build_chat_messages(spans)

    root_span_name = ""
    provider = ""
    total_duration_ms = 0

    if spans:
        root = next((s for s in spans if not s.parent_span_id), spans[0])
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
    - `agent_message` for any span whose `output_messages` has assistant text,
       at most once per span (tracked via `emitted_span_ids`).
    - `context_compacted` when a compaction event rides on an `invoke_agent`
       span.

    Spans with operation names we don't special-case (`chat`,
    `generate_content`, or anything else) just contribute their text via
    `agent_message` if present; their children are walked normally.
    """
    if not spans:
        return []

    tree = build_span_tree(spans)
    messages: list[AgentChatMessage] = []
    emitted_span_ids: set[str] = set()

    user_prompt, user_started_at, user_refs = _find_user_prompt(spans)
    if user_prompt:
        messages.append(
            AgentChatMessage(
                type="user_message",
                text=user_prompt,
                agent_name="User",
                started_at=_dt_to_iso(user_started_at),
                content_refs=user_refs,
            )
        )

    def _walk(node: SpanNode, nearest_agent: str = "", _depth: int = 0) -> None:
        """Preorder-walk one subtree, appending to the enclosing `messages`.

        Mutates the enclosing `messages` and `emitted_span_ids` — the
        `emitted_span_ids` set deduplicates `agent_message` emission so a
        span that's reached both via a parent `invoke_agent`'s
        `aggregate_node` hook and directly isn't emitted twice.

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
            return
        span = node.span
        op = span.operation_name
        agent_name = span.agent_name or nearest_agent

        # ---- invoke_agent ----
        if op == OP_INVOKE_AGENT:
            name = span.agent_name or span.span_name.removeprefix(
                f"{OP_INVOKE_AGENT} "
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
                        started_at=_dt_to_iso(span.started_at),
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

            for child in node.children:
                _walk(child, name, _depth + 1)

            if span.span_id not in emitted_span_ids:
                msg = _emit_agent_message(span, name, aggregate_node=node)
                if msg:
                    emitted_span_ids.add(span.span_id)
                    messages.append(msg)

            if span.compaction_summary or span.compaction_items_before > 0:
                messages.append(
                    AgentChatMessage(
                        type="context_compacted",
                        span_id=span.span_id,
                        agent_name=name,
                        compaction_summary=span.compaction_summary,
                        compaction_items_before=span.compaction_items_before,
                        compaction_items_after=span.compaction_items_after,
                        started_at=_dt_to_iso(span.started_at),
                    )
                )
            return

        # ---- execute_tool ----
        if op == "execute_tool":
            tool_name = span.tool_name or span.span_name.removeprefix("execute_tool ")
            messages.append(
                AgentChatMessage(
                    type="tool_call",
                    span_id=span.span_id,
                    agent_name=span.agent_name or nearest_agent,
                    tool_name=tool_name,
                    tool_arguments=span.tool_call_arguments,
                    tool_result=span.tool_call_result,
                    duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
                    started_at=_dt_to_iso(span.started_at),
                    status=span.status_code,
                    content_refs=_content_refs(span),
                )
            )
            for child in node.children:
                _walk(child, nearest_agent, _depth + 1)
            return

        # ---- chat / generate_content / unknown: walk children, maybe emit ----
        for child in node.children:
            _walk(child, agent_name, _depth + 1)

        if span.span_id not in emitted_span_ids:
            msg = _emit_agent_message(span, agent_name)
            if msg:
                emitted_span_ids.add(span.span_id)
                messages.append(msg)

    for root in tree:
        _walk(root)

    return messages


def build_span_tree(spans: list[AgentSpanSchema]) -> list[SpanNode]:
    """Build a parent-child tree from flat spans, sorted by start time."""
    node_map: dict[str, SpanNode] = {}
    roots: list[SpanNode] = []

    for span in spans:
        node_map[span.span_id] = SpanNode(span=span)

    for span in spans:
        node = node_map[span.span_id]
        if span.parent_span_id:
            parent = node_map.get(span.parent_span_id)
            if parent:
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


def _extract_user_text(
    messages: list[dict[str, Any]], *, last_only: bool = False
) -> str:
    """Extract user text from normalized input_messages.

    First pass: entries tagged `role == "user"`. Fallback pass: entries
    that could plausibly be the user prompt — anything that isn't
    explicitly an `assistant` or `tool` message. Some SDKs (notably
    Google ADK) store the user prompt with an empty or provider-specific
    role, so a strict `role == "user"` filter misses them; but we still
    want to exclude model replies and tool results to avoid surfacing
    one of those as "the user prompt".
    """
    if not messages:
        return ""
    texts = [
        m.get("content", "")
        for m in messages
        if m.get("role") == "user" and m.get("content")
    ]
    if not texts:
        texts = [
            m.get("content", "")
            for m in messages
            if m.get("content") and m.get("role") not in {"assistant", "tool"}
        ]
    if last_only and texts:
        return texts[-1]
    return "\n".join(texts)


def _extract_assistant_text(messages: list[dict[str, Any]]) -> str:
    """Extract assistant text from normalized output_messages."""
    if not messages:
        return ""
    texts = [
        m.get("content", "")
        for m in messages
        if m.get("role") != "user" and m.get("content")
    ]
    return "\n".join(texts)


def _dt_to_iso(dt: Any) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    try:
        return dt.isoformat()
    except AttributeError:
        logger.exception("unexpected non-datetime value %r in _dt_to_iso", dt)
        return str(dt)


def _compute_duration_ms(started_at: Any, ended_at: Any) -> int:
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
    raw = span.content_refs
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(r) for r in raw if r]
    return []


def _sum_descendant_tokens(node: SpanNode) -> tuple[int, int, int, str]:
    """Sum input, output, and reasoning tokens across a subtree."""
    input_t = node.span.input_tokens or 0
    output_t = node.span.output_tokens or 0
    reasoning_t = node.span.reasoning_tokens or 0
    reasoning_text = node.span.reasoning_content or ""
    for child in node.children:
        ci, co, cr, ct = _sum_descendant_tokens(child)
        input_t += ci
        output_t += co
        reasoning_t += cr
        if ct and not reasoning_text:
            reasoning_text = ct
    return input_t, output_t, reasoning_t, reasoning_text


def _find_user_prompt(spans: list[AgentSpanSchema]) -> UserPrompt:
    """Find the user prompt for this trace.

    Prefers invoke_agent spans, falls back to any span with input_messages.
    """
    sorted_spans = sorted(spans, key=_span_sort_key)

    for prefer_invoke_agent in (True, False):
        for s in sorted_spans:
            if prefer_invoke_agent and s.operation_name != OP_INVOKE_AGENT:
                continue
            msgs = s.input_messages or []
            if not msgs:
                continue
            text = _extract_user_text(msgs, last_only=True)
            if text:
                return UserPrompt(text, _dt_to_iso(s.started_at), _content_refs(s))

    return UserPrompt("", "", [])


def _emit_agent_message(
    span: AgentSpanSchema,
    agent_name: str,
    *,
    aggregate_node: SpanNode | None = None,
) -> AgentChatMessage | None:
    """Build an agent_message from a span's output_messages, or None if empty."""
    if not span.output_messages:
        return None
    text = _extract_assistant_text(span.output_messages)
    if not text:
        return None

    if aggregate_node:
        agg_in, agg_out, agg_reasoning, agg_reasoning_text = _sum_descendant_tokens(
            aggregate_node
        )
    else:
        agg_in = span.input_tokens
        agg_out = span.output_tokens
        agg_reasoning = span.reasoning_tokens
        agg_reasoning_text = span.reasoning_content or ""

    return AgentChatMessage(
        type="agent_message",
        span_id=span.span_id,
        agent_name=agent_name,
        model=span.response_model or span.request_model,
        text=text,
        reasoning_content=agg_reasoning_text,
        reasoning_tokens=agg_reasoning,
        input_tokens=agg_in or span.input_tokens,
        output_tokens=agg_out or span.output_tokens,
        duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
        started_at=_dt_to_iso(span.started_at),
        status=span.status_code,
        content_refs=_content_refs(span),
    )
