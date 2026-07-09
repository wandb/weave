"""Tests for SubAgent child nesting and the new ``SubAgent.start_subagent()`` method.

Two things are exercised here:

1. ``SubAgent.start_subagent(name, model)`` — a NEW method mirroring
   ``Turn.start_subagent()``. Lets the user nest invocations: outer agent →
   inner agent.

2. ``SubAgent`` captures its OTel context at ``__enter__`` and threads it
   to children created via ``.start_llm()`` / ``.start_tool()`` / ``.start_subagent()``. The
   children pin their OTel parent to the SubAgent's span explicitly,
   so they nest correctly even if the ambient OTel context drifts (e.g.
   the caller exits ``with sub:`` before creating the child).
"""

from __future__ import annotations

import threading

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.conversation.conversation import (
    LLM,
    Conversation,
    SubAgent,
    Tool,
    Turn,
    get_current_llm,
    get_current_subagent,
    get_current_turn,
    start_llm,
    start_subagent,
    start_tool,
    start_turn,
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
# New: SubAgent.start_subagent() method exists and returns a SubAgent
# ---------------------------------------------------------------------------


class TestSubagentMethodExists:
    def test_returns_subagent(self) -> None:
        sa = SubAgent(name="outer")
        nested = sa.start_subagent(name="inner")
        assert isinstance(nested, SubAgent)
        assert nested.name == "inner"

    @pytest.mark.parametrize(
        ("child_model", "expected"),
        [
            ("", "gpt-4o"),  # unspecified -> inherits the parent's model
            ("gpt-4o-mini", "gpt-4o-mini"),  # explicit model overrides inherited
        ],
    )
    def test_model_inheritance(self, child_model: str, expected: str) -> None:
        outer = SubAgent(name="outer", model="gpt-4o")
        inner = outer.start_subagent(name="inner", model=child_model)
        assert inner.model == expected


# ---------------------------------------------------------------------------
# Standard nesting (children created inside ``with sub:``)
# ---------------------------------------------------------------------------


class TestStandardNesting:
    """The common pattern: enter SubAgent, then call ``.start_llm()`` / etc."""

    def test_llm_nests_under_subagent(self, otel_spans: InMemorySpanExporter) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="researcher") as sa:
                with sa.start_llm(model="gpt-4o"):
                    pass
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent.span_id == sa_span.context.span_id

    def test_tool_nests_under_subagent(self, otel_spans: InMemorySpanExporter) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="researcher") as sa:
                with sa.start_tool(name="web_search", tool_call_id="tc-1"):
                    pass
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == sa_span.context.span_id

    def test_subagent_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="outer") as outer:
                with outer.start_subagent(name="inner"):
                    pass
        spans = otel_spans.get_finished_spans()
        outer_span = _by_agent_name(spans, "outer")
        inner_span = _by_agent_name(spans, "inner")
        assert inner_span.parent.span_id == outer_span.context.span_id

    def test_three_level_chain(self, otel_spans: InMemorySpanExporter) -> None:
        """Turn → outer_sub → inner_sub → llm. Each parent links to the level above."""
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="outer") as outer:
                with outer.start_subagent(name="inner") as inner:
                    with inner.start_llm(model="gpt-4o"):
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
        SubAgent because ``.start_llm()`` captured the SubAgent's context at the
        moment the SubAgent was entered.
        """
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            sa = turn.start_subagent(name="researcher")
            with sa:
                # Grab a handle to the LLM while SubAgent is the ambient
                # context — but DO NOT enter it yet.
                llm = sa.start_llm(model="gpt-4o")
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
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            sa = turn.start_subagent(name="researcher")
            with sa:
                tool = sa.start_tool(name="web_search", tool_call_id="tc-1")
            with tool:
                pass

        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == sa_span.context.span_id

    def test_subagent_created_after_outer_exits_still_nests(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            outer = turn.start_subagent(name="outer")
            with outer:
                inner = outer.start_subagent(name="inner")
            with inner:
                pass

        spans = otel_spans.get_finished_spans()
        outer_span = _by_agent_name(spans, "outer")
        inner_span = _by_agent_name(spans, "inner")
        assert inner_span.parent.span_id == outer_span.context.span_id


# ---------------------------------------------------------------------------
# Robust nesting for a Turn's children too: a child built inside ``with turn:``
# but entered after the Turn exits still nests under the Turn instead of
# becoming a detached root span. Same mechanism as SubAgent, on ``_SpanBase``.
# ---------------------------------------------------------------------------


class TestTurnExplicitContextWinsOverAmbient:
    """A Turn is usually used entirely within its own ``with`` block, but if a
    child is created in-block and entered out-of-block (queue worker, callback),
    the ambient OTel context has drifted back to the Conversation — which has no
    span — so pre-fix the child became a detached root span in its own trace.
    """

    def test_llm_created_after_turn_exits_still_nests_under_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"):
            turn = Turn(agent_name="bot")
            with turn:
                llm = turn.start_llm(model="gpt-4o")  # constructed here, not entered
            # Turn has exited; ambient OTel context is back to the Conversation.
            with llm:
                pass

        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent is not None
        assert llm_span.parent.span_id == turn_span.context.span_id

    def test_tool_created_after_turn_exits_still_nests_under_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"):
            turn = Turn(agent_name="bot")
            with turn:
                tool = turn.start_tool(name="web_search", tool_call_id="tc-1")
            with tool:
                pass

        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent is not None
        assert tool_span.parent.span_id == turn_span.context.span_id

    def test_subagent_created_after_turn_exits_still_nests_under_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"):
            turn = Turn(agent_name="bot")
            with turn:
                sa = turn.start_subagent(name="researcher")
            with sa:
                pass

        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        sa_span = _by_agent_name(spans, "researcher")
        assert sa_span.parent is not None
        assert sa_span.parent.span_id == turn_span.context.span_id


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
        with Conversation(conversation_id="s"), Turn(agent_name="bot"):
            with LLM(model="gpt-4o"):
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent.span_id == turn_span.context.span_id

    def test_standalone_tool_uses_ambient_when_no_parent_context(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot"):
            with Tool(name="f"):
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == turn_span.context.span_id


# ---------------------------------------------------------------------------
# Cross-thread: a child built in one thread but entered in another still nests
# under its parent, because the parent context is threaded explicitly on the
# object rather than via thread-local ambient context. (Cross-process is not
# supported — the parent span/context are in-memory; that needs OTel context
# propagation.)
# ---------------------------------------------------------------------------


class TestCrossThread:
    def test_child_entered_in_another_thread_still_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        errbox: dict[str, str] = {}
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="researcher") as sa:
                llm = sa.start_llm(model="gpt-4o")  # built in this thread

            # Enter/exit the LLM in a DIFFERENT thread, where ambient OTel
            # context is empty and the contextvar token was set elsewhere.
            def worker() -> None:
                try:
                    with llm:
                        pass
                except BaseException as exc:
                    errbox["err"] = repr(exc)

            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()

        assert "err" not in errbox, errbox.get("err")
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent is not None
        assert llm_span.parent.span_id == sa_span.context.span_id


# ---------------------------------------------------------------------------
# The `_current_subagent` contextvar: `get_current_subagent()` reflects the
# subagent whose ``with`` block we're inside, and nested subagents stack.
# ---------------------------------------------------------------------------


class TestCurrentSubagentContextvar:
    def test_current_subagent_set_inside_reset_outside(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        assert get_current_subagent() is None
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            assert get_current_subagent() is None  # a Turn is not a SubAgent
            with turn.start_subagent(name="researcher") as sa:
                assert get_current_subagent() is sa
            assert get_current_subagent() is None
        assert get_current_subagent() is None

    def test_current_subagent_stacks_for_nested(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="outer") as outer:
                assert get_current_subagent() is outer
                with outer.start_subagent(name="inner") as inner:
                    assert get_current_subagent() is inner
                assert get_current_subagent() is outer  # restored on inner exit
            assert get_current_subagent() is None


# ---------------------------------------------------------------------------
# Gap 1: the IMPLICIT top-level factories resolve the current SubAgent (not just
# the Turn), so `weave.start_llm()` / `start_tool()` / `start_subagent()` used
# inside a subagent nest under the subagent — matching the explicit `sa.start_*`.
# ---------------------------------------------------------------------------


class TestImplicitPathNestsUnderSubagent:
    def test_implicit_start_llm_inside_subagent_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="researcher"):
                with start_llm(model="gpt-4o"):  # top-level implicit
                    pass
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent.span_id == sa_span.context.span_id

    def test_implicit_start_tool_inside_subagent_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="researcher"):
                with start_tool(name="web_search", tool_call_id="tc-1"):
                    pass
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == sa_span.context.span_id

    def test_implicit_start_subagent_inside_subagent_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="outer"):
                with start_subagent(name="inner"):  # top-level implicit
                    pass
        spans = otel_spans.get_finished_spans()
        outer_span = _by_agent_name(spans, "outer")
        inner_span = _by_agent_name(spans, "inner")
        assert inner_span.parent.span_id == outer_span.context.span_id


# ---------------------------------------------------------------------------
# Gap 2: top-level `start_tool` / `start_subagent` DELEGATE (like `start_llm`),
# so a child built in-block but entered after the parent exits nests under the
# parent instead of detaching into its own trace.
# ---------------------------------------------------------------------------


class TestImplicitOutOfBlockNesting:
    def test_implicit_tool_after_turn_exits_nests_under_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"):
            turn = Turn(agent_name="bot")
            with turn:
                tool = start_tool(name="web_search", tool_call_id="tc-1")  # implicit
            with tool:  # entered after the turn exits
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent is not None
        assert tool_span.parent.span_id == turn_span.context.span_id
        assert tool_span.context.trace_id == turn_span.context.trace_id

    def test_implicit_subagent_after_turn_exits_nests_under_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"):
            turn = Turn(agent_name="bot")
            with turn:
                sa = start_subagent(name="researcher")  # implicit
            with sa:  # entered after the turn exits
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = _by_prefix(spans, "invoke_agent bot")
        sa_span = _by_agent_name(spans, "researcher")
        assert sa_span.parent is not None
        assert sa_span.parent.span_id == turn_span.context.span_id
        assert sa_span.context.trace_id == turn_span.context.trace_id

    def test_implicit_tool_inside_subagent_after_subagent_exits_nests_under_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            sa = turn.start_subagent(name="researcher")
            with sa:
                tool = start_tool(name="web_search", tool_call_id="tc-1")  # implicit
            with tool:
                pass
        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        tool_span = _by_prefix(spans, "execute_tool")
        assert tool_span.parent.span_id == sa_span.context.span_id


# ---------------------------------------------------------------------------
# Gap 4: an explicit child built in one thread and entered/ended in another must
# not strand the source thread's `_current_llm` contextvar on the ended span.
# ---------------------------------------------------------------------------


class TestNoCrossThreadContextvarLeak:
    def test_llm_entered_in_worker_does_not_strand_source_thread_current_llm(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            with turn.start_subagent(name="researcher") as sa:
                llm = sa.start_llm(model="gpt-4o")  # built in this (main) thread

            def worker() -> None:
                with llm:  # entered + ended entirely in the worker thread
                    pass

            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()

            # The main thread never entered the LLM, so it must not be left as
            # the "current" LLM — least of all the now-ended one.
            assert get_current_llm() is None

        spans = otel_spans.get_finished_spans()
        sa_span = _by_agent_name(spans, "researcher")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent.span_id == sa_span.context.span_id


# ---------------------------------------------------------------------------
# A Turn is never a child of a SubAgent ("a sub-agent can't start a turn").
# Starting a new turn — or entering one — drops any lingering current sub-agent
# from a prior turn, so the turn's own implicit children nest under the Turn,
# not a stale sub-agent (which would land them in the previous turn's trace).
# ---------------------------------------------------------------------------


class TestStartTurnSkipsActiveSubagent:
    def test_implicit_start_turn_clears_current_subagent(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn1:
            with turn1.start_subagent(name="sa"):
                assert get_current_subagent() is not None
                start_turn(agent_name="bot2")  # top-level implicit
                assert get_current_subagent() is None
                assert get_current_turn() is not None

    def test_entering_a_turn_clears_subagent_and_restores_on_exit(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn1:
            with turn1.start_subagent(name="sa") as sa:
                with Turn(agent_name="bot2"):
                    assert get_current_subagent() is None
                # back inside the enclosing sub-agent's block
                assert get_current_subagent() is sa

    def test_implicit_llm_after_start_turn_in_subagent_nests_under_new_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """The core bug: an LLM started (implicitly) under a turn begun while a
        sub-agent was still current must nest under that new turn — same trace —
        not the stale sub-agent from the previous turn's trace.
        """
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn1:
            with turn1.start_subagent(name="sa"):
                turn2 = start_turn(agent_name="bot2")
                with turn2:
                    with start_llm(model="gpt-4o"):
                        pass
        spans = otel_spans.get_finished_spans()
        turn2_span = _by_agent_name(spans, "bot2")
        llm_span = _by_prefix(spans, "chat")
        assert llm_span.parent is not None
        assert llm_span.parent.span_id == turn2_span.context.span_id
        assert llm_span.context.trace_id == turn2_span.context.trace_id
