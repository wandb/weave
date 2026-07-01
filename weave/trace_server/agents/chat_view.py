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

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from weave.shared.refs_internal import WEAVE_INTERNAL_SCHEME
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
    # Query-time costs (USD). None means no contributing span had a price, so
    # the cost is unknown rather than 0 (mirrors AgentSpanSchema cost columns).
    input_cost_usd: float | None = None
    output_cost_usd: float | None = None
    total_cost_usd: float | None = None


def add_optional_cost(acc: float | None, value: float | None) -> float | None:
    """Sum two optional costs, treating None as "no contribution".

    Stays None until a non-None value appears, so a collection of entirely
    unpriced spans reports None (unknown) rather than 0.0.
    """
    if value is None:
        return acc
    return (acc or 0.0) + value


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
    root_agent_name: str | None = None
    root_agent_version: str | None = None
    root_status_code: str | None = None
    provider: str | None = None
    total_duration_ms: int | None = None
    total_cost_usd: float | None = None

    if spans:
        root = _select_root_span(spans)
        root_span_name = root.agent_name or root.span_name
        root_agent_name = root.agent_name
        root_agent_version = root.agent_version
        root_status_code = root.status_code
        provider = root.provider_name
        # `total_duration_ms` == root span wall-clock duration
        # (`root.ended_at - root.started_at`). Under OTel convention the
        # root encloses its children, so this is the elapsed time for the
        # whole turn — not a sum of child durations (which would double
        # count overlapping subagents / parallel tool calls).
        total_duration_ms = _compute_duration_ms(root.started_at, root.ended_at)
        # Cost, unlike duration, IS a sum across every span in the trace.
        for span in spans:
            total_cost_usd = add_optional_cost(total_cost_usd, span.total_cost_usd)

    return AgentTraceChatRes(
        trace_id=trace_id,
        root_span_name=root_span_name,
        agent_name=root_agent_name,
        agent_version=root_agent_version,
        status_code=root_status_code,
        provider=provider,
        total_duration_ms=total_duration_ms,
        total_cost_usd=total_cost_usd,
        messages=messages,
    )


