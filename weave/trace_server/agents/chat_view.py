"""Normalize agent spans into a structured chat / agent trajectory view.

The database stores a trace as tree-shaped span rows. The chat UI needs a
linear timeline, so this module projects the span tree into ordered
`AgentChatMessage` events: one leading user prompt, then lifecycle markers,
tool calls, assistant responses, and context compaction events.

This is a Weave product projection, not an OTel semantic-convention layer.
Subagent spans remain inline in the same turn, inheriting the nearest enclosing
agent label unless they provide their own. When SDKs mirror the final assistant
text onto both an `invoke_agent` span and a descendant LLM span, the descendant
message wins and the parent invoke output is suppressed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from weave.trace_server.agents.constants import (
    MAX_WALK_DEPTH,
    OP_EXECUTE_TOOL,
    OP_INVOKE_AGENT,
)
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import (
    AgentChatAgentStart,
    AgentChatAssistantMessage,
    AgentChatContextCompacted,
    AgentChatMessage,
    AgentChatToolCall,
    AgentChatUserMessage,
    AgentSpanSchema,
    AgentTraceChatRes,
)

logger = logging.getLogger(__name__)

_USER_ROLE = "user"
_ASSISTANT_ROLE = "assistant"
# Provider SDKs may emit non-standard roles in their normalized message arrays.
# Treat tool/system/assistant-like entries as context rather than user prompts.
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


def _root_sort_key(span: AgentSpanSchema) -> tuple[float, str]:
    """Prefer spans that ended latest when a trace has no single root."""
    return (_datetime_sort_seconds(span.ended_at), span.span_id)


def _own_agent_label(span: AgentSpanSchema) -> str | None:
    """Return this span's own agent identity, preferring display name over id."""
    return span.agent_name or span.agent_id or None


def _agent_label(span: AgentSpanSchema, nearest_agent: str | None) -> str | None:
    """Return this span's agent label, inheriting from the nearest agent."""
    return _own_agent_label(span) or nearest_agent


def _invoke_agent_label(span: AgentSpanSchema, nearest_agent: str | None) -> str | None:
    """Return the label descendants should inherit from an invoke_agent span."""
    span_name = span.span_name or ""
    span_name_label = (
        span_name.removeprefix(f"{OP_INVOKE_AGENT} ").strip()
        if span_name.startswith(f"{OP_INVOKE_AGENT} ")
        else None
    )
    return _agent_label(span, nearest_agent) or span_name_label or None


def _has_agent_start_payload(span: AgentSpanSchema, agent_label: str | None) -> bool:
    """Return whether an invoke_agent span has useful lifecycle data to show."""
    return bool(
        agent_label
        or span.request_model
        or span.system_instructions
        or span.tool_definitions
    )


