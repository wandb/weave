"""Tests for ``set_attributes`` and ``add_event``.

Both live on ``_SpanBase`` so every span class (Tool, LLM, SubAgent, Turn)
gets identical behavior. Tests are parametrized across the four span
classes; the two methods get one test each so each test reads
top-to-bottom without indirection.
"""

from __future__ import annotations

import logging

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.conversation.conversation import (
    LLM,
    Conversation,
    SubAgent,
    Tool,
    Turn,
    log_conversation,
    log_turn,
)

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


# ---------------------------------------------------------------------------
# set_attributes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_set_attributes_lands_on_span(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    with Conversation(conversation_id="test-conversation"), factory() as span_obj:
        span_obj.set_attributes({"weave.first": "one", "weave.second": "two"})
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert finished_span.attributes["weave.first"] == "one"
    assert finished_span.attributes["weave.second"] == "two"


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_set_attributes_no_op_after_end(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    with Conversation(conversation_id="test-conversation"):
        span_obj = factory()
        with span_obj:
            pass
        span_obj.set_attributes({"weave.late_a": "a", "weave.late_b": "b"})
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert "weave.late_a" not in (finished_span.attributes or {})
    assert "weave.late_b" not in (finished_span.attributes or {})


def test_set_attributes_accepts_sequence_value(
    otel_spans: InMemorySpanExporter,
) -> None:
    """OTel accepts ``Sequence[str]`` — used for e.g. ``gen_ai.response.finish_reasons``."""
    with Conversation(conversation_id="test-conversation"), LLM(model="gpt-4o") as llm:
        llm.set_attributes({"gen_ai.response.finish_reasons": ["stop"]})
    chat_span = _only_span(otel_spans.get_finished_spans(), "chat gpt-4o")
    assert tuple(chat_span.attributes["gen_ai.response.finish_reasons"]) == ("stop",)


# ---------------------------------------------------------------------------
# add_event
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_add_event_records_on_span(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    with Conversation(conversation_id="test-conversation"), factory() as span_obj:
        span_obj.add_event("weave.evt", {"event_key": "event_value"})
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert len(finished_span.events) == 1
    assert finished_span.events[0].name == "weave.evt"
    assert finished_span.events[0].attributes["event_key"] == "event_value"


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_add_event_no_op_after_end(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    with Conversation(conversation_id="test-conversation"):
        span_obj = factory()
        with span_obj:
            pass
        span_obj.add_event("weave.late")
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert len(finished_span.events) == 0


# ---------------------------------------------------------------------------
# Cross-method: chaining + warning behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("_class_label", "factory", "_span_name"), CASES, ids=CLASS_LABELS
)
def test_returns_self_for_chaining(
    otel_spans: InMemorySpanExporter, _class_label, factory, _span_name
) -> None:
    """Both mutators return ``self`` for fluent chaining on a live span."""
    with Conversation(conversation_id="test-conversation"), factory() as span_obj:
        assert span_obj.set_attributes({"key": "value"}) is span_obj
        assert span_obj.add_event("event-name") is span_obj


def test_warns_when_span_not_started(
    caplog: pytest.LogCaptureFixture, otel_spans: InMemorySpanExporter
) -> None:
    """Both mutators warn and emit no span when called before ``with``."""
    caplog.set_level(logging.WARNING, logger="weave.conversation.conversation")
    tool = Tool(name="test-tool")
    tool.set_attributes({"weave.first": "one"})
    tool.add_event("weave.evt")
    messages = [record.message for record in caplog.records]
    assert any("set_attributes" in m and "span not started" in m for m in messages)
    assert any("add_event" in m and "span not started" in m for m in messages)
    assert len(otel_spans.get_finished_spans()) == 0


def test_warns_when_span_already_ended(caplog: pytest.LogCaptureFixture) -> None:
    """Both mutators warn when called after ``end()``."""
    caplog.set_level(logging.WARNING, logger="weave.conversation.conversation")
    with Conversation(conversation_id="test-conversation"):
        tool = Tool(name="test-tool")
        with tool:
            pass
        tool.set_attributes({"weave.first": "one"})
        tool.add_event("weave.evt")
    messages = [record.message for record in caplog.records]
    assert any("set_attributes" in m and "span already ended" in m for m in messages)
    assert any("add_event" in m and "span already ended" in m for m in messages)


# ---------------------------------------------------------------------------
# Conversation attributes (stamped on every span)
# ---------------------------------------------------------------------------


def test_conversation_attributes_on_every_streaming_span(
    otel_spans: InMemorySpanExporter,
) -> None:
    """A conversation's attributes land on the turn root and every child span."""
    attrs = {"weave.integration.name": "wb-agent", "custom.tier": "gold"}
    with Conversation(
        conversation_id="convo-attrs-streaming", attributes=attrs
    ) as conversation:
        turn = conversation.start_turn(agent_name="bot")
        with turn:
            with turn.llm(model="gpt-4o"):
                pass
            with turn.tool(name="Edit"):
                pass
            with turn.subagent(name="researcher"):
                pass
    spans = otel_spans.get_finished_spans()
    names = {span.name for span in spans}
    assert {
        "invoke_agent bot",
        "chat gpt-4o",
        "execute_tool Edit",
        "invoke_agent researcher",
    } <= names
    for span in spans:
        assert span.attributes["weave.integration.name"] == "wb-agent"
        assert span.attributes["custom.tier"] == "gold"


def test_conversation_attributes_on_every_batch_span(
    otel_spans: InMemorySpanExporter,
) -> None:
    """log_turn applies attributes to the turn and its child spans."""
    log_turn(
        conversation_id="convo-attrs-batch",
        agent_name="bot",
        spans=[LLM(model="gpt-4o"), Tool(name="Edit")],
        attributes={"weave.integration.name": "wb-agent"},
    )
    spans = otel_spans.get_finished_spans()
    assert len(spans) == 3
    for span in spans:
        assert span.attributes["weave.integration.name"] == "wb-agent"


def test_conversation_attributes_on_every_log_conversation_span(
    otel_spans: InMemorySpanExporter,
) -> None:
    """log_conversation applies attributes to every turn root and child span."""
    log_conversation(
        turns=[
            Turn(agent_name="bot", spans=[LLM(model="gpt-4o")]),
            Turn(agent_name="bot", spans=[Tool(name="Edit")]),
        ],
        conversation_id="convo-attrs-log-conversation",
        attributes={"weave.integration.name": "wb-agent"},
    )
    spans = otel_spans.get_finished_spans()
    assert len(spans) == 4  # two turn roots + one child each
    for span in spans:
        assert span.attributes["weave.integration.name"] == "wb-agent"


def test_no_conversation_attributes_by_default(
    otel_spans: InMemorySpanExporter,
) -> None:
    with Conversation(conversation_id="convo-attrs-default") as conversation:
        with conversation.start_turn(agent_name="bot"):
            pass
    span = _only_span(otel_spans.get_finished_spans(), "invoke_agent bot")
    assert "weave.integration.name" not in (span.attributes or {})
