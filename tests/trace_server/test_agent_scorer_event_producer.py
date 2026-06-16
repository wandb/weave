"""Producer-level tests for the ScoreAgentSpansEvent Kafka event."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from weave.trace_server.agents.kafka_events import (
    SCORE_AGENT_SPANS_TOPIC,
    ScoreAgentSpansEvent,
)
from weave.trace_server.kafka import KafkaProducer


def test_event_topic_and_round_trip() -> None:
    """Topic constant is stable and a fully-populated event round-trips through JSON."""
    assert SCORE_AGENT_SPANS_TOPIC == "weave.score_agent_spans"

    event = _make_event(
        project_id="proj-1",
        trace_id="trace-1",
        span_id="span-root",
        conversation_id="conv-1",
        operation_name="invoke_agent",
    )
    parsed = ScoreAgentSpansEvent.model_validate_json(event.model_dump_json())
    assert parsed == event


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    ("max_buffer_size", "buffer_len", "expect_publish"),
    [
        (2, 5, False),  # buffer full -> drop
        (100, 0, True),  # under limit -> publish
    ],
    ids=["buffer_full_drops", "under_limit_publishes"],
)
def test_producer_buffer_pressure(
    max_buffer_size: int, buffer_len: int, expect_publish: bool
) -> None:
    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = max_buffer_size
    producer.__len__ = MagicMock(return_value=buffer_len)
    _bind_real_methods(producer, "produce_score_agent_spans", "_check_buffer_pressure")

    producer.produce_score_agent_spans(_make_event())

    if expect_publish:
        producer.produce.assert_called_once()
        assert producer.produce.call_args.kwargs["topic"] == "weave.score_agent_spans"
    else:
        producer.produce.assert_not_called()


def _make_event(**overrides) -> ScoreAgentSpansEvent:
    """Minimal valid ScoreAgentSpansEvent for tests; override any field."""
    base = {
        "event_type": "weave.genai.turn_ended",
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


def _bind_real_methods(producer: MagicMock, *names: str) -> None:
    """Replace MagicMock auto-stubs with real `KafkaProducer` methods bound to the mock."""
    for name in names:
        setattr(producer, name, getattr(KafkaProducer, name).__get__(producer))
