"""Tests for the explicit ``parent=`` override and W3C ``traceparent``
cross-process propagation on the implicit ``start_*`` factories.

``parent=`` resolves to one of:
- a ``Turn`` / ``SubAgent`` object — nest under it explicitly (override ambient);
- ``"ignore"`` — force a brand-new root trace;
- a W3C ``traceparent`` string — adopt a remote parent (cross-process).
"""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.conversation.conversation import (
    Conversation,
    Turn,
    start_llm,
    start_subagent,
    start_tool,
    start_turn,
)


def _by_name(spans: list, name: str):
    matches = [s for s in spans if s.name == name]
    assert len(matches) == 1, f"expected 1 {name!r}, got {[s.name for s in spans]}"
    return matches[0]


def _by_prefix(spans: list, prefix: str):
    matches = [s for s in spans if s.name.startswith(prefix)]
    assert len(matches) == 1, f"expected 1 {prefix!r}, got {[s.name for s in spans]}"
    return matches[0]


class TestParentContainerOverride:
    def test_llm_parent_overrides_ambient_container(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """Inside a sub-agent, ``parent=<turn>`` nests the LLM under the turn,
        not the ambient sub-agent.
        """
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="sa"):
                with start_llm(model="m", parent=turn):
                    pass
        spans = otel_spans.get_finished_spans()
        turn_sp = _by_prefix(spans, "invoke_agent bot")
        llm_sp = _by_name(spans, "chat m")
        assert llm_sp.parent.span_id == turn_sp.context.span_id

    def test_tool_parent_overrides_ambient_container(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="sa"):
                with start_tool(name="f", tool_call_id="t1", parent=turn):
                    pass
        spans = otel_spans.get_finished_spans()
        turn_sp = _by_prefix(spans, "invoke_agent bot")
        tool_sp = _by_prefix(spans, "execute_tool")
        assert tool_sp.parent.span_id == turn_sp.context.span_id

    def test_subagent_parent_overrides_ambient_container(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="outer"):
                with start_subagent(name="pinned", parent=turn):
                    pass
        spans = otel_spans.get_finished_spans()
        turn_sp = _by_prefix(spans, "invoke_agent bot")
        pinned = _by_prefix(spans, "invoke_agent pinned")
        assert pinned.parent.span_id == turn_sp.context.span_id


class TestParentIgnore:
    def test_ignore_forces_new_root_trace(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with start_llm(model="m", parent="ignore"):
                pass
        spans = otel_spans.get_finished_spans()
        turn_sp = _by_prefix(spans, "invoke_agent bot")
        llm_sp = _by_name(spans, "chat m")
        assert llm_sp.parent is None
        assert llm_sp.context.trace_id != turn_sp.context.trace_id


class TestTraceparent:
    def test_empty_before_span_starts(self) -> None:
        # A turn that was never entered has no span -> empty traceparent.
        assert Turn(agent_name="bot").traceparent() == ""

    def test_export_is_w3c_format(self, otel_spans: InMemorySpanExporter) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            tp = turn.traceparent()
        # 00-<32 hex trace>-<16 hex span>-<2 hex flags>
        version, trace_id, span_id, flags = tp.split("-")
        assert version == "00"
        assert len(trace_id) == 32
        assert len(span_id) == 16
        assert len(flags) == 2

    def test_adopt_nests_under_remote_parent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """Export one turn's traceparent, then a later start_turn(parent=tp)
        nests under it — same trace, parent = the exported span.
        """
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            tp = turn.traceparent()
        bot_sp = _by_prefix(otel_spans.get_finished_spans(), "invoke_agent bot")

        # No conversation/turn active here — the remote parent is adopted purely
        # from the traceparent string (the cross-process case).
        with start_turn(parent=tp, agent_name="child"):
            pass

        child_sp = _by_prefix(otel_spans.get_finished_spans(), "invoke_agent child")
        assert child_sp.parent is not None
        assert child_sp.parent.span_id == bot_sp.context.span_id
        assert child_sp.context.trace_id == bot_sp.context.trace_id