def _join_or_none(items: list[str]) -> str | None:
    if not items:
        return None
    return "\n".join(items)


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

    Build the parent-child tree, prepend a single user prompt if one can be
    found, then let `ChatTraversal` apply the explicit tree-walk policy.
    """
    if not spans:
        return []

    tree = build_span_tree(spans)
    traversal = ChatTraversal()

    if user_message := _find_user_message(spans):
        traversal.messages.append(user_message)

    traversal.walk_roots(tree)
    return traversal.messages


@dataclass
class ChatTraversal:
    """Stateful span-tree to chat-timeline traversal.

    The traversal emits lifecycle and tool events as it enters spans, then
    walks children. Content spans may emit assistant text after children. An
    `invoke_agent` span emits its own assistant text only when no descendant
    already emitted one; that boolean return value is the mirror-suppression
    signal for parent agent spans.
    """

    messages: list[AgentChatMessage] = field(default_factory=list)

    def walk_roots(self, roots: list[SpanNode]) -> None:
        for root in roots:
            self._walk_node(root, nearest_agent=None, depth=0)

    def _walk_node(self, node: SpanNode, nearest_agent: str | None, depth: int) -> bool:
        """Walk one subtree and return whether it emitted assistant text."""
        span = node.span
        if depth > MAX_WALK_DEPTH:
            logger.warning(
                "span tree walk truncated at depth %d (trace_id=%s, span_id=%s)",
                depth,
                span.trace_id,
                span.span_id,
            )
            return False

        if span.operation_name == OP_INVOKE_AGENT:
            return self._walk_invoke_agent(node, nearest_agent, depth)
        if span.operation_name == OP_EXECUTE_TOOL:
            return self._walk_tool(node, nearest_agent, depth)
        return self._walk_content_span(node, nearest_agent, depth)

    def _walk_invoke_agent(
        self, node: SpanNode, nearest_agent: str | None, depth: int
    ) -> bool:
        """Walk an agent invocation and suppress mirrored parent output."""
        span = node.span
        agent_start_label = _own_agent_label(span)
        subtree_agent = _invoke_agent_label(span, nearest_agent)

        if _has_agent_start_payload(span, agent_start_label):
            # TODO: Move type-specific payload construction into AgentChat*
            # constructors once this projection stabilizes, so traversal
            # methods only encode ordering/suppression policy.
            self.messages.append(
                AgentChatMessage(
                    type="agent_start",
                    span_id=span.span_id,
                    agent_name=agent_start_label,
                    started_at=span.started_at,
                    agent_start=AgentChatAgentStart(
                        model=span.request_model,
                        status=span.status_code,
                        system_instructions=_join_or_none(span.system_instructions),
                        tool_definitions=span.tool_definitions or None,
                    ),
                )
            )
        else:
            logger.debug(
                "invoke_agent span without agent identity or lifecycle metadata (span_id=%s)",
                span.span_id,
            )

        if span.compaction_summary or (span.compaction_items_before or 0) > 0:
            self.messages.append(
                AgentChatMessage(
                    type="context_compacted",
                    span_id=span.span_id,
                    agent_name=subtree_agent,
                    started_at=span.started_at,
                    context_compacted=AgentChatContextCompacted(
                        compaction_summary=span.compaction_summary,
                        compaction_items_before=span.compaction_items_before,
                        compaction_items_after=span.compaction_items_after,
                    ),
                )
            )

        subtree_emitted_assistant = self._walk_children(
            node, nearest_agent=subtree_agent, depth=depth
        )
        if not subtree_emitted_assistant:
            msg = _emit_assistant_message(span, subtree_agent, aggregate_node=node)
            if msg:
                self.messages.append(msg)
                subtree_emitted_assistant = True

        return subtree_emitted_assistant

    def _walk_tool(self, node: SpanNode, nearest_agent: str | None, depth: int) -> bool:
        """Emit a tool-call event, then walk any nested spans below it."""
        span = node.span
        agent_name = _agent_label(span, nearest_agent)
        span_name = span.span_name or ""
        tool_name = span.tool_name or span_name.removeprefix(f"{OP_EXECUTE_TOOL} ")
        self.messages.append(
            AgentChatMessage(
                type="tool_call",
                span_id=span.span_id,
                agent_name=agent_name,
                started_at=span.started_at,
                tool_call=AgentChatToolCall(
                    tool_name=tool_name,
                    tool_arguments=span.tool_call_arguments,
                    tool_result=span.tool_call_result,
                    duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
                    status=span.status_code,
                    content_refs=_content_refs(span),
                ),
            )
        )
        return self._walk_children(node, nearest_agent=agent_name, depth=depth)

    def _walk_content_span(
        self, node: SpanNode, nearest_agent: str | None, depth: int
    ) -> bool:
        """Walk a regular content span and emit its assistant text if present."""
        span = node.span
        agent_name = _agent_label(span, nearest_agent)
        subtree_emitted_assistant = self._walk_children(
            node, nearest_agent=agent_name, depth=depth
        )

        msg = _emit_assistant_message(span, agent_name)
        if msg:
            self.messages.append(msg)
            return True
        return subtree_emitted_assistant

    def _walk_children(
        self, node: SpanNode, nearest_agent: str | None, depth: int
    ) -> bool:
        """Walk children and return whether any child subtree emitted assistant text."""
        emitted_assistant = False
        for child in node.children:
            if self._walk_node(child, nearest_agent, depth + 1):
                emitted_assistant = True
        return emitted_assistant


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


def _filter_message_texts(
    messages: list[NormalizedMessage],
    *,
    include_roles: set[str] | None = None,
    exclude_roles: set[str] | None = None,
) -> list[str]:
    """Return non-empty message content matching role include/exclude filters."""
    texts: list[str] = []
    for message in messages:
        role = message.role
        content = message.content
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
                [m.role for m in messages],
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


def _compute_duration_ms(started_at: datetime | None, ended_at: datetime | None) -> int:
    """Return elapsed milliseconds, or 0 when either timestamp is missing."""
    if not started_at or not ended_at:
        return 0
    delta = ended_at - started_at
    return max(0, int(delta.total_seconds() * 1000))


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
                agent_name="User",
                started_at=s.started_at,
                user_message=AgentChatUserMessage(
                    text=text,
                    content_refs=_content_refs(s),
                ),
            )
    return None


def _emit_assistant_message(
    span: AgentSpanSchema,
    agent_name: str | None,
    *,
    aggregate_node: SpanNode | None = None,
) -> AgentChatMessage | None:
    """Build a renderable assistant_message from a span's output_messages.

    `invoke_agent` spans sometimes mirror the final assistant text from a
    descendant LLM span. Callers pass `aggregate_node` only when the invoke span
    itself needs to emit because no descendant already did; in that case token
    usage is summed across the subtree so the emitted message reflects the
    whole agent turn. Returns None when there is no non-user output text.
    """
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
        started_at=span.started_at,
        assistant_message=AgentChatAssistantMessage(
            model=span.response_model or span.request_model,
            text=text,
            reasoning_content=totals.reasoning_content,
            reasoning_tokens=totals.reasoning_tokens,
            input_tokens=totals.input_tokens or span.input_tokens,
            output_tokens=totals.output_tokens or span.output_tokens,
            duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
            status=span.status_code,
            content_refs=_content_refs(span),
        ),
    )
