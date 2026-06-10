"""Tests for ``set_attribute`` and ``add_event`` on session span classes.

Both methods live on ``_SpanBase`` so all four span classes (Tool, LLM,
SubAgent, Turn) get identical behavior. Parametrized across the four
classes to lock in uniformity.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session.session import LLM, Session, SubAgent, Tool, Turn

# (class_label, factory, otel_span_name) — span_name is the full emitted name
# (not a prefix) so SubAgent and Turn (both "invoke_agent") don't collide.
CASES = [
    ("Tool", lambda: Tool(name="test-tool"), "execute_tool test-tool"),
    ("LLM", lambda: LLM(model="gpt-4o"), "chat gpt-4o"),
    ("SubAgent", lambda: SubAgent(name="researcher"), "invoke_agent researcher"),
    ("Turn", lambda: Turn(agent_name="weather-bot"), "invoke_agent weather-bot"),
]
CLASS_LABELS = [case[0] for case in CASES]


def _only_span(spans: list, span_name: str):
    matches = [span for span in spans if span.name == span_name]
    assert len(matches) == 1, [span.name for span in matches]
    return matches[0]


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_set_attribute_lands_on_span(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    with Session(session_id="test-session"), factory() as span_obj:
        span_obj.set_attribute("weave.tag", "value")
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert finished_span.attributes["weave.tag"] == "value"


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_set_attribute_no_op_after_end(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    with Session(session_id="test-session"):
        span_obj = factory()
        with span_obj:
            pass
        span_obj.set_attribute("weave.late", "value")
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert "weave.late" not in (finished_span.attributes or {})


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_add_event_records_on_span(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with Session(session_id="test-session"), factory() as span_obj:
        span_obj.add_event(
            "weave.evt", {"event_key": "event_value"}, timestamp=timestamp
        )
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert len(finished_span.events) == 1
    event = finished_span.events[0]
    assert event.name == "weave.evt"
    assert event.attributes["event_key"] == "event_value"
    assert event.timestamp == int(timestamp.timestamp() * 1_000_000_000)


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_add_event_no_op_after_end(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    with Session(session_id="test-session"):
        span_obj = factory()
        with span_obj:
            pass
        span_obj.add_event("weave.late")
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert len(finished_span.events) == 0


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_set_attributes_lands_on_span(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    """Bulk ``set_attributes`` lands every key on the OTel span."""
    with Session(session_id="test-session"), factory() as span_obj:
        span_obj.set_attributes({"weave.first": "one", "weave.second": "two"})
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert finished_span.attributes["weave.first"] == "one"
    assert finished_span.attributes["weave.second"] == "two"


@pytest.mark.parametrize(
    ("_class_label", "factory", "_span_name"), CASES, ids=CLASS_LABELS
)
def test_returns_self_for_chaining(
    otel_spans: InMemorySpanExporter, _class_label, factory, _span_name
) -> None:
    """All three mutators return ``self`` for fluent chaining on a live span."""
    with Session(session_id="test-session"), factory() as span_obj:
        assert span_obj.set_attribute("key", "value") is span_obj
        assert span_obj.set_attributes({"key": "value"}) is span_obj
        assert span_obj.add_event("event-name") is span_obj


def test_set_attribute_accepts_sequence_value(
    otel_spans: InMemorySpanExporter,
) -> None:
    """OTel accepts ``Sequence[str]`` — used for e.g. ``gen_ai.response.finish_reasons``."""
    with Session(session_id="test-session"), LLM(model="gpt-4o") as llm:
        llm.set_attribute("gen_ai.response.finish_reasons", ["stop"])
    chat_span = _only_span(otel_spans.get_finished_spans(), "chat gpt-4o")
    assert tuple(chat_span.attributes["gen_ai.response.finish_reasons"]) == ("stop",)


def test_no_op_on_unentered_span(otel_spans: InMemorySpanExporter) -> None:
    """Unentered span doesn't crash and emits no OTel output."""
    tool = Tool(name="test-tool")
    tool.set_attribute("key", "value")
    tool.add_event("event-name")
    assert len(otel_spans.get_finished_spans()) == 0


def test_warns_when_span_not_started(caplog: pytest.LogCaptureFixture) -> None:
    """Calling set_attribute / add_event on an unentered span warns the user."""
    caplog.set_level(logging.WARNING, logger="weave.session.session")
    tool = Tool(name="test-tool")
    tool.set_attribute("weave.tag", "value")
    tool.add_event("weave.evt")
    messages = [record.message for record in caplog.records]
    assert any(
        "set_attribute" in message and "span not started" in message
        for message in messages
    )
    assert any(
        "add_event" in message and "span not started" in message for message in messages
    )


def test_warns_when_span_already_ended(caplog: pytest.LogCaptureFixture) -> None:
    """Calling set_attribute / add_event after end() warns the user."""
    caplog.set_level(logging.WARNING, logger="weave.session.session")
    with Session(session_id="test-session"):
        tool = Tool(name="test-tool")
        with tool:
            pass
        tool.set_attribute("weave.tag", "value")
        tool.add_event("weave.evt")
    messages = [record.message for record in caplog.records]
    assert any(
        "set_attribute" in message and "span already ended" in message
        for message in messages
    )
    assert any(
        "add_event" in message and "span already ended" in message
        for message in messages
    )
