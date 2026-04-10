"""Normalize agent spans into a structured chat / agent trajectory view.

Converts a flat list of ``AgentSpanSchema`` rows (from the ``genai_spans``
table) into a linear sequence of ``AgentChatMessage`` objects suitable for
rendering an agent conversation UI.

The normalization handles provider-specific formats (OpenAI Agents SDK,
Google ADK) and produces a unified output.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from weave.trace_server.agent_types import (
    AgentChatMessage,
    AgentSpanSchema,
    AgentTraceChatRes,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _safe_parse_json(s: str) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def _normalize_content_refs(raw: Any) -> list[str]:
    """Normalize content_refs into a list of strings.

    Handles both native list[str] (from Array(String) columns) and legacy
    JSON-encoded strings for backward compatibility.
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(r) for r in raw if r]
    if isinstance(raw, str):
        parsed = _safe_parse_json(raw)
        if isinstance(parsed, list):
            return [str(r) for r in parsed if r]
        try:
            fixed = (
                raw.replace("'", '"')
                .replace("True", "true")
                .replace("False", "false")
                .replace("None", "null")
            )
            parsed = json.loads(fixed)
            if isinstance(parsed, list):
                return [str(r) for r in parsed if r]
        except (json.JSONDecodeError, TypeError):
            pass
    return []


# ---------------------------------------------------------------------------
# Text extraction from message formats
# ---------------------------------------------------------------------------


def _extract_user_text(
    messages: list[dict[str, Any]], *, last_only: bool = False
) -> str:
    """Extract user text from normalized input_messages.

    Args:
        messages: Normalized message list (each has role, content, etc.).
        last_only: If True, return only the last user message (multi-turn).
    """
    if not messages:
        return ""
    texts = [
        m.get("content", "")
        for m in messages
        if m.get("role") == "user" and m.get("content")
    ]
    if not texts:
        texts = [m.get("content", "") for m in messages if m.get("content")]
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


def _extract_system_prompt(instructions: list[str] | str) -> str:
    """Extract readable system prompt from normalized system_instructions."""
    if not instructions:
        return ""
    if isinstance(instructions, str):
        parsed = _safe_parse_json(instructions)
        if isinstance(parsed, list):
            return "\n".join(str(i) for i in parsed if i)
        return instructions
    return "\n".join(instructions)


def _looks_like_tool_call(text: str) -> bool:
    """Detect text that is SDK metadata rather than human-readable content.

    Filters out OpenAI Agents SDK Python repr strings
    (ResponseReasoningItem, ResponseFunctionToolCall, etc.) and
    serialized tool-call JSON that shouldn't appear as assistant text.
    """
    t = text.strip()
    if not t:
        return False
    if (
        t.startswith("ResponseFunctionToolCall(")
        or t.startswith("transfer_to_")
        or t.startswith('{"tool_calls"')
        or t.startswith('[{"tool_calls"')
    ):
        return True
    lines = t.split("\n")
    return all(
        line.strip() == "" or _RESPONSE_REPR_RE.match(line.strip()) for line in lines
    )


_RESPONSE_REPR_RE = re.compile(r"^Response[A-Z][A-Za-z]*\(.+\)$", re.DOTALL)


def _dt_to_iso(dt: Any) -> str:
    """Convert a datetime (or None / str) to an ISO 8601 string."""
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    try:
        return dt.isoformat()
    except AttributeError:
        return str(dt)


def _compute_duration_ms(
    started_at: Any,
    ended_at: Any,
) -> int:
    """Compute span duration in milliseconds."""
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
        return 0


# ---------------------------------------------------------------------------
# Span tree
# ---------------------------------------------------------------------------

_NOISE_TOOL_NAMES = {"(merged tools)", "(merged)", "transfer_to_agent"}


def _sum_descendant_tokens(
    node: SpanNode,
) -> tuple[int, int, int, str]:
    """Recursively sum input, output, and reasoning tokens across a subtree.

    Returns:
        (input_tokens, output_tokens, reasoning_tokens, reasoning_content)
    """
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


@dataclass
class SpanNode:
    """A span with its children, for tree traversal."""

    span: AgentSpanSchema
    children: list[SpanNode] = field(default_factory=list)


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
                roots.append(node)
        else:
            roots.append(node)

    def _sort(nodes: list[SpanNode]) -> None:
        nodes.sort(key=lambda n: n.span.started_at or "")
        for n in nodes:
            _sort(n.children)

    _sort(roots)
    return roots


# ---------------------------------------------------------------------------
# User prompt extraction
# ---------------------------------------------------------------------------


