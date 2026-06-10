"""Tests for ``set_attribute`` and ``add_event`` on session span classes.

Both methods live on ``_SpanBase`` so all four span classes (Tool, LLM,
SubAgent, Turn) get identical behavior. Parametrized across the four
classes to lock in uniformity.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session.session import LLM, Session, SubAgent, Tool, Turn

# (label, factory, otel span name) — name is full not prefix so SubAgent and
# Turn (both "invoke_agent") don't collide.
CASES = [
    ("Tool", lambda: Tool(name="f"), "execute_tool f"),
    ("LLM", lambda: LLM(model="gpt-4o"), "chat gpt-4o"),
    ("SubAgent", lambda: SubAgent(name="sa"), "invoke_agent sa"),
    ("Turn", lambda: Turn(agent_name="t"), "invoke_agent t"),
]
IDS = [c[0] for c in CASES]


def _only(spans: list, name: str):
    matches = [sp for sp in spans if sp.name == name]
    assert len(matches) == 1, [s.name for s in matches]
    return matches[0]


@pytest.mark.parametrize(("_label", "factory", "span_name"), CASES, ids=IDS)
def test_set_attribute_lands_on_span(
    otel_spans: InMemorySpanExporter, _label, factory, span_name
) -> None:
    with Session(session_id="s"), factory() as x:
        x.set_attribute("weave.tag", "v")
    assert (
        _only(otel_spans.get_finished_spans(), span_name).attributes["weave.tag"] == "v"
    )


@pytest.mark.parametrize(("_label", "factory", "span_name"), CASES, ids=IDS)
def test_set_attribute_no_op_after_end(
    otel_spans: InMemorySpanExporter, _label, factory, span_name
) -> None:
    with Session(session_id="s"):
        x = factory()
        with x:
            pass
        x.set_attribute("weave.late", "x")
    assert "weave.late" not in (
        _only(otel_spans.get_finished_spans(), span_name).attributes or {}
    )


@pytest.mark.parametrize(("_label", "factory", "span_name"), CASES, ids=IDS)
def test_add_event_records_on_span(
    otel_spans: InMemorySpanExporter, _label, factory, span_name
) -> None:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with Session(session_id="s"), factory() as x:
        x.add_event("weave.evt", {"k": "v"}, timestamp=ts)
    span = _only(otel_spans.get_finished_spans(), span_name)
    assert len(span.events) == 1
    assert (span.events[0].name, span.events[0].attributes["k"]) == ("weave.evt", "v")
    assert span.events[0].timestamp == int(ts.timestamp() * 1_000_000_000)


@pytest.mark.parametrize(("_label", "factory", "span_name"), CASES, ids=IDS)
def test_add_event_no_op_after_end(
    otel_spans: InMemorySpanExporter, _label, factory, span_name
) -> None:
    with Session(session_id="s"):
        x = factory()
        with x:
            pass
        x.add_event("weave.late")
    assert len(_only(otel_spans.get_finished_spans(), span_name).events) == 0


def test_returns_self_for_chaining() -> None:
    """Both methods return ``self`` — checked on Tool (mixin, same on all)."""
    t = Tool(name="f")
    assert t.set_attribute("k", "v") is t
    assert t.add_event("e") is t


def test_set_attribute_accepts_sequence_value(otel_spans: InMemorySpanExporter) -> None:
    """OTel accepts ``Sequence[str]`` — used for e.g. ``gen_ai.response.finish_reasons``."""
    with Session(session_id="s"), LLM(model="gpt-4o") as c:
        c.set_attribute("gen_ai.response.finish_reasons", ["stop"])
    span = _only(otel_spans.get_finished_spans(), "chat gpt-4o")
    assert tuple(span.attributes["gen_ai.response.finish_reasons"]) == ("stop",)


def test_no_op_on_unentered_span() -> None:
    """No OTel span ever created (caller never entered the context manager)."""
    t = Tool(name="f")
    assert t.set_attribute("k", "v") is t
    assert t.add_event("e") is t
