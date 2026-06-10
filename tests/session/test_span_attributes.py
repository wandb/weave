"""Tests for ``set_attribute`` and ``add_event`` on session span classes.

These two methods are escape hatches that delegate to the underlying OTel
span: ``set_attribute`` lands arbitrary keys not covered by the declared
GenAI semconv fields, and ``add_event`` records OTel span events.

Both live on ``_SpanBase`` so all four span classes (Tool, LLM, SubAgent,
Turn) get the same behavior. This file exercises each class independently
to lock in that uniformity.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session.session import (
    LLM,
    Session,
    SubAgent,
    Tool,
    Turn,
)


def _find(spans: list, name_prefix: str):
    """Return the single finished span whose name starts with ``name_prefix``."""
    matches = [sp for sp in spans if sp.name.startswith(name_prefix)]
    assert len(matches) == 1, (
        f"expected 1 span with prefix {name_prefix!r}, got {[s.name for s in matches]}"
    )
    return matches[0]


# ---------------------------------------------------------------------------
# set_attribute
# ---------------------------------------------------------------------------


class TestSetAttributeTool:
    def test_lands_on_finished_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"), Tool(name="f") as t:
            t.set_attribute("weave.display_name", "f: Tokyo")
        span = _find(otel_spans.get_finished_spans(), "execute_tool")
        assert span.attributes["weave.display_name"] == "f: Tokyo"

    def test_returns_self_for_chaining(self) -> None:
        t = Tool(name="f")
        assert t.set_attribute("k", "v") is t

    def test_no_op_after_end(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"):
            t = Tool(name="f")
            with t:
                pass
            t.set_attribute("weave.too_late", "x")
        span = _find(otel_spans.get_finished_spans(), "execute_tool")
        assert "weave.too_late" not in (span.attributes or {})


class TestSetAttributeLLM:
    def test_lands_on_finished_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"), LLM(model="gpt-4o") as c:
            c.set_attribute("gen_ai.response.id", "resp-abc")
        span = _find(otel_spans.get_finished_spans(), "chat")
        assert span.attributes["gen_ai.response.id"] == "resp-abc"

    def test_accepts_sequence_values(self, otel_spans: InMemorySpanExporter) -> None:
        """OTel accepts ``Sequence[str]`` / numeric sequences as attribute values."""
        with Session(session_id="s"), Turn(agent_name="bot"), LLM(model="gpt-4o") as c:
            c.set_attribute("gen_ai.response.finish_reasons", ["stop"])
        span = _find(otel_spans.get_finished_spans(), "chat")
        assert tuple(span.attributes["gen_ai.response.finish_reasons"]) == ("stop",)

    def test_no_op_after_end(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"):
            c = LLM(model="gpt-4o")
            with c:
                pass
            c.set_attribute("weave.too_late", "x")
        span = _find(otel_spans.get_finished_spans(), "chat")
        assert "weave.too_late" not in (span.attributes or {})


class TestSetAttributeSubAgent:
    def test_lands_on_finished_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with turn.subagent(name="researcher") as sa:
                sa.set_attribute("weave.display_name", "Agent: research-bot")
        # Two invoke_agent spans (Turn + SubAgent); pick the SubAgent by name.
        spans = otel_spans.get_finished_spans()
        sa_spans = [
            sp
            for sp in spans
            if sp.name.startswith("invoke_agent")
            and sp.attributes.get("gen_ai.agent.name") == "researcher"
        ]
        assert len(sa_spans) == 1
        assert sa_spans[0].attributes["weave.display_name"] == "Agent: research-bot"


class TestSetAttributeTurn:
    def test_lands_on_finished_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as t:
            t.set_attribute("weave.custom_tag", "v1")
        span = _find(otel_spans.get_finished_spans(), "invoke_agent")
        assert span.attributes["weave.custom_tag"] == "v1"


# ---------------------------------------------------------------------------
# add_event
# ---------------------------------------------------------------------------


class TestAddEventTool:
    def test_records_event_with_attributes(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with Session(session_id="s"), Turn(agent_name="bot"), Tool(name="f") as t:
            t.add_event(
                "weave.permission_request",
                {"weave.permission.suggestions": "[]"},
                timestamp=ts,
            )
        span = _find(otel_spans.get_finished_spans(), "execute_tool")
        assert len(span.events) == 1
        event = span.events[0]
        assert event.name == "weave.permission_request"
        assert event.attributes["weave.permission.suggestions"] == "[]"
        expected_ns = int(ts.timestamp() * 1_000_000_000)
        assert event.timestamp == expected_ns

    def test_default_timestamp_is_now(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"), Tool(name="f") as t:
            t.add_event("weave.marker")
        span = _find(otel_spans.get_finished_spans(), "execute_tool")
        assert len(span.events) == 1
        assert span.events[0].name == "weave.marker"

    def test_returns_self_for_chaining(self) -> None:
        t = Tool(name="f")
        assert t.add_event("e") is t

    def test_no_op_after_end(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"):
            t = Tool(name="f")
            with t:
                pass
            t.add_event("weave.too_late")
        span = _find(otel_spans.get_finished_spans(), "execute_tool")
        assert len(span.events) == 0


class TestAddEventLLM:
    def test_records_event(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"), LLM(model="gpt-4o") as c:
            c.add_event("weave.lifecycle", {"state": "streaming"})
        span = _find(otel_spans.get_finished_spans(), "chat")
        assert len(span.events) == 1
        assert span.events[0].name == "weave.lifecycle"
        assert span.events[0].attributes["state"] == "streaming"


class TestAddEventSubAgent:
    def test_records_event(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with turn.subagent(name="researcher") as sa:
                sa.add_event("weave.lifecycle", {"state": "spawned"})
        spans = otel_spans.get_finished_spans()
        sa_span = next(
            sp
            for sp in spans
            if sp.name.startswith("invoke_agent")
            and sp.attributes.get("gen_ai.agent.name") == "researcher"
        )
        assert len(sa_span.events) == 1
        assert sa_span.events[0].name == "weave.lifecycle"


class TestAddEventTurn:
    def test_records_event(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as t:
            t.add_event("weave.lifecycle", {"state": "received"})
        span = _find(otel_spans.get_finished_spans(), "invoke_agent")
        assert len(span.events) == 1
        assert span.events[0].name == "weave.lifecycle"


# ---------------------------------------------------------------------------
# No-OTel safety
# ---------------------------------------------------------------------------


class TestNoOtelInstalled:
    """When the span never got an OTel span (e.g. constructed without entering
    a context manager, or OTel disabled), both methods quietly no-op.
    """

    def test_set_attribute_on_unentered_tool(self) -> None:
        t = Tool(name="f")
        # No otel_spans fixture — _otel_span stays None. Must not raise.
        assert t.set_attribute("k", "v") is t

    def test_add_event_on_unentered_tool(self) -> None:
        t = Tool(name="f")
        assert t.add_event("e", {"k": "v"}) is t


# ---------------------------------------------------------------------------
# Sanity: methods exist on all four classes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", [Tool, LLM, SubAgent, Turn])
def test_set_attribute_defined_on_class(cls: type) -> None:
    assert callable(getattr(cls, "set_attribute", None))


@pytest.mark.parametrize("cls", [Tool, LLM, SubAgent, Turn])
def test_add_event_defined_on_class(cls: type) -> None:
    assert callable(getattr(cls, "add_event", None))