def find_user_prompt(
    spans: list[AgentSpanSchema],
) -> tuple[str, str, list[str]]:
    """Pre-scan spans to find the user prompt for this trace.

    Uses last_only=True because multi-turn conversations send the full
    history as input_messages, and we only want the current turn's prompt.

    Returns:
        (prompt_text, started_at, content_refs) — started_at is the ISO
        timestamp of the span that carried the user prompt; content_refs is
        the list of uploaded attachment refs from the same span.
    """
    sorted_spans = sorted(spans, key=lambda s: s.started_at or "")

    msgs_field = "input_messages"
    for s in sorted_spans:
        msgs = getattr(s, msgs_field, None) or []
        if s.operation_name == "invoke_agent" and msgs:
            text = _extract_user_text(msgs, last_only=True)
            if text and not _looks_like_tool_call(text):
                return (
                    text,
                    _dt_to_iso(s.started_at),
                    _normalize_content_refs(s.content_refs),
                )

    for s in sorted_spans:
        msgs = getattr(s, msgs_field, None) or []
        if msgs:
            text = _extract_user_text(msgs, last_only=True)
            if text and not _looks_like_tool_call(text):
                return (
                    text,
                    _dt_to_iso(s.started_at),
                    _normalize_content_refs(s.content_refs),
                )

    for s in sorted_spans:
        if s.attributes_dump:
            attrs = _safe_parse_json(s.attributes_dump)
            if isinstance(attrs, dict):
                prompt = attrs.get("gen_ai.prompt")
                if prompt and isinstance(prompt, str):
                    return prompt, _dt_to_iso(s.started_at), []

    return "", "", []


# ---------------------------------------------------------------------------
# Main: build chat messages
# ---------------------------------------------------------------------------