def build_chat_messages(spans: list[AgentSpanSchema]) -> list[AgentChatMessage]:
    """Convert a list of agent spans into a linear chat trajectory.

    Walk the parent-child tree, emitting one user message per turn — each LLM
    span's *new* user input (see `ChatTraversal._emit_user_turn`) — interleaved
    with its assistant/tool events. A single realtime trace can hold many turns
    (one chat span each), so the conversation is reconstructed from the spans'
    own messages rather than assuming one user prompt per trace.

    Only when the walk surfaces no user message at all — e.g. an SDK that
    records the prompt on the enclosing `invoke_agent` span rather than the LLM
    span — do we fall back to a single synthesized leading prompt.
    """
    if not spans:
        return []

    tree = build_span_tree(spans)
    traversal = ChatTraversal()
    traversal.walk_roots(tree)

    messages = traversal.messages
    if not traversal.emitted_user and (user_message := _find_user_message(spans)):
        messages.insert(0, user_message)

    # The walk emits an invoke_agent's `agent_start` before descending to the
    # chat span that carries that turn's user message, but the user speaks
    # first and the agent is invoked in response. Restore that order so the
    # opening prompt leads (matches the single-prompt-per-trace SDK shape).
    if (
        len(messages) >= 2
        and messages[0].type == "agent_start"
        and messages[1].type == "user_message"
    ):
        messages[0], messages[1] = messages[1], messages[0]

    return messages


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
    # True once any per-turn user message has been emitted during the walk;
    # gates the invoke_agent leading-prompt fallback in build_chat_messages.
    emitted_user: bool = False
    # (text, media-digests) of the most recently emitted user message, so the
    # same message replayed by a following LLM span is not emitted twice.
    _last_user_sig: tuple[str, tuple[str, ...]] | None = None
    # The system-instructions text most recently surfaced (from either an
    # invoke_agent or a content span), so the same instructions replayed on
    # every turn's LLM span render once, not once per call. None until the
    # first instructions are emitted.
    _last_system_instructions: str | None = None
    # A just-emitted agent_start that carries an agent identity but no system
    # prompt (some SDKs record the prompt on the child LLM span, not the
    # invoke_agent span). A descendant content span's instructions fold into it
    # rather than emitting a redundant second card. Reset per invoke_agent and
    # cleared at the turn boundary (user message).
    _pending_agent_start: AgentChatMessage | None = None

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
            instructions = _join_or_none(span.system_instructions)
            if instructions:
                self._last_system_instructions = instructions
            start_msg = AgentChatMessage(
                type="agent_start",
                span_id=span.span_id,
                agent_name=agent_start_label,
                agent_version=span.agent_version,
                status_code=span.status_code,
                started_at=span.started_at,
                agent_start=AgentChatAgentStart(
                    model=span.request_model,
                    status=span.status_code,
                    system_instructions=instructions,
                    tool_definitions=span.tool_definitions or None,
                ),
            )
            self.messages.append(start_msg)
            # When the invoke_agent span carried no system prompt, let a
            # descendant content span fold its instructions into this card.
            self._pending_agent_start = None if instructions else start_msg
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
                    agent_version=span.agent_version,
                    status_code=span.status_code,
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
                agent_version=span.agent_version,
                status_code=span.status_code,
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
        """Walk a regular content span and emit its assistant text if present.

        A span that produced reasoning but no assistant text (an LLM step that
        only emitted a tool call) still emits a reasoning-only message, so
        thinking interleaved between tool calls is surfaced rather than dropped.
        Such a step is not the turn's final assistant text, so it does not
        suppress a mirrored final message on the enclosing `invoke_agent` span.
        """
        span = node.span
        agent_name = _agent_label(span, nearest_agent)
        self._emit_system_instructions(span, agent_name)
        self._emit_user_turn(span)
        subtree_emitted_assistant = self._walk_children(
            node, nearest_agent=agent_name, depth=depth
        )

        msg = _emit_assistant_message(span, agent_name)
        if msg is None:
            return subtree_emitted_assistant
        self.messages.append(msg)
        assistant = msg.assistant_message
        emitted_text = bool(assistant and assistant.text)
        return emitted_text or subtree_emitted_assistant

    def _emit_system_instructions(
        self, span: AgentSpanSchema, agent_name: str | None
    ) -> None:
        """Surface a content span's system instructions as an agent_start card.

        Providers that instrument plain LLM/chat spans (with no enclosing
        `invoke_agent` span) record ``gen_ai.system_instructions`` on each call.
        Those instructions are extracted onto every span, but only
        `_walk_invoke_agent` previously read them, so traces built from bare
        chat spans dropped their system prompt entirely. Reuse the `agent_start`
        card the UI already renders for system instructions.

        Deduped against the last-surfaced instructions (set here and by
        `_walk_invoke_agent`) so the prompt replayed on every turn's span shows
        once, not once per call; a genuinely changed prompt emits a new card.

        When the enclosing invoke_agent already emitted a bare agent_start for
        this turn (agent identity but no prompt), the instructions fold into
        that card instead of emitting a redundant second one.
        """
        instructions = _join_or_none(span.system_instructions)
        if not instructions or instructions == self._last_system_instructions:
            return
        self._last_system_instructions = instructions

        pending = self._pending_agent_start
        self._pending_agent_start = None
        if (
            pending is not None
            and pending.agent_start is not None
            and pending.agent_name == agent_name
        ):
            pending.agent_start.system_instructions = instructions
            if pending.agent_start.model is None:
                pending.agent_start.model = span.request_model
            if pending.agent_start.tool_definitions is None:
                pending.agent_start.tool_definitions = span.tool_definitions or None
            return

        self.messages.append(
            AgentChatMessage(
                type="agent_start",
                span_id=span.span_id,
                agent_name=agent_name,
                agent_version=span.agent_version,
                status_code=span.status_code,
                started_at=span.started_at,
                agent_start=AgentChatAgentStart(
                    model=span.request_model,
                    status=span.status_code,
                    system_instructions=instructions,
                    tool_definitions=span.tool_definitions or None,
                ),
            )
        )

    def _emit_user_turn(self, span: AgentSpanSchema) -> None:
        """Emit the user message(s) for the new turn this LLM span answers.

        The new user input is the trailing run of consecutive user-role
        messages in ``input_messages`` — those appended since the previous
        assistant/system message (or the start). Earlier turns are replayed as
        history and skipped; they were emitted by the span that first answered
        them. The run need not alternate: a turn can be several user messages.

        Each message becomes its own bubble so its own media stays with it;
        collapsing the run would re-group every turn's audio onto one message.
        Media comes from the message's inline ``uri`` parts, resolved to the
        internal ref form via the span's ``content_refs`` because the read path
        requires internal refs (the int->ext converter rejects a bare external
        ref).
        """
        for message in _trailing_user_messages(span.input_messages):
            text = _display_text(message.content)
            media = _message_content_refs(span, [message])
            if not text and not media:
                continue
            sig = (text, tuple(media))
            if sig == self._last_user_sig:
                continue
            self._last_user_sig = sig
            self.emitted_user = True
            # A user message marks a new turn; an unfilled agent_start from an
            # earlier turn must not absorb this turn's instructions.
            self._pending_agent_start = None
            self.messages.append(
                AgentChatMessage(
                    type="user_message",
                    agent_name="User",
                    started_at=span.started_at,
                    user_message=AgentChatUserMessage(text=text, content_refs=media),
                )
            )

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


