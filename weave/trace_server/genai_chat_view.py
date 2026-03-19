"""Normalize GenAI spans into a structured chat / agent trajectory view.

Converts a flat list of ``GenAISpanSchema`` rows (from the ``genai_spans``
table) into a linear sequence of ``GenAIChatMessage`` objects suitable for
rendering an agent conversation UI.

The normalization handles provider-specific formats (OpenAI Agents SDK,
Google ADK) and produces a unified output.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from weave.trace_server.trace_server_interface import (
    GenAIChatMessage,
    GenAISpanSchema,
    GenAITraceChatRes,
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


def _parse_content_refs(raw: str) -> str:
    """Validate content_refs is well-formed JSON; pass through or empty."""
    if not raw:
        return ""
    parsed = _safe_parse_json(raw)
    if isinstance(parsed, list):
        return raw
    try:
        fixed = raw.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")
        parsed = json.loads(fixed)
        if isinstance(parsed, list):
            return json.dumps(parsed)
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


# ---------------------------------------------------------------------------
# Text extraction from message formats
# ---------------------------------------------------------------------------


def _extract_text_from_parts(parts: list[Any]) -> str:
    """Extract text from message parts (OpenAI and Google formats)."""
    texts: list[str] = []
    for p in parts:
        if isinstance(p, str):
            texts.append(p)
        elif isinstance(p, dict):
            if "content" in p and isinstance(p["content"], str):
                texts.append(p["content"])
            elif "text" in p and isinstance(p["text"], str):
                texts.append(p["text"])
    return "\n".join(texts)


def _extract_user_text(raw: Any, *, last_only: bool = False) -> str:
    """Extract user text from input_messages.

    Args:
        raw: Parsed JSON from input_messages.
        last_only: If True, return only the last user message (multi-turn).
    """
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw

    texts: list[str] = []

    # Google format: {contents: [{role: "user", parts: [{text: "..."}]}]}
    if isinstance(raw, dict) and "contents" in raw and isinstance(raw["contents"], list):
        for c in raw["contents"]:
            if isinstance(c, dict) and c.get("role") == "user" and isinstance(c.get("parts"), list):
                t = _extract_text_from_parts(c["parts"])
                if t:
                    texts.append(t)
        if last_only and texts:
            return texts[-1]
        return "\n".join(texts) if texts else ""

    # OpenAI format: [{role: "user", parts: [{content: "..."}]}]
    if isinstance(raw, list):
        for msg in raw:
            if isinstance(msg, str):
                texts.append(msg)
                continue
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "user")
            if role != "user":
                continue
            if isinstance(msg.get("parts"), list):
                t = _extract_text_from_parts(msg["parts"])
                if t:
                    texts.append(t)
            elif isinstance(msg.get("content"), str):
                texts.append(msg["content"])
        if last_only and texts:
            return texts[-1]
        return "\n".join(texts) if texts else ""

    return ""


def _extract_assistant_text(raw: Any) -> str:
    """Extract assistant (non-user) text from output_messages."""
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw

    # Google format: {content: {parts: [{text: "..."}]}}
    if isinstance(raw, dict) and "content" in raw:
        content = raw["content"]
        if isinstance(content, dict) and isinstance(content.get("parts"), list):
            return _extract_text_from_parts(content["parts"])
        if isinstance(content, str):
            return content
        return ""

    # OpenAI format: [{role: "assistant", parts: [...]}]
    if isinstance(raw, list):
        texts: list[str] = []
        for msg in raw:
            if isinstance(msg, str):
                texts.append(msg)
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "user":
                continue
            if isinstance(msg.get("parts"), list):
                texts.append(_extract_text_from_parts(msg["parts"]))
            elif isinstance(msg.get("content"), str):
                texts.append(msg["content"])
        return "\n".join(t for t in texts if t)

    return ""


def _extract_system_prompt(raw: str) -> str:
    """Extract readable system prompt from system_instructions JSON."""
    if not raw:
        return ""
    parsed = _safe_parse_json(raw)
    if parsed is None:
        return raw
    if isinstance(parsed, str):
        return parsed
    if isinstance(parsed, list):
        return "\n".join(
            m.get("content", "") or m.get("text", "")
            for m in parsed
            if isinstance(m, dict) and (m.get("content") or m.get("text"))
        )
    return ""


def _looks_like_tool_call(text: str) -> bool:
    """Detect text that is tool-call metadata rather than human-readable content."""
    t = text.strip()
    return (
        t.startswith("ResponseFunctionToolCall(")
        or t.startswith("transfer_to_")
        or t.startswith('{"tool_calls"')
        or t.startswith('[{"tool_calls"')
    )


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
        from datetime import datetime

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

    span: GenAISpanSchema
    children: list[SpanNode] = field(default_factory=list)


def build_span_tree(spans: list[GenAISpanSchema]) -> list[SpanNode]:
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


def find_user_prompt(spans: list[GenAISpanSchema]) -> tuple[str, str]:
    """Pre-scan spans to find the user prompt for this trace.

    Uses last_only=True because multi-turn conversations send the full
    history as input_messages, and we only want the current turn's prompt.

    Returns:
        (prompt_text, started_at) — started_at is the ISO timestamp of the
        span that carried the user prompt, or empty string if not found.
    """
    sorted_spans = sorted(spans, key=lambda s: s.started_at or "")

    for s in sorted_spans:
        if s.operation_name == "invoke_agent" and s.input_messages:
            text = _extract_user_text(_safe_parse_json(s.input_messages), last_only=True)
            if text and not _looks_like_tool_call(text):
                return text, _dt_to_iso(s.started_at)

    for s in sorted_spans:
        if s.input_messages:
            text = _extract_user_text(_safe_parse_json(s.input_messages), last_only=True)
            if text and not _looks_like_tool_call(text):
                return text, _dt_to_iso(s.started_at)

    for s in sorted_spans:
        if s.attributes_dump:
            attrs = _safe_parse_json(s.attributes_dump)
            if isinstance(attrs, dict):
                prompt = attrs.get("gen_ai.prompt")
                if prompt and isinstance(prompt, str):
                    return prompt, _dt_to_iso(s.started_at)

    return "", ""


# ---------------------------------------------------------------------------
# Main: build chat messages
# ---------------------------------------------------------------------------


def build_chat_messages(
    spans: list[GenAISpanSchema],
) -> list[GenAIChatMessage]:
    """Convert a list of GenAI spans into a structured chat trajectory.

    Args:
        spans: All spans for a single trace, typically ordered by started_at.

    Returns:
        Ordered list of chat messages representing the agent trajectory.
    """
    if not spans:
        return []

    tree = build_span_tree(spans)
    messages: list[GenAIChatMessage] = []
    agent_response_emitted: set[str] = set()

    user_prompt, user_started_at = find_user_prompt(spans)
    if user_prompt:
        messages.append(
            GenAIChatMessage(
                type="user_message",
                text=user_prompt,
                agent_name="User",
                started_at=_dt_to_iso(user_started_at),
            )
        )

    def _walk(node: SpanNode, nearest_agent: str = "") -> None:
        span = node.span
        op = span.operation_name
        agent_name = (
            span.agent_name
            or nearest_agent
            or span.span_name.replace("invoke_agent ", "").replace("generate_content ", "")
        )

        # ---- invoke_agent ----
        if op == "invoke_agent":
            name = span.agent_name or span.span_name.replace("invoke_agent ", "")

            if span.agent_name:
                messages.append(
                    GenAIChatMessage(
                        type="agent_start",
                        span_id=span.span_id,
                        agent_name=span.agent_name,
                        model=span.request_model,
                        status=span.status_code,
                        system_instructions=_extract_system_prompt(span.system_instructions),
                        tool_definitions=span.tool_definitions or "",
                        started_at=_dt_to_iso(span.started_at),
                    )
                )

            for child in node.children:
                _walk(child, name)

            if span.output_messages and span.span_id not in agent_response_emitted:
                text = _extract_assistant_text(_safe_parse_json(span.output_messages))
                if text and not _looks_like_tool_call(text):
                    agent_response_emitted.add(span.span_id)
                    # Tokens live on child chat spans, not on the invoke_agent
                    # span itself, so aggregate across the whole subtree.
                    agg_in, agg_out, agg_reasoning, agg_reasoning_text = (
                        _sum_descendant_tokens(node)
                    )
                    messages.append(
                        GenAIChatMessage(
                            type="agent_message",
                            span_id=span.span_id,
                            agent_name=name,
                            model=span.response_model or span.request_model,
                            text=text,
                            reasoning_content=agg_reasoning_text,
                            reasoning_tokens=agg_reasoning,
                            input_tokens=agg_in or span.input_tokens,
                            output_tokens=agg_out or span.output_tokens,
                            duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
                            started_at=_dt_to_iso(span.started_at),
                            status=span.status_code,
                            content_refs=_parse_content_refs(span.content_refs),
                        )
                    )

            # Emit compaction event if this span triggered context compaction
            if span.compaction_summary or span.compaction_items_before > 0:
                messages.append(
                    GenAIChatMessage(
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
                    GenAIChatMessage(
                        type="agent_handoff",
                        span_id=span.span_id,
                        text=tool_name.replace("transfer_to_", "→ "),
                        status=span.status_code,
                        started_at=_dt_to_iso(span.started_at),
                    )
                )
            elif tool_name not in _NOISE_TOOL_NAMES:
                messages.append(
                    GenAIChatMessage(
                        type="tool_call",
                        span_id=span.span_id,
                        agent_name=span.agent_name or nearest_agent,
                        tool_name=tool_name,
                        tool_arguments=span.tool_call_arguments,
                        tool_result=span.tool_call_result,
                        duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
                        started_at=_dt_to_iso(span.started_at),
                        status=span.status_code,
                        content_refs=_parse_content_refs(span.content_refs),
                    )
                )

            for child in node.children:
                _walk(child, nearest_agent)
            return

        # ---- handoff / agent_handoff ----
        if op in {"handoff", "agent_handoff"}:
            messages.append(
                GenAIChatMessage(
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
                text = _extract_assistant_text(_safe_parse_json(span.output_messages))
                if text and not _looks_like_tool_call(text):
                    messages.append(
                        GenAIChatMessage(
                            type="agent_message",
                            span_id=span.span_id,
                            agent_name=nearest_agent or agent_name,
                            model=span.response_model or span.request_model,
                            text=text,
                            input_tokens=span.input_tokens,
                            output_tokens=span.output_tokens,
                            duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
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
            text = _extract_assistant_text(_safe_parse_json(span.output_messages))
            if text and not _looks_like_tool_call(text):
                messages.append(
                    GenAIChatMessage(
                        type="agent_message",
                        span_id=span.span_id,
                        agent_name=nearest_agent or agent_name,
                        model=span.response_model or span.request_model,
                        text=text,
                        reasoning_content=span.reasoning_content or "",
                        reasoning_tokens=span.reasoning_tokens,
                        input_tokens=span.input_tokens,
                        output_tokens=span.output_tokens,
                        duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
                        started_at=_dt_to_iso(span.started_at),
                        status=span.status_code,
                    )
                )


    for root in tree:
        _walk(root)

    return messages


def build_trace_chat(
    spans: list[GenAISpanSchema],
    trace_id: str,
) -> GenAITraceChatRes:
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
        sorted_spans = sorted(spans, key=lambda s: s.started_at or "")
        root = next(
            (s for s in sorted_spans if not s.parent_span_id),
            sorted_spans[0],
        )
        root_span_name = root.agent_name or root.span_name
        provider = root.provider_name
        total_duration_ms = _compute_duration_ms(root.started_at, root.ended_at)

    return GenAITraceChatRes(
        trace_id=trace_id,
        root_span_name=root_span_name,
        provider=provider,
        total_duration_ms=total_duration_ms,
        messages=messages,
    )
