"""Unit tests for ScoreAgentSpansEvent."""

from __future__ import annotations

import datetime

import pytest

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
    event = ScoreAgentSpansEvent.from_row(root_row, "acme")
    assert event == ScoreAgentSpansEvent(
        event_type="weave.genai.turn_ended",
        status_code="OK",
        project_id="p",
        entity_name="acme",
        trace_id="tr",
        span_id="root",
        parent_span_id=None,
        conversation_id="c",
        operation_name="invoke_agent",
    )
    assert EmbedAgentSpansEvent.from_row(root_row, "acme") == EmbedAgentSpansEvent(
        event_type="weave.genai.turn_ended",
        status_code="OK",
        project_id="p",
        entity_name="acme",
        trace_id="tr",
        span_id="root",
        parent_span_id=None,
        conversation_id="c",
        operation_name="invoke_agent",
    )
    # The row itself carries no entity, so an unstamped event has none: consumers
    # that route by entity have to treat that as unroutable, not as allowed.
    assert EmbedAgentSpansEvent.from_row(root_row).entity_name is None

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


def test_embed_requires_conversation_but_score_does_not() -> None:
    """A root span with no `conversation_id` still scores, but never feeds insights embedding."""
    no_convo_row = AgentSpanCHInsertable(
        project_id="p",
        trace_id="tr",
        span_id="root",
        parent_span_id="",
        span_name="root",
        status_code="OK",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
        conversation_id="",
        operation_name="invoke_agent",
    )
    assert EmbedAgentSpansEvent.from_row(no_convo_row, "acme") is None
    score_event = ScoreAgentSpansEvent.from_row(no_convo_row, "acme")
    assert score_event is not None
    assert score_event.conversation_id is None


@pytest.mark.parametrize(
    "eval_fields",
    [
        {"eval_run_id": "eval-run"},
        {"eval_predict_and_score_call_id": "predict-and-score"},
        {"eval_kind": "agent"},
    ],
)
def test_embed_excludes_evaluation_spans(eval_fields: dict[str, str]) -> None:
    """Evaluation roots still score but never feed Insights embedding."""
    eval_row = AgentSpanCHInsertable(
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
        **eval_fields,
    )

    assert ScoreAgentSpansEvent.from_row(eval_row, "acme") is not None
    assert EmbedAgentSpansEvent.from_row(eval_row, "acme") is None
