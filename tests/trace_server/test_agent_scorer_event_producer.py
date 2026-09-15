"""Producer-level tests for the ScoreAgentSpansEvent Kafka event."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from weave.trace_server import kafka
from weave.trace_server.agents.kafka_events import (
    EMBED_AGENT_SPANS_TOPIC,
    SCORE_AGENT_SPANS_TOPIC,
    EmbedAgentSpansEvent,
    ScoreAgentSpansEvent,
)
from weave.trace_server.kafka import (
    DELIVERY_ERROR_LOG_EVERY,
    DELIVERY_FAILED_METRIC,
    KafkaProducer,
    _bucketed_project_key,
)


def _make_event(
    event_class: type[ScoreAgentSpansEvent | EmbedAgentSpansEvent],
    **overrides,
) -> ScoreAgentSpansEvent | EmbedAgentSpansEvent:
    """Build a minimal valid agent spans event; override any field."""
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
    return event_class(**base)


def test_topic_constant_values() -> None:
    assert SCORE_AGENT_SPANS_TOPIC == "weave.score_agent_spans"
    assert EMBED_AGENT_SPANS_TOPIC == "weave.embed_agent_spans"


def test_event_round_trip() -> None:
    event = _make_event(
        ScoreAgentSpansEvent,
        project_id="proj-1",
        trace_id="trace-1",
        span_id="span-root",
        conversation_id="conv-1",
        operation_name="invoke_agent",
    )
    payload = event.model_dump_json()
    parsed = ScoreAgentSpansEvent.model_validate_json(payload)
    assert parsed == event

    embed_event = EmbedAgentSpansEvent.model_validate_json(payload)
    assert embed_event == EmbedAgentSpansEvent(**event.model_dump())


def _bind_real_methods(producer: MagicMock, *names: str) -> None:
    """Replace MagicMock auto-stubs with real `KafkaProducer` methods bound to the mock."""
    for name in names:
        setattr(producer, name, getattr(KafkaProducer, name).__get__(producer))


@pytest.mark.parametrize(
    ("method_name", "event_class"),
    [
        ("produce_score_agent_spans", ScoreAgentSpansEvent),
        ("produce_embed_agent_spans", EmbedAgentSpansEvent),
    ],
)
@pytest.mark.disable_logging_error_check
def test_producer_drops_when_buffer_full(
    method_name: str,
    event_class: type[ScoreAgentSpansEvent | EmbedAgentSpansEvent],
) -> None:
    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 2
    producer.__len__ = MagicMock(return_value=5)  # buffer full
    _bind_real_methods(
        producer, method_name, "_produce_agent_spans", "_check_buffer_pressure"
    )

    getattr(producer, method_name)(_make_event(event_class))

    producer.produce.assert_not_called()


@pytest.mark.parametrize(
    ("method_name", "event_class", "topic"),
    [
        (
            "produce_score_agent_spans",
            ScoreAgentSpansEvent,
            "weave.score_agent_spans",
        ),
        (
            "produce_embed_agent_spans",
            EmbedAgentSpansEvent,
            "weave.embed_agent_spans",
        ),
    ],
)
def test_producer_publishes_under_buffer_limit(
    method_name: str,
    event_class: type[ScoreAgentSpansEvent | EmbedAgentSpansEvent],
    topic: str,
) -> None:
    producer = MagicMock(spec=KafkaProducer)
    producer.max_buffer_size = 100
    producer.__len__ = MagicMock(return_value=0)
    _bind_real_methods(
        producer,
        method_name,
        "_produce_agent_spans",
        "_check_buffer_pressure",
    )

    getattr(producer, method_name)(_make_event(event_class))

    producer.produce.assert_called_once()
    call_kwargs = producer.produce.call_args.kwargs
    assert call_kwargs["topic"] == topic
    assert "on_delivery" not in call_kwargs


@pytest.mark.disable_logging_error_check
def test_delivery_failure_is_counted_per_topic_and_error(monkeypatch) -> None:
    """Failed deliveries always increment the counter; logger.error is sampled."""
    producer = MagicMock(spec=KafkaProducer)
    producer._delivery_error_counts = {}
    _bind_real_methods(producer, "_on_delivery", "_record_delivery_error")
    emitted = MagicMock()
    logged = MagicMock()
    monkeypatch.setattr(kafka, "emit_counter", emitted)
    monkeypatch.setattr(kafka.logger, "error", logged)
    message = MagicMock()
    message.topic.return_value = "weave.embed_agent_spans"
    message.key.return_value = b"conv-1"
    error = MagicMock()
    error.name.return_value = "_MSG_TIMED_OUT"
    error.str.return_value = "Local: Message timed out"

    producer._on_delivery(None, message)
    emitted.assert_not_called()
    logged.assert_not_called()

    producer._on_delivery(error, message)
    emitted.assert_called_once_with(
        DELIVERY_FAILED_METRIC,
        1,
        ["topic:weave.embed_agent_spans", "error:_MSG_TIMED_OUT"],
    )
    logged.assert_called_once_with(
        "Kafka delivery failed topic=%s error=%s count=%s",
        "weave.embed_agent_spans",
        "Local: Message timed out",
        1,
        extra={"key": b"conv-1", "error_code": "_MSG_TIMED_OUT"},
    )

    producer._on_delivery(error, message)
    assert emitted.call_count == 2
    logged.assert_called_once()

    for _ in range(DELIVERY_ERROR_LOG_EVERY - 2):
        producer._on_delivery(error, message)

    assert emitted.call_count == DELIVERY_ERROR_LOG_EVERY
    assert logged.call_count == 2
    assert logged.call_args.args[3] == DELIVERY_ERROR_LOG_EVERY

    other = MagicMock()
    other.topic.return_value = "weave.call_ended"
    other.key.return_value = b"call-1"
    producer._on_delivery(error, other)
    assert emitted.call_count == DELIVERY_ERROR_LOG_EVERY + 1
    assert logged.call_count == 3


def test_produce_defaults_on_delivery() -> None:
    """produce() setdefaults _on_delivery; an explicit callback wins."""
    producer = MagicMock(spec=KafkaProducer)
    _bind_real_methods(producer, "_attach_delivery_callback")
    attached = producer._attach_delivery_callback({"topic": "weave.call_ended"})
    assert attached["on_delivery"] == producer._on_delivery

    other = object()
    attached = producer._attach_delivery_callback(
        {"topic": "weave.call_ended", "on_delivery": other}
    )
    assert attached["on_delivery"] is other


@pytest.mark.disable_logging_error_check
def test_bucketed_project_key(monkeypatch):
    """Bucket suffix is deterministic per salt, scoped to N, off by default."""
    key = "WF_KAFKA_PROJECT_ID_BUCKET_COUNT"

    monkeypatch.delenv(key, raising=False)
    assert _bucketed_project_key("proj-a", "call-1") == "proj-a"

    monkeypatch.setenv(key, "4")
    first = _bucketed_project_key("proj-a", "call-1")
    assert first == _bucketed_project_key("proj-a", "call-1")
    prefix, _, bucket = first.partition(":")
    assert prefix == "proj-a"
    assert 0 <= int(bucket) < 4

    seen = {
        _bucketed_project_key("proj-a", f"call-{i}").split(":")[1] for i in range(100)
    }
    assert len(seen) > 1
    assert _bucketed_project_key("proj-b", "call-1").startswith("proj-b:")
