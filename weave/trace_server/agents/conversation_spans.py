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
    AgentConversationSpanRating,
)
from weave.trace_server.emoji_util import detone_emojis
from weave.trace_server.interface.feedback_types import AGENT_SPAN_FEEDBACK_TYPES
from weave.trace_server.query_builder.agent_query_builder import (
    coerce_literal,
    safe_float,
    safe_int,
    safe_str,
)


def is_supported_feedback(feedback_type: str) -> bool:
    """Whether a feedback row's type is surfaced by agent_conversation_spans."""
    return feedback_type in AGENT_SPAN_FEEDBACK_TYPES


# Valid span status codes; unexpected SQL values coerce to "UNSET".
_STATUS_CODES: frozenset[StatusCodeLiteral] = frozenset(get_args(StatusCodeLiteral))


def parse_conversation_spans(raw: object) -> list[AgentConversationSpan]:
    """Parse a conversation's `spans` array into typed spans.

    Defensive: skips malformed tuples and coerces an unknown status to "UNSET"
    so one bad row never breaks the best-effort spans hydration. Tuple shape is
    `(started_at, operation_name, trace_id, span_id, status_code, duration_ms)`;
    `started_at` was only the sort key and is dropped here.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    spans: list[AgentConversationSpan] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 6:
            continue
        status: StatusCodeLiteral = coerce_literal(
            safe_str(item[4]), _STATUS_CODES, "UNSET"
        )
        spans.append(
            AgentConversationSpan(
                operation_name=safe_str(item[1]),
                trace_id=safe_str(item[2]),
                span_id=safe_str(item[3]),
                status=status,
                duration_ms=safe_int(item[5]),
            )
        )
    return spans


def _feedback_tags(raw: dict[str, Any]) -> list[str]:
    """Return the `scorer_tags` on a feedback row, skin-tone-detoned.

    Emoji tags come back as the detoned glyph (so the client renders it
    directly); text tags pass through unchanged.
    """
    tags = raw.get("scorer_tags")
    if not isinstance(tags, list):
        return []
    return [detone_emojis(tag) for tag in tags if isinstance(tag, str) and tag]


def _feedback_ratings(raw: dict[str, Any]) -> list[AgentConversationSpanRating]:
    """Return the `scorer_ratings` on a feedback row.

    Each rating is a name -> value pair; optional reason/confidence are joined
    in from the parallel `scorer_rating_reasons` / `scorer_rating_confidences`
    maps by rating name.
    """
    ratings = raw.get("scorer_ratings")
    if not isinstance(ratings, dict):
        return []
    reasons = raw.get("scorer_rating_reasons")
    confidences = raw.get("scorer_rating_confidences")
    reasons = reasons if isinstance(reasons, dict) else {}
    confidences = confidences if isinstance(confidences, dict) else {}
    out: list[AgentConversationSpanRating] = []
    for name, value in ratings.items():
        if not isinstance(name, str):
            continue
        reason = reasons.get(name)
        confidence = confidences.get(name)
        out.append(
            AgentConversationSpanRating(
                name=name,
                value=safe_float(value),
                reason=reason if isinstance(reason, str) and reason else None,
                confidence=safe_float(confidence)
                if isinstance(confidence, (int, float))
                else None,
            )
        )
    return out


def span_feedback_marker(
    raw: dict[str, Any], *, trace_id: str | None
) -> AgentConversationSpanFeedback:
    """Shape a supported feedback row into a positioned feedback marker.

    `trace_id` is the turn the feedback is anchored to, or None for
    conversation-level feedback. Callers must filter to `is_supported_feedback`
    rows first, since `feedback_type` is a constrained literal.
    """
    feedback_type = safe_str(raw.get("feedback_type"))
    return AgentConversationSpanFeedback(
        trace_id=trace_id,
        feedback_type=feedback_type,  # type: ignore[arg-type]  # caller filters
        tags=_feedback_tags(raw),
        ratings=_feedback_ratings(raw),
    )
