"""Tests for ``set_attribute``, ``set_attributes``, and ``add_event``.

All three live on ``_SpanBase`` so every span class (Tool, LLM, SubAgent,
Turn) gets identical behavior. Tests cross-parametrize over the (span
class x mutator method) cross product to lock in that uniformity.
"""

from __future__ import annotations

import logging

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


# (op_name, invoke_on_span, assert_landed_on_finished_span)
# The three mutators have different signatures; capture each call shape
# alongside the matching "did it land?" check so cross-parametrize stays clean.
MUTATORS = [
    (
        "set_attribute",
        lambda span: span.set_attribute("weave.tag", "value"),
        lambda finished: finished.attributes.get("weave.tag") == "value",
    ),
    (
        "set_attributes",
        lambda span: span.set_attributes({"weave.first": "one", "weave.second": "two"}),
        lambda finished: (
            finished.attributes.get("weave.first") == "one"
            and finished.attributes.get("weave.second") == "two"
        ),
    ),
    (
        "add_event",
        lambda span: span.add_event("weave.evt", {"event_key": "event_value"}),
        lambda finished: (
            len(finished.events) == 1
            and finished.events[0].name == "weave.evt"
            and finished.events[0].attributes["event_key"] == "event_value"
        ),
    ),
]
MUTATOR_LABELS = [mutator[0] for mutator in MUTATORS]


def _only_span(spans: list, span_name: str):
    matches = [span for span in spans if span.name == span_name]
    assert len(matches) == 1, [span.name for span in matches]
    return matches[0]


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
@pytest.mark.parametrize(
    ("_op", "invoke", "assert_landed"), MUTATORS, ids=MUTATOR_LABELS
)
def test_mutator_lands_on_live_span(
    otel_spans: InMemorySpanExporter,
    _class_label,
    factory,
    span_name,
    _op,
    invoke,
    assert_landed,
) -> None:
    """Each mutator writes through to the OTel span when called inside ``with``."""
    with Session(session_id="test-session"), factory() as span_obj:
        invoke(span_obj)
    assert assert_landed(_only_span(otel_spans.get_finished_spans(), span_name))


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
@pytest.mark.parametrize(
    ("_op", "invoke", "assert_landed"), MUTATORS, ids=MUTATOR_LABELS
)
def test_mutator_no_op_after_end(
    otel_spans: InMemorySpanExporter,
    _class_label,
    factory,
    span_name,
    _op,
    invoke,
    assert_landed,
) -> None:
    """Each mutator is a no-op when called after the span has ended."""
    with Session(session_id="test-session"):
        span_obj = factory()
        with span_obj:
            pass
        invoke(span_obj)
    assert not assert_landed(_only_span(otel_spans.get_finished_spans(), span_name))


@pytest.mark.parametrize(
    ("_class_label", "factory", "_span_name"), CASES, ids=CLASS_LABELS
)
def test_mutators_return_self_for_chaining(
    otel_spans: InMemorySpanExporter, _class_label, factory, _span_name
) -> None:
    """All mutators return ``self`` for fluent chaining."""
    with Session(session_id="test-session"), factory() as span_obj:
        for _op, invoke, _assert_landed in MUTATORS:
            assert invoke(span_obj) is span_obj


@pytest.mark.parametrize(
    ("op", "invoke", "_assert_landed"), MUTATORS, ids=MUTATOR_LABELS
)
def test_warns_when_span_not_started(
    caplog: pytest.LogCaptureFixture,
    otel_spans: InMemorySpanExporter,
    op,
    invoke,
    _assert_landed,
) -> None:
    """Each mutator warns and emits no span when called before ``with``."""
    caplog.set_level(logging.WARNING, logger="weave.session.session")
    invoke(Tool(name="test-tool"))
    assert any(
        op in record.message and "span not started" in record.message
        for record in caplog.records
    )
    assert len(otel_spans.get_finished_spans()) == 0


@pytest.mark.parametrize(
    ("op", "invoke", "_assert_landed"), MUTATORS, ids=MUTATOR_LABELS
)
def test_warns_when_span_already_ended(
    caplog: pytest.LogCaptureFixture, op, invoke, _assert_landed
) -> None:
    """Each mutator warns when called after ``end()``."""
    caplog.set_level(logging.WARNING, logger="weave.session.session")
    with Session(session_id="test-session"):
        tool = Tool(name="test-tool")
        with tool:
            pass
        invoke(tool)
    assert any(
        op in record.message and "span already ended" in record.message
        for record in caplog.records
    )


def test_set_attribute_accepts_sequence_value(
    otel_spans: InMemorySpanExporter,
) -> None:
    """OTel accepts ``Sequence[str]`` — used for e.g. ``gen_ai.response.finish_reasons``."""
    with Session(session_id="test-session"), LLM(model="gpt-4o") as llm:
        llm.set_attribute("gen_ai.response.finish_reasons", ["stop"])
    chat_span = _only_span(otel_spans.get_finished_spans(), "chat gpt-4o")
    assert tuple(chat_span.attributes["gen_ai.response.finish_reasons"]) == ("stop",)