def _display_text(content: str) -> str:
    """Extract human-readable text from a message content field.

    Content is either plain text (legacy) or a JSON-serialized parts array
    (multimodal messages).  For parts arrays, concatenate the text parts;
    reasoning parts are excluded (they surface separately via
    `reasoning_content`).  For plain text, return as-is.
    """
    if not content or not content.startswith("["):
        return content
    try:
        parts = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content
    if not isinstance(parts, list):
        return content
    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict):
            # Reasoning is rendered separately via `reasoning_content`;
            # concatenating it here would duplicate it in the message body.
            if p.get("type") == "reasoning":
                continue
            # Support both the weave parts model (``content``) and the
            # OpenAI-style multimodal shape (``text``). Non-text parts (e.g.
            # images) carry neither and are skipped for display.
            if isinstance(p.get("content"), str):
                texts.append(p["content"])
            elif isinstance(p.get("text"), str):
                texts.append(p["text"])
        elif isinstance(p, str):
            texts.append(p)
    return "\n".join(texts)


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
        text = _display_text(message.content)
        if not text:
            continue
        if include_roles is not None and role not in include_roles:
            continue
        if exclude_roles is not None and role in exclude_roles:
            continue
        texts.append(text)
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


def first_user_preview_text(messages: list[NormalizedMessage]) -> str:
    """Public: opening user-prompt text from a span's `input_messages`.

    Used to build the conversation table's "first message" preview directly
    from the grouped spans query, applying the same role resolution as the
    full chat view so previews match the opened conversation.
    """
    return _extract_user_text(messages, last_only=True)


def last_assistant_preview_text(messages: list[NormalizedMessage]) -> str:
    """Public: final assistant/output text from a span's `output_messages`."""
    return _extract_non_user_output_text(messages)


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


# Content part types that reference uploaded media by ref rather than inlining
# text. The conversation SDK emits attached media as ``uri`` parts (see
# weave/conversation/conversation_otel.py::_media_to_part); ``blob``/``file`` are accepted
# defensively in case other producers use a ref-bearing variant.
_MEDIA_PART_TYPES = {"uri", "blob", "file"}


def _parse_content_parts(content: str) -> list[dict]:
    """Parse a message ``content`` field into its parts array.

    Multimodal content is a JSON-serialized parts array (see
    genai_extraction._normalize_single_message); plain-text/legacy content is
    not a JSON list and yields nothing.
    """
    if not content or not content.startswith("["):
        return []
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [p for p in parsed if isinstance(p, dict)]


def _ref_digest(ref: str) -> str:
    """Return the trailing object digest of a content ref.

    The same object is referenced in two forms sharing one digest: the inline
    message ``uri`` part uses the external ``weave:///entity/project/...`` form,
    while the span-level ``content_refs`` uses the internal
    ``weave-trace-internal:///...`` form. Both end in ``...:<digest>``, so the
    digest is the stable key for matching one to the other.
    """
    return ref.rsplit(":", 1)[-1]


