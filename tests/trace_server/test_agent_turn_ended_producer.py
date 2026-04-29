"""Producer-level tests for the agent_turn_ended Kafka event."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from weave.trace_server.agents.events import (
    AGENT_TURN_ENDED_TOPIC,
    AgentTurnEndedEvent,
)


def test_topic_constant_value() -> None:
    assert AGENT_TURN_ENDED_TOPIC == "weave.agent_turn_ended"


def test_event_round_trip() -> None:
    event = AgentTurnEndedEvent(
        project_id="proj-1",
        trace_id="trace-1",
        root_span_id="span-root",
        conversation_id="conv-1",
        agent_name="research_agent",
        operation_name="invoke_agent",
        request_model="gpt-5",
        ended_at_ns=1_700_000_000_000_000_000,
    )
    payload = event.model_dump_json()
    parsed = AgentTurnEndedEvent.model_validate_json(payload)
    assert parsed == event


def test_event_defaults() -> None:
    event = AgentTurnEndedEvent(
        project_id="p",
        trace_id="t",
        root_span_id="r",
    )
    assert event.conversation_id == ""
    assert event.agent_name == ""
    assert event.operation_name == ""
    assert event.request_model == ""
    assert event.ended_at_ns == 0


@pytest.mark.disable_logging_error_check
def test_producer_drops_when_buffer_full() -> None:
    from weave.trace_server.kafka import KafkaProducer

    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 2
    producer.__len__ = MagicMock(return_value=5)  # buffer full
    producer.produce_agent_turn_ended = (
        KafkaProducer.produce_agent_turn_ended.__get__(producer)
    )

    event = AgentTurnEndedEvent(project_id="p", trace_id="t", root_span_id="r")
    producer.produce_agent_turn_ended(event)

    producer.produce.assert_not_called()


def test_producer_flushes_when_requested() -> None:
    from weave.trace_server.kafka import KafkaProducer

    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 100
    producer.__len__ = MagicMock(return_value=0)
    producer.produce_agent_turn_ended = (
        KafkaProducer.produce_agent_turn_ended.__get__(producer)
    )

    event = AgentTurnEndedEvent(project_id="p", trace_id="t", root_span_id="r")
    producer.produce_agent_turn_ended(event, flush_immediately=True)

    producer.produce.assert_called_once()
    call_kwargs = producer.produce.call_args.kwargs
    assert call_kwargs["topic"] == "weave.agent_turn_ended"
    producer.flush.assert_called_once_with(0)
