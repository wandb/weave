"""Unit tests for ScoreAgentSpansEvent."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.kafka_events import ScoreAgentSpansEvent
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.ch_sentinel_values import SENTINEL_EPOCH

_STARTED_AT = datetime.datetime(2024, 1, 1, 11, 0, 0, tzinfo=datetime.timezone.utc)
_ENDED_AT = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)


def test_from_row() -> None:
    """A finished root span yields a turn_ended event; a child span yields None."""
    root_row = AgentSpanCHInsertable(
        project_id="p",
        trace_id="tr",
        span_id="root",
        parent_span_id="",
        span_name="root",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
        conversation_id="c",
        agent_name="a",
        operation_name="invoke_agent",
        request_model="gpt-5",
    )
    event = ScoreAgentSpansEvent.from_row(root_row)
    assert event == ScoreAgentSpansEvent(
        event_type="turn_ended",
        project_id="p",
        trace_id="tr",
        root_span_id="root",
        ended_at=_ENDED_AT,
        conversation_id="c",
        agent_name="a",
        operation_name="invoke_agent",
        request_model="gpt-5",
    )

    child_row = AgentSpanCHInsertable(
        project_id="p",
        trace_id="tr",
        span_id="child",
        parent_span_id="root",
        span_name="child",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
    )
    assert ScoreAgentSpansEvent.from_row(child_row) is None