def _media_part_digests(messages: list[NormalizedMessage]) -> set[str]:
    """Object digests of media (uri/blob/file) parts inlined in ``messages``.

    Pure extraction — it carries no notion of direction. Callers decide whose
    media this is by choosing which messages to pass: media belongs to the role
    that owns the message it sits on, not to whichever input/output list it
    appears in (see ``_user_messages``).
    """
    digests: set[str] = set()
    for message in messages:
        for part in _parse_content_parts(message.content):
            if part.get("type") in _MEDIA_PART_TYPES:
                uri = part.get("uri")
                if isinstance(uri, str) and uri:
                    digests.add(_ref_digest(uri))
    return digests


def _directional_content_refs(
    span: AgentSpanSchema, part_digests: set[str]
) -> list[str]:
    """Resolve ``part_digests`` against the span's ``content_refs``.

    ``content_refs`` is a direction-agnostic digest->ref lookup holding each ref
    in the internal, int<->ext-convertible form the response pipeline requires
    (the int->ext adapter raises on a bare external ``weave:///`` ref, the form
    inline message parts carry). Returns the internal refs whose digest matches
    a supplied part digest; direction is the caller's choice of messages, never
    this lookup.
    """
    if not part_digests:
        return []
    return [r for r in _content_refs(span) if _ref_digest(r) in part_digests]


_INTERNAL_REF_PREFIX = f"{WEAVE_INTERNAL_SCHEME}:///"


