"""Unit tests for ScoreAgentSpansEvent."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.kafka_events import (
    EmbedAgentSpansEvent,
    ScoreAgentSpansEvent,
)
from weave.trace_server.agents.schema import AgentSpanCHInsertable

_STARTED_AT = datetime.datetime(2024, 1, 1, 11, 0, 0)
_ENDED_AT = datetime.datetime(2024, 1, 1, 12, 0, 0)


def test_from_row() -> None:
    """A finished root span yields a turn_ended event; a child span yields None."""
    root_row = AgentSpanCHInsertable(
        project_id="p",
        trace_id="tr",
        span_id="root",
        parent_span_id="",
        span_name="root",
        status_code="OK",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
        conversation_id="c",
        operation_name="invoke_agent",
    )
    event = ScoreAgentSpansEvent.from_row(root_row)
    assert event == ScoreAgentSpansEvent(
        event_type="weave.genai.turn_ended",
        status_code="OK",
        project_id="p",
        trace_id="tr",
        span_id="root",
        parent_span_id=None,
        conversation_id="c",
        operation_name="invoke_agent",
    )
    assert EmbedAgentSpansEvent.from_row(root_row) == EmbedAgentSpansEvent(
        event_type="weave.genai.turn_ended",
        status_code="OK",
        project_id="p",
        trace_id="tr",
        span_id="root",
        parent_span_id=None,
        conversation_id="c",
        operation_name="invoke_agent",
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
    assert EmbedAgentSpansEvent.from_row(child_row) is None
