"""Kafka event payloads emitted by the agent observability system."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

from weave.trace_server.agents.schema import (
    AgentSpanCHInsertable,
    AgentSpanOpName,
    StatusCodeLiteral,
)
from weave.trace_server.ch_sentinel_values import SENTINEL_EPOCH as SENTINEL_EPOCH_UTC

if TYPE_CHECKING:
    from weave.trace_server.kafka import KafkaProducer

logger = logging.getLogger(__name__)

SCORE_AGENT_SPANS_TOPIC = "weave.score_agent_spans"

_SENTINEL_EPOCH_NAIVE = SENTINEL_EPOCH_UTC.replace(tzinfo=None)


class ScoreAgentSpansEvent(BaseModel):
    """Trigger event for agent scoring."""

    event_type: AgentSpanOpName
    status_code: StatusCodeLiteral
    project_id: str
    trace_id: str
    span_id: str
    operation_name: str | None
    parent_span_id: str | None
    conversation_id: str | None

    def emit(self, producer: KafkaProducer | None) -> None:
        """Produce this event to Kafka. Logs failures without raising."""
        if producer is None:
            return
        try:
            producer.produce_score_agent_spans(self)
        except Exception:
            logger.exception("Failed to emit ScoreAgentSpansEvent")

    @staticmethod
    def from_row(row: AgentSpanCHInsertable) -> ScoreAgentSpansEvent | None:
        """Return a ScoreAgentSpansEvent from a finished span row if it matches any event_type (else None).

        Currently only "turn_ended" is supported, but the interface is designed to support multiple types.
        """
        event_type: AgentSpanOpName | None = None
        # A span with no parent is assumed to represent the end of a turn
        if not row.parent_span_id:
            event_type = "weave.genai.turn_ended"
        # Ignore in-progress spans
        if event_type and row.ended_at > _SENTINEL_EPOCH_NAIVE:
            return ScoreAgentSpansEvent(
                event_type=event_type,
                status_code=row.status_code,
                project_id=row.project_id,
                trace_id=row.trace_id,
                span_id=row.span_id,
                # Resolve optional fields to None (instead of empty strings)
                parent_span_id=row.parent_span_id or None,
                conversation_id=row.conversation_id or None,
                operation_name=row.operation_name or None,
            )
        return None