def _iter_internal_refs(value: Any) -> Iterator[str]:
    """Yield every internal weave ref found anywhere in ``value``.

    Recurses through dicts/lists and attempts ``json.loads`` on strings so refs
    buried inside JSON-serialized blobs (e.g. a message ``content`` parts array)
    are not missed, regardless of which field/part shape carries them. Only
    internal-form refs are yielded: the int->ext adapter converts these and
    rejects bare external refs, and external inline refs are already handled via
    ``_directional_content_refs``.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(_INTERNAL_REF_PREFIX):
            yield stripped
        elif stripped[:1] in {"[", "{"}:
            try:
                parsed = json.loads(stripped)
            except (ValueError, TypeError):
                return
            yield from _iter_internal_refs(parsed)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_internal_refs(v)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_internal_refs(item)


def _inline_media_refs(messages: list[NormalizedMessage]) -> list[str]:
    """Internal weave refs embedded inline anywhere in ``messages``.

    Server-side content conversion replaces an inline blob with a weave ref in
    the message part itself (rather than via the span's ``content_refs``). Walk
    each message recursively so those refs render, without special-casing any
    part shape.
    """
    refs: list[str] = []
    seen: set[str] = set()
    for message in messages:
        for ref in _iter_internal_refs(message.model_dump()):
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _message_content_refs(
    span: AgentSpanSchema, messages: list[NormalizedMessage]
) -> list[str]:
    """Content refs for ``messages``: span.content_refs matched by media-part
    digest (client-uploaded media) plus internal refs found inline in the
    messages (server-converted content).
    """
    refs = list(_directional_content_refs(span, _media_part_digests(messages)))
    seen = set(refs)
    for ref in _inline_media_refs(messages):
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def _user_messages(messages: list[NormalizedMessage]) -> list[NormalizedMessage]:
    """The user's side of a message list, selected by role.

    Direction is the message role, not its input/output position: a multi-turn
    conversation replays the prior assistant turn — model-generated media and
    all — into the next turn's ``input_messages``, so selecting by position
    would mislabel that assistant audio/image as user-supplied. Uses the same
    role resolution as ``_extract_user_text``: everything that isn't
    assistant/system/tool context (explicit ``user`` plus provider-variant
    empty/unknown roles).
    """
    return [m for m in messages if m.role not in _NON_USER_PROMPT_ROLES]


def _trailing_user_messages(
    messages: list[NormalizedMessage],
) -> list[NormalizedMessage]:
    """The contiguous run of user-role messages at the end of ``messages``.

    This is the new user input an LLM span responds to: the messages appended
    since the previous assistant/system message (or the start). Earlier history
    is excluded; it was answered by earlier spans. Role decides the boundary
    (see ``_user_messages``), so the sequence need not alternate.
    """
    turn: list[NormalizedMessage] = []
    for message in reversed(messages):
        if message.role in _NON_USER_PROMPT_ROLES:
            break
        turn.append(message)
    turn.reverse()
    return turn


def _input_content_refs(spans: list[AgentSpanSchema]) -> list[str]:
    """User-supplied media refs across a trace, de-duplicated, in internal form.

    ``attach_media`` records media on the LLM/chat span, but the rendered user
    prompt is synthesized from the enclosing invoke_agent span, so media and
    user text live on different spans. Gather user-side input media across all
    spans so it lands on the user message regardless of which span carries it;
    only user-role messages contribute (see ``_user_messages``).
    """
    refs: list[str] = []
    seen: set[str] = set()
    for span in spans:
        for ref in _message_content_refs(span, _user_messages(span.input_messages)):
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _sum_descendant_tokens(node: SpanNode) -> TokenTotals:
    """Sum input, output, and reasoning tokens (and costs) across a subtree."""
    input_t = node.span.input_tokens or 0
    output_t = node.span.output_tokens or 0
    reasoning_t = node.span.reasoning_tokens or 0
    reasoning_text = node.span.reasoning_content
    input_cost_usd = node.span.input_cost_usd
    output_cost_usd = node.span.output_cost_usd
    total_cost_usd = node.span.total_cost_usd
    for child in node.children:
        child_totals = _sum_descendant_tokens(child)
        input_t += child_totals.input_tokens
        output_t += child_totals.output_tokens
        reasoning_t += child_totals.reasoning_tokens
        if child_totals.reasoning_content and not reasoning_text:
            reasoning_text = child_totals.reasoning_content
        input_cost_usd = add_optional_cost(input_cost_usd, child_totals.input_cost_usd)
        output_cost_usd = add_optional_cost(
            output_cost_usd, child_totals.output_cost_usd
        )
        total_cost_usd = add_optional_cost(total_cost_usd, child_totals.total_cost_usd)
    return TokenTotals(
        input_t,
        output_t,
        reasoning_t,
        reasoning_text,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=total_cost_usd,
    )


def _find_user_message(spans: list[AgentSpanSchema]) -> AgentChatMessage | None:
    """Find the user prompt for this trace.

    Priority order: invoke_agent spans first, then anything else, with
    started_at tiebreaking inside each group. Returns the first span whose
    `input_messages` yields user text, already shaped as an API message.

    Media direction comes from the input message parts; the ref value comes
    from `content_refs` (internal form) via `_input_content_refs`, gathered
    across the trace since `attach_media` records on the LLM span while the
    user text comes from the enclosing invoke_agent span.
    """
    user_media_refs = _input_content_refs(spans)
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
                    content_refs=user_media_refs,
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
    whole agent turn.

    A span that produced reasoning but no assistant text (e.g. an LLM step that
    only emitted a tool call) still yields a message carrying that reasoning, so
    thinking interleaved between tool calls is surfaced rather than dropped.
    Returns None only when there is neither output text nor reasoning content.
    """
    text = (
        _extract_non_user_output_text(span.output_messages)
        if span.output_messages
        else ""
    )
    if not text and not span.reasoning_content:
        return None

    if aggregate_node:
        totals = _sum_descendant_tokens(aggregate_node)
    else:
        totals = TokenTotals(
            input_tokens=span.input_tokens or 0,
            output_tokens=span.output_tokens or 0,
            reasoning_tokens=span.reasoning_tokens or 0,
            reasoning_content=span.reasoning_content,
            input_cost_usd=span.input_cost_usd,
            output_cost_usd=span.output_cost_usd,
            total_cost_usd=span.total_cost_usd,
        )

    return AgentChatMessage(
        type="assistant_message",
        span_id=span.span_id,
        agent_name=agent_name,
        agent_version=span.agent_version,
        status_code=span.status_code,
        started_at=span.started_at,
        assistant_message=AgentChatAssistantMessage(
            model=span.response_model or span.request_model,
            text=text,
            reasoning_content=totals.reasoning_content,
            reasoning_tokens=totals.reasoning_tokens,
            input_tokens=totals.input_tokens or span.input_tokens,
            output_tokens=totals.output_tokens or span.output_tokens,
            input_cost_usd=totals.input_cost_usd,
            output_cost_usd=totals.output_cost_usd,
            total_cost_usd=totals.total_cost_usd,
            duration_ms=_compute_duration_ms(span.started_at, span.ended_at),
            status=span.status_code,
            content_refs=_message_content_refs(span, span.output_messages),
        ),
    )
