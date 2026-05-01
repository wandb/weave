"""Producer-level tests for the ScoreAgentSpansEvent Kafka event."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from weave.trace_server.agents.kafka_events import (
    SCORE_AGENT_SPANS_TOPIC,
    ScoreAgentSpansEvent,
)
from weave.trace_server.kafka import KafkaProducer


def _make_event(**overrides) -> ScoreAgentSpansEvent:
    """Minimal valid ScoreAgentSpansEvent for tests; override any field."""
    base = {
        "event_type": "turn_ended",
        "status_code": "OK",
        "project_id": "p",
        "trace_id": "t",
        "span_id": "r",
        "parent_span_id": None,
        "conversation_id": None,
        "operation_name": None,
    }
    base.update(overrides)
    return ScoreAgentSpansEvent(**base)


def test_topic_constant_value() -> None:
    assert SCORE_AGENT_SPANS_TOPIC == "weave.score_agent_spans"


def test_event_round_trip() -> None:
    event = _make_event(
        project_id="proj-1",
        trace_id="trace-1",
        span_id="span-root",
        conversation_id="conv-1",
        operation_name="invoke_agent",
    )
    payload = event.model_dump_json()
    parsed = ScoreAgentSpansEvent.model_validate_json(payload)
    assert parsed == event


@pytest.mark.disable_logging_error_check
def test_producer_drops_when_buffer_full() -> None:
    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 2
    producer.__len__ = MagicMock(return_value=5)  # buffer full
    producer.produce_score_agent_spans = (
        KafkaProducer.produce_score_agent_spans.__get__(producer)
    )

    producer.produce_score_agent_spans(_make_event())

    producer.produce.assert_not_called()


def test_producer_publishes_under_buffer_limit() -> None:
    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 100
    producer.__len__ = MagicMock(return_value=0)
    producer.produce_score_agent_spans = (
        KafkaProducer.produce_score_agent_spans.__get__(producer)
    )

    producer.produce_score_agent_spans(_make_event())

    producer.produce.assert_called_once()
    call_kwargs = producer.produce.call_args.kwargs
    assert call_kwargs["topic"] == "weave.score_agent_spans"
