"""Tests for the ``end_subagent`` / ``end_tool`` convenience functions (closing
the ``end_*`` asymmetry) and the async context-manager support (``async with``).
"""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import weave
from weave.conversation.conversation import (
    Conversation,
    Turn,
    end_subagent,
    end_tool,
    get_current_subagent,
    get_current_tool,
    start_subagent,
    start_tool,
)


def _by_name(spans: list, name: str):
    matches = [s for s in spans if s.name == name]
    assert len(matches) == 1, f"expected 1 {name!r}, got {[s.name for s in spans]}"
    return matches[0]


def _by_prefix(spans: list, prefix: str):
    matches = [s for s in spans if s.name.startswith(prefix)]
    assert len(matches) == 1, f"expected 1 {prefix!r}, got {[s.name for s in spans]}"
    return matches[0]


class TestEndSubagentAndTool:
    def test_end_subagent_clears_current(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """Imperative ``start_subagent`` makes it current; ``end_subagent`` ends
        it and restores the enclosing container (mirrors ``end_turn``).
        """
        with Conversation(conversation_id="s"), Turn(agent_name="bot"):
            sa = start_subagent(name="sa")
            assert get_current_subagent() is sa
            end_subagent()
            assert get_current_subagent() is None

    def test_end_tool_clears_current(self, otel_spans: InMemorySpanExporter) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot"):
            tool = start_tool(name="f", tool_call_id="t1")
            assert get_current_tool() is tool
            end_tool()
            assert get_current_tool() is None

    def test_get_current_tool_tracks_with_block(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(conversation_id="s"), Turn(agent_name="bot") as turn:
            assert get_current_tool() is None
            with turn.start_tool(name="f", tool_call_id="t1") as tool:
                assert get_current_tool() is tool
            assert get_current_tool() is None  # auto-ended on __exit__
        # the tool span was emitted under the turn
        spans = otel_spans.get_finished_spans()
        turn_sp = _by_prefix(spans, "invoke_agent bot")
        tool_sp = _by_prefix(spans, "execute_tool")
        assert tool_sp.parent.span_id == turn_sp.context.span_id


class TestAsyncContextManagers:
    @pytest.mark.asyncio
    async def test_async_conversation_turn_llm_nest(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        async with weave.start_conversation(conversation_id="s"):
            async with weave.start_turn(agent_name="bot") as turn:
                async with turn.start_llm(model="m"):
                    pass
        spans = otel_spans.get_finished_spans()
        turn_sp = _by_prefix(spans, "invoke_agent bot")
        llm_sp = _by_name(spans, "chat m")
        assert llm_sp.parent.span_id == turn_sp.context.span_id

    @pytest.mark.asyncio
    async def test_async_subagent_nesting(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        async with weave.start_conversation(conversation_id="s"):
            async with weave.start_turn(agent_name="bot") as turn:
                async with turn.start_subagent(name="sa") as sa:
                    async with sa.start_llm(model="m"):
                        pass
        spans = otel_spans.get_finished_spans()
        sa_sp = _by_prefix(spans, "invoke_agent sa")
        llm_sp = _by_name(spans, "chat m")
        assert llm_sp.parent.span_id == sa_sp.context.span_id
