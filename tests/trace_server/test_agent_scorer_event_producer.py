"""Producer-level tests for the ScoreAgentSpansEvent Kafka event."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from weave.trace_server.agents.kafka_events import (
    SCORE_AGENT_SPANS_TOPIC,
    ScoreAgentSpansEvent,
)

_ENDED_AT = datetime.datetime(2024, 1, 1, 12, 0, 0)


def test_topic_constant_value() -> None:
    assert SCORE_AGENT_SPANS_TOPIC == "weave.score_agent_spans"


def test_event_round_trip() -> None:
    event = ScoreAgentSpansEvent(
        event_type="turn_ended",
        project_id="proj-1",
        trace_id="trace-1",
        root_span_id="span-root",
        conversation_id="conv-1",
        agent_name="research_agent",
        operation_name="invoke_agent",
        request_model="gpt-5",
        ended_at=_ENDED_AT,
    )
    payload = event.model_dump_json()
    parsed = ScoreAgentSpansEvent.model_validate_json(payload)
    assert parsed == event


def test_event_defaults() -> None:
    event = ScoreAgentSpansEvent(
        event_type="turn_ended",
        project_id="p",
        trace_id="t",
        root_span_id="r",
        ended_at=_ENDED_AT,
    )
    assert event.conversation_id is None
    assert event.agent_name is None
    assert event.operation_name is None
    assert event.request_model is None


@pytest.mark.disable_logging_error_check
def test_producer_drops_when_buffer_full() -> None:
    from weave.trace_server.kafka import KafkaProducer

    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 2
    producer.__len__ = MagicMock(return_value=5)  # buffer full
    producer.produce_score_agent_spans = (
        KafkaProducer.produce_score_agent_spans.__get__(producer)
    )

    event = ScoreAgentSpansEvent(
        event_type="turn_ended",
        project_id="p",
        trace_id="t",
        root_span_id="r",
        ended_at=_ENDED_AT,
    )
    producer.produce_score_agent_spans(event)

    producer.produce.assert_not_called()


def test_producer_publishes_under_buffer_limit() -> None:
    from weave.trace_server.kafka import KafkaProducer

    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 100
    producer.__len__ = MagicMock(return_value=0)
    producer.produce_score_agent_spans = (
        KafkaProducer.produce_score_agent_spans.__get__(producer)
    )

    event = ScoreAgentSpansEvent(
        event_type="turn_ended",
        project_id="p",
        trace_id="t",
        root_span_id="r",
        ended_at=_ENDED_AT,
    )
    producer.produce_score_agent_spans(event)

    producer.produce.assert_called_once()
    call_kwargs = producer.produce.call_args.kwargs
    assert call_kwargs["topic"] == "weave.score_agent_spans"
