"""Pure transforms for a conversation's span sequence and its feedback markers.

These helpers shape raw ClickHouse output into the typed `AgentConversationSpan`
/ `AgentConversationSpanFeedback` models returned by `agent_conversation_spans`.
They hold no database or `self` state — the query execution lives in
`clickhouse.py`, which imports from here — so they can be reasoned about and
tested in isolation.
"""

from typing import Any, get_args

from weave.trace_server.agents.schema import StatusCodeLiteral
from weave.trace_server.agents.types import (
    AgentConversationSpan,
    AgentConversationSpanFeedback,
    ConversationSpanKind,
)
from weave.trace_server.emoji_util import detone_emojis
from weave.trace_server.interface.feedback_types import (
    AGENT_USER_FEEDBACK_TYPE,
    REACTION_FEEDBACK_TYPE,
)
from weave.trace_server.query_builder.agent_query_builder import (
    coerce_literal,
    safe_int,
    safe_str,
)

# Valid span kinds; unexpected SQL values coerce to "unknown".
_SPAN_KINDS: frozenset[ConversationSpanKind] = frozenset(get_args(ConversationSpanKind))

# Valid span status codes; unexpected SQL values coerce to "UNSET".
_STATUS_CODES: frozenset[StatusCodeLiteral] = frozenset(get_args(StatusCodeLiteral))


def parse_conversation_spans(raw: object) -> list[AgentConversationSpan]:
    """Parse a conversation's `spans` array into typed spans.

    Defensive: skips malformed tuples and coerces unknown kinds to "unknown" so
    one bad row never breaks the best-effort spans hydration. Tuple shape is
    `(started_at, kind, trace_id, span_id, status_code, duration_ms)`;
    `started_at` was only the sort key and is dropped here.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    spans: list[AgentConversationSpan] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 6:
            continue
        kind: ConversationSpanKind = coerce_literal(
            safe_str(item[1]), _SPAN_KINDS, "unknown"
        )
        status: StatusCodeLiteral = coerce_literal(
            safe_str(item[4]), _STATUS_CODES, "UNSET"
        )
        spans.append(
            AgentConversationSpan(
                kind=kind,
                trace_id=safe_str(item[2]),
                span_id=safe_str(item[3]),
                status=status,
                duration_ms=safe_int(item[5]),
            )
        )
    return spans


def _feedback_tags(feedback_type: str, raw: dict[str, Any]) -> list[str]:
    """Return the human tags on a feedback row, skin-tone-detoned.

    Agent user feedback carries its tags in `scorer_tags`; a classic reaction is
    a single emoji tag in its payload. Emoji tags come back as the detoned glyph
    (so the client renders it directly); text tags pass through unchanged.
    """
    if feedback_type == REACTION_FEEDBACK_TYPE:
        payload = raw.get("payload")
        glyph = payload.get("detoned") if isinstance(payload, dict) else None
        return [glyph] if isinstance(glyph, str) and glyph else []
    if feedback_type == AGENT_USER_FEEDBACK_TYPE:
        tags = raw.get("scorer_tags")
        if not isinstance(tags, list):
            return []
        return [detone_emojis(tag) for tag in tags if isinstance(tag, str) and tag]
    return []


def span_feedback_marker(
    raw: dict[str, Any], *, trace_id: str | None
) -> AgentConversationSpanFeedback:
    """Shape a raw feedback row into a positioned feedback marker.

    `trace_id` is the turn the feedback is anchored to, or None for
    conversation-level feedback.
    """
    feedback_type = safe_str(raw.get("feedback_type"))
    return AgentConversationSpanFeedback(
        trace_id=trace_id,
        feedback_type=feedback_type,
        tags=_feedback_tags(feedback_type, raw),
    )
