"""Unit tests for the agent scorer event helpers."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from weave.trace_server.agents.kafka_events import (
    ScoreAgentSpansEvent,
    emit_scorer_events,
    make_turn_ended_event,
)
from weave.trace_server.agents.schema import AgentSpanCHInsertable

_LATER = datetime.datetime(2024, 1, 1, 12, 0, 0)


def _make_row(
    *,
    span_id: str = "s",
    parent_span_id: str = "",
    trace_id: str = "t",
    ended_at: datetime.datetime | None = None,
    **kwargs,
) -> AgentSpanCHInsertable:
    return AgentSpanCHInsertable(
        project_id="p",
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        span_name="n",
        started_at=datetime.datetime(2024, 1, 1, 11, 0, 0),
        ended_at=ended_at if ended_at is not None else datetime.datetime(1970, 1, 1),
        **kwargs,
    )


def test_emit_events_produces_and_flushes() -> None:
    producer = MagicMock()
    events = [
        ScoreAgentSpansEvent(
            event_type="turn_ended",
            project_id="p",
            trace_id="t",
            root_span_id="r",
            ended_at=_LATER,
        )
    ]

    count = emit_scorer_events(producer, events)

    assert count == 1
    producer.produce_agent_scorer_event.assert_called_once()
    event_arg = producer.produce_agent_scorer_event.call_args.args[0]
    assert isinstance(event_arg, ScoreAgentSpansEvent)
    producer.flush.assert_called_once_with(0)


def test_emit_events_noop_on_empty_list() -> None:
    producer = MagicMock()

    count = emit_scorer_events(producer, [])

    assert count == 0
    producer.produce_agent_scorer_event.assert_not_called()
    producer.flush.assert_not_called()
