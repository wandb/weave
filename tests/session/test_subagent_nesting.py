"""Tests for SubAgent child nesting and the new ``SubAgent.subagent()`` method.

Two things are exercised here:

1. ``SubAgent.subagent(name, model)`` — a NEW method mirroring
   ``Turn.subagent()`` and the TypeScript ``startSubagent`` factory on
   SubAgent. Lets the user nest invocations: outer agent → inner agent.

2. ``SubAgent`` captures its OTel context at ``__enter__`` and threads it
   to children created via ``.llm()`` / ``.tool()`` / ``.subagent()``. The
   children pin their OTel parent to the SubAgent's span explicitly,
   so they nest correctly even if the ambient OTel context drifts (e.g.
   the caller exits ``with sub:`` before creating the child).
"""

from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session.session import (
    LLM,
    Session,
    SubAgent,
    Tool,
    Turn,
)


def _by_agent_name(spans: list, agent_name: str):
    """Find the single invoke_agent span tagged with ``agent_name``."""
    matches = [
        sp
        for sp in spans
        if sp.name.startswith("invoke_agent")
        and sp.attributes.get("gen_ai.agent.name") == agent_name
    ]
    assert len(matches) == 1, (
        f"expected 1 invoke_agent for {agent_name!r}, got "
        f"{[(s.name, s.attributes.get('gen_ai.agent.name')) for s in matches]}"
    )
    return matches[0]


def _by_prefix(spans: list, prefix: str):
    matches = [sp for sp in spans if sp.name.startswith(prefix)]
    assert len(matches) == 1, (
        f"expected 1 span with prefix {prefix!r}, got {[s.name for s in matches]}"
    )
    return matches[0]


# ---------------------------------------------------------------------------
# New: SubAgent.subagent() method exists and returns a SubAgent
# ---------------------------------------------------------------------------


class TestSubagentMethodExists:
    def test_returns_subagent(self) -> None:
        sa = SubAgent(name="outer")
        nested = sa.subagent(name="inner")
        assert isinstance(nested, SubAgent)
        assert nested.name == "inner"

    def test_inherits_model_when_not_specified(self) -> None:
        outer = SubAgent(name="outer", model="gpt-4o")
        inner = outer.subagent(name="inner")
        assert inner.model == "gpt-4o"

    def test_explicit_model_overrides_inherited(self) -> None:
        outer = SubAgent(name="outer", model="gpt-4o")
        inner = outer.subagent(name="inner", model="gpt-4o-mini")
        assert inner.model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Standard nesting (children created inside ``with sub:``)
# ---------------------------------------------------------------------------


class TestStandardNesting:
    """The common pattern: enter SubAgent, then call ``.llm()`` / etc."""

    def test_llm_nests_under_subagent(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with turn.subagent(name="researcher") as sa:
                with sa.llm(model="gpt-4o"):
                    pass
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent.span_id == sa_span.context.span_id

    def test_tool_nests_under_subagent(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with turn.subagent(name="researcher") as sa:
                with sa.tool(name="web_search", tool_call_id="tc-1"):
                    pass
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == sa_span.context.span_id

    def test_subagent_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with turn.subagent(name="outer") as outer:
                with outer.subagent(name="inner"):
                    pass
        spans = otel_spans.get_finished_spans()
        outer_span = _by_agent_name(spans, "outer")
        inner_span = _by_agent_name(spans, "inner")
        assert inner_span.parent.span_id == outer_span.context.span_id

    def test_three_level_chain(self, otel_spans: InMemorySpanExporter) -> None:
        """Turn → outer_sub → inner_sub → llm. Each parent links to the level above."""
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with turn.subagent(name="outer") as outer:
                with outer.subagent(name="inner") as inner:
                    with inner.llm(model="gpt-4o"):
                        pass
        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        outer_span = _by_agent_name(spans, "outer")
        inner_span = _by_agent_name(spans, "inner")
        llm_span = _by_prefix(spans, "chat")
        assert outer_span.parent.span_id == turn_span.context.span_id
        assert inner_span.parent.span_id == outer_span.context.span_id
        assert llm_span.parent.span_id == inner_span.context.span_id


# ---------------------------------------------------------------------------
# Robust nesting: explicit context wins over ambient
# ---------------------------------------------------------------------------


class TestExplicitContextWinsOverAmbient:
    """When the ambient OTel context drifts away from the SubAgent (the
    caller created the child outside ``with sub:``), the explicit parent
    context captured at ``__enter__`` still pins the child to the SubAgent.
    """

    def test_llm_created_after_subagent_exits_still_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """Pre-fix this nested under Turn (ambient); post-fix it nests under
        SubAgent because ``.llm()`` captured the SubAgent's context at the
        moment the SubAgent was entered.
        """
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            sa = turn.subagent(name="researcher")
            with sa:
                # Grab a handle to the LLM while SubAgent is the ambient
                # context — but DO NOT enter it yet.
                llm = sa.llm(model="gpt-4o")
            # SubAgent has exited; ambient OTel context is back to Turn.
            with llm:
                pass

        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent.span_id == sa_span.context.span_id

    def test_tool_created_after_subagent_exits_still_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            sa = turn.subagent(name="researcher")
            with sa:
                tool = sa.tool(name="web_search", tool_call_id="tc-1")
            with tool:
                pass

        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == sa_span.context.span_id

    def test_subagent_created_after_outer_exits_still_nests(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            outer = turn.subagent(name="outer")
            with outer:
                inner = outer.subagent(name="inner")
            with inner:
                pass

        spans = otel_spans.get_finished_spans()
        outer_span = _by_agent_name(spans, "outer")
        inner_span = _by_agent_name(spans, "inner")
        assert inner_span.parent.span_id == outer_span.context.span_id


# ---------------------------------------------------------------------------
# Backwards-compat: SubAgent constructed standalone (no parent SubAgent)
# behaves the same as before — ambient context picks up parent.
# ---------------------------------------------------------------------------


class TestBackwardsCompatible:
    def test_standalone_llm_uses_ambient_when_no_parent_context(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """A bare ``LLM()`` (no parent SubAgent) still inherits ambient context
        when entered — Turn here. This is the regression guard for callers that
        construct LLMs directly without going through a SubAgent.
        """
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with LLM(model="gpt-4o"):
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent.span_id == turn_span.context.span_id
        _ = turn  # silence "unused"

    def test_standalone_tool_uses_ambient_when_no_parent_context(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            with Tool(name="f"):
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == turn_span.context.span_id
        _ = turn