def build_chat_messages(
    spans: list[AgentSpanSchema],
) -> list[AgentChatMessage]:
    """Convert a list of agent spans into a structured chat trajectory.

    Args:
        spans: All spans for a single trace, typically ordered by started_at.

    Returns:
        Ordered list of chat messages representing the agent trajectory.
    """
    if not spans:
        return []

    tree = build_span_tree(spans)
    messages: list[AgentChatMessage] = []
    agent_response_emitted: set[str] = set()
    # Dedup by first 200 chars to avoid hashing megabyte-scale messages
    emitted_agent_texts: set[str] = set()

    user_prompt, user_started_at, user_content_refs = find_user_prompt(spans)
    if user_prompt:
        messages.append(
            AgentChatMessage(
                type="user_message",
                text=user_prompt,
                agent_name="User",
                started_at=_dt_to_iso(user_started_at),
                content_refs=user_content_refs,
            )
        )

    def _walk(node: SpanNode, nearest_agent: str = "") -> None:
        span = node.span
        op = span.operation_name
        agent_name = (
            span.agent_name
            or nearest_agent
            or span.span_name.replace("invoke_agent ", "").replace(
                "generate_content ", ""
            )
        )

        # ---- invoke_agent ----
        if op == "invoke_agent":
            name = span.agent_name or span.span_name.replace("invoke_agent ", "")

            if span.agent_name:
                messages.append(
                    AgentChatMessage(
                        type="agent_start",
                        span_id=span.span_id,
                        agent_name=span.agent_name,
                        model=span.request_model,
                        status=span.status_code,
                        system_instructions=_extract_system_prompt(
                            span.system_instructions
                        ),
                        tool_definitions=span.tool_definitions or "",
                        started_at=_dt_to_iso(span.started_at),
                    )
                )

            for child in node.children:
                _walk(child, name)

            if span.output_messages and span.span_id not in agent_response_emitted:
                text = _extract_assistant_text(span.output_messages)
                if (
                    text
                    and not _looks_like_tool_call(text)
                    and text[:200] not in emitted_agent_texts
                ):
                    agent_response_emitted.add(span.span_id)
                    emitted_agent_texts.add(text[:200])
                    agg_in, agg_out, agg_reasoning, agg_reasoning_text = (
                        _sum_descendant_tokens(node)
                    )
                    messages.append(
                        AgentChatMessage(
                            type="agent_message",
                            span_id=span.span_id,
                            agent_name=name,
                            model=span.response_model or span.request_model,
                            text=text,
                            reasoning_content=agg_reasoning_text,
                            reasoning_tokens=agg_reasoning,
                            input_tokens=agg_in or span.input_tokens,
                            output_tokens=agg_out or span.output_tokens,
                            duration_ms=_compute_duration_ms(
                                span.started_at, span.ended_at
                            ),
                            started_at=_dt_to_iso(span.started_at),
                            status=span.status_code,
                            content_refs=_normalize_content_refs(span.content_refs),
                        )
                    )

            # Emit compaction event if this span triggered context compaction
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
            tool_name = span.tool_name or span.span_name.replace("execute_tool ", "")

            if tool_name.startswith("transfer_to_"):
                messages.append(
                    AgentChatMessage(
                        type="agent_handoff",
                        span_id=span.span_id,
                        text=tool_name.replace("transfer_to_", "→ "),
                        status=span.status_code,
                        started_at=_dt_to_iso(span.started_at),
                    )
                )
            elif tool_name not in _NOISE_TOOL_NAMES:
                messages.append(
                    AgentChatMessage(
                        type="tool_call",
                        span_id=span.span_id,
                        agent_name=span.agent_name or nearest_agent,
                        tool_name=tool_name,
                        tool_arguments=span.tool_call_arguments,
                        tool_result=span.tool_call_result,
                        duration_ms=_compute_duration_ms(
                            span.started_at, span.ended_at
                        ),
                        started_at=_dt_to_iso(span.started_at),
                        status=span.status_code,
                        content_refs=_normalize_content_refs(span.content_refs),
                    )
                )

            for child in node.children:
                _walk(child, nearest_agent)
            return

        # ---- handoff / agent_handoff ----
        if op in {"handoff", "agent_handoff"}:
            messages.append(
                AgentChatMessage(
                    type="agent_handoff",
                    span_id=span.span_id,
                    agent_name=span.agent_name,
                    text=span.span_name.replace("agent_handoff ", "→ "),
                    status=span.status_code,
                    started_at=_dt_to_iso(span.started_at),
                )
            )
            for child in node.children:
                _walk(child, nearest_agent)
            return

        # ---- chat: either walk children or emit leaf message ----
        if op == "chat":
            if node.children:
                for child in node.children:
                    _walk(child, nearest_agent)
            elif span.output_messages:
                text = _extract_assistant_text(span.output_messages)
                if (
                    text
                    and not _looks_like_tool_call(text)
                    and text not in emitted_agent_texts
                ):
                    emitted_agent_texts.add(text)
                    messages.append(
                        AgentChatMessage(
                            type="agent_message",
                            span_id=span.span_id,
                            agent_name=nearest_agent or agent_name,
                            model=span.response_model or span.request_model,
                            text=text,
                            input_tokens=span.input_tokens,
                            output_tokens=span.output_tokens,
                            duration_ms=_compute_duration_ms(
                                span.started_at, span.ended_at
                            ),
                            started_at=_dt_to_iso(span.started_at),
                            status=span.status_code,
                        )
                    )
            return

        # ---- generate_content (Google): walk children ----
        if op == "generate_content":
            for child in node.children:
                _walk(child, agent_name)
            return

        # ---- unknown/empty op (call_llm, invocation, etc.) ----
        for child in node.children:
            _walk(child, nearest_agent)

        if span.output_messages:
            text = _extract_assistant_text(span.output_messages)
            if (
                text
                and not _looks_like_tool_call(text)
                and text not in emitted_agent_texts
            ):
                emitted_agent_texts.add(text)
                messages.append(
                    AgentChatMessage(
                        type="agent_message",
                        span_id=span.span_id,
                        agent_name=nearest_agent or agent_name,
                        model=span.response_model or span.request_model,
                        text=text,
                        reasoning_content=span.reasoning_content or "",
                        reasoning_tokens=span.reasoning_tokens,
                        input_tokens=span.input_tokens,
                        output_tokens=span.output_tokens,
                        duration_ms=_compute_duration_ms(
                            span.started_at, span.ended_at
                        ),
                        started_at=_dt_to_iso(span.started_at),
                        status=span.status_code,
                    )
                )

    for root in tree:
        _walk(root)

    return messages


def build_trace_chat(
    spans: list[AgentSpanSchema],
    trace_id: str,
) -> AgentTraceChatRes:
    """Build the full chat response for a trace.

    Args:
        spans: All spans for the trace.
        trace_id: The trace identifier.

    Returns:
        Complete chat view response with metadata and messages.
    """
    messages = build_chat_messages(spans)

    root_span_name = ""
    provider = ""
    total_duration_ms = 0

    if spans:
        # Spans are already sorted by started_at from the query
        root = next(
            (s for s in spans if not s.parent_span_id),
            spans[0],
        )
        root_span_name = root.agent_name or root.span_name
        provider = root.provider_name
        total_duration_ms = _compute_duration_ms(root.started_at, root.ended_at)

    return AgentTraceChatRes(
        trace_id=trace_id,
        root_span_name=root_span_name,
        provider=provider,
        total_duration_ms=total_duration_ms,
        messages=messages,
    )
