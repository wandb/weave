"""Kafka event payloads emitted by the agent observability system."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.ch_sentinel_values import SENTINEL_EPOCH

if TYPE_CHECKING:
    from weave.trace_server.kafka import KafkaProducer

logger = logging.getLogger(__name__)

SCORE_AGENT_SPANS_TOPIC = "weave.score_agent_spans"

ScoreAgentSpansEventType = Literal["turn_ended"]


class ScoreAgentSpansEvent(BaseModel):
    """Trigger event for agent scoring."""

    event_type: ScoreAgentSpansEventType
    project_id: str
    trace_id: str
    root_span_id: str
    ended_at: datetime.datetime
    conversation_id: str | None = None
    agent_name: str | None = None
    operation_name: str | None = None
    request_model: str | None = None

    def emit(self, producer: KafkaProducer) -> None:
        """Produce this event to Kafka. Logs failures without raising."""
        try:
            producer.produce_score_agent_spans(self)
        except Exception as e:
            logger.exception("Failed to emit ScoreAgentSpansEvent")

    @staticmethod
    def from_row(row: AgentSpanCHInsertable) -> ScoreAgentSpansEvent | None:
        """Return a ScoreAgentSpansEvent from a finished span row if it matches any event_type (else None).

        Currently only "turn_ended" is supported, but the interface is designed to support multiple types.
        """
        event_type: ScoreAgentSpansEventType | None = None
        # A span with no parent is assumed to represent the end of a turn
        if not row.parent_span_id:
            event_type = "turn_ended"
        # Ignore in-progress spans
        if event_type and row.ended_at > SENTINEL_EPOCH:
            return ScoreAgentSpansEvent(
                event_type=event_type,
                project_id=row.project_id,
                trace_id=row.trace_id,
                root_span_id=row.span_id,
                ended_at=row.ended_at,
                # Resolve empty strings to None for optional fields:
                conversation_id=row.conversation_id or None,
                agent_name=row.agent_name or None,
                operation_name=row.operation_name or None,
                request_model=row.request_model or None,
            )
        return None
