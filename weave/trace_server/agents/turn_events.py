"""Helpers for emitting agent turn-completion Kafka events from ingest paths.

A turn is one OTel trace. When the root span of a trace arrives with
``ended_at`` set, we publish an ``AgentTurnEndedEvent`` to trigger downstream
scoring workers. The helpers here isolate that emit logic from the
ClickHouse ingest path so the ingest function stays small.
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

from weave.trace_server.agents.events import AgentTurnEndedEvent

if TYPE_CHECKING:
    from weave.trace_server.agents.schema import AgentSpanCHInsertable
    from weave.trace_server.kafka import KafkaProducer

logger = logging.getLogger(__name__)

_EPOCH = datetime.datetime(1970, 1, 1)


def build_turn_ended_events(
    genai_rows: list[AgentSpanCHInsertable], project_id: str
) -> list[AgentTurnEndedEvent]:
    """Return one AgentTurnEndedEvent per row that is a completed root span.

    A row qualifies when ``parent_span_id`` is empty (root) AND ``ended_at``
    is set to a real timestamp (post-epoch). Non-root spans and unfinished
    root spans are skipped.
    """
    events: list[AgentTurnEndedEvent] = []
    for row in genai_rows:
        if row.parent_span_id:
            continue
        if row.ended_at <= _EPOCH:
            continue
        events.append(
            AgentTurnEndedEvent(
                project_id=project_id,
                trace_id=row.trace_id,
                root_span_id=row.span_id,
                conversation_id=row.conversation_id,
                agent_name=row.agent_name,
                operation_name=row.operation_name,
                request_model=row.request_model,
                ended_at_ns=int(row.ended_at.timestamp() * 1_000_000_000),
            )
        )
    return events


def emit_turn_ended_events(
    producer: KafkaProducer,
    genai_rows: list[AgentSpanCHInsertable],
    project_id: str,
) -> int:
    """Produce one Kafka event per completed-root-span row. Returns emitted count.

    Safe to call with an empty or all-non-qualifying list — returns 0.
    Flushes the producer once after emitting (non-blocking flush(0)).
    """
    events = build_turn_ended_events(genai_rows, project_id)
    if not events:
        return 0
    for event in events:
        producer.produce_agent_turn_ended(event)
    producer.flush(0)
    return len(events)
