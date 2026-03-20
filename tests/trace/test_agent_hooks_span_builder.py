"""Tests for the agent hooks span builder.

Validates that Cursor hook events produce correctly structured OTel spans
matching the GenAI semantic conventions.
"""

from __future__ import annotations

import json
import threading

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from weave.agent_hooks.events import AgentHookEvent
from weave.agent_hooks.span_builder import SpanBuilder


class _InMemoryExporter(SpanExporter):
    """Minimal in-memory exporter for testing."""

    def __init__(self) -> None:
        self._spans: list = []
        self._lock = threading.Lock()

    def export(self, spans):
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self) -> list:
        with self._lock:
            return list(self._spans)

    def shutdown(self) -> None:
        pass


def _make_builder() -> tuple[SpanBuilder, _InMemoryExporter]:
    """Create a SpanBuilder backed by an in-memory exporter for testing."""
    exporter = _InMemoryExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    builder = SpanBuilder(provider)
    return builder, exporter


def _event(kind: str, conv: str = "test-conv", gen: str = "gen1", **kwargs) -> AgentHookEvent:
    """Helper to create a test event with defaults."""
    return AgentHookEvent(
        source="cursor",
        event_kind=kind,
        conversation_id=conv,
        generation_id=gen,
        model="claude-sonnet-4",
        workspace_roots=["/test"],
        **kwargs,
    )


class TestBasicTurnStructure:
    """A single turn should produce invoke_agent root + tool children."""

    def test_full_turn_produces_correct_hierarchy(self) -> None:
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="hello"))
        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Read",
                              tool_input={"path": "/foo.py"}))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Read",
                              tool_output="file contents"))
        builder.handle(_event("agent_response", response_text="Done."))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        # 4 spans: invoke_agent root + execute_tool Read + chat (user prompt) + chat (response)
        assert len(spans) == 4, f"Expected 4 spans, got {len(spans)}: {[s.name for s in spans]}"

        tool_span = next(s for s in spans if "Read" in s.name)
        agent_span = next(s for s in spans if "invoke_agent" in s.name)
        response_span = next(
            s
            for s in spans
            if s.name == "chat" and "gen_ai.output.messages" in s.attributes
        )

        # Tool is child of agent
        assert tool_span.parent is not None
        assert tool_span.parent.span_id == agent_span.context.span_id
        assert tool_span.attributes["gen_ai.tool.name"] == "Read"
        assert tool_span.attributes["gen_ai.tool.call.arguments"] == '{"path": "/foo.py"}'
        assert tool_span.attributes["gen_ai.tool.call.result"] == "file contents"

        # Response is child of agent
        assert response_span.parent is not None
        assert response_span.parent.span_id == agent_span.context.span_id
        resp_msgs = json.loads(response_span.attributes["gen_ai.output.messages"])
        assert resp_msgs[0]["content"] == "Done."

        # Agent root has input prompt
        assert agent_span.parent is None
        assert agent_span.attributes["gen_ai.operation.name"] == "invoke_agent"
        msgs_in = json.loads(agent_span.attributes["gen_ai.input.messages"])
        assert msgs_in[0]["content"] == "hello"

    def test_all_spans_share_conversation_id(self) -> None:
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="test"))
        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Shell",
                              tool_input={"command": "ls"}))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Shell",
                              tool_output="file.py"))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        for span in spans:
            assert span.attributes["gen_ai.conversation.id"] == "test-conv"

    def test_all_spans_share_trace_id(self) -> None:
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="test"))
        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Shell",
                              tool_input={"command": "ls"}))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Shell"))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        trace_ids = {s.context.trace_id for s in spans}
        assert len(trace_ids) == 1, f"All spans should share one trace_id, got {len(trace_ids)}"


class TestMultiTurnConversation:
    """Multiple turns in the same conversation should each be a separate trace."""

    def test_two_turns_produce_two_traces(self) -> None:
        builder, exporter = _make_builder()

        # Turn 1
        builder.handle(_event("user_prompt", gen="gen1", prompt_text="turn 1"))
        builder.handle(_event("tool_use_start", gen="gen1", tool_use_id="t1", tool_name="Read",
                              tool_input={"path": "/a.py"}))
        builder.handle(_event("tool_use_end", gen="gen1", tool_use_id="t1", tool_name="Read"))
        builder.handle(_event("agent_response", gen="gen1", response_text="done 1"))
        builder.handle(_event("stop", gen="gen1"))

        # Turn 2
        builder.handle(_event("user_prompt", gen="gen2", prompt_text="turn 2"))
        builder.handle(_event("tool_use_start", gen="gen2", tool_use_id="t2", tool_name="Write",
                              tool_input={"path": "/b.py"}))
        builder.handle(_event("tool_use_end", gen="gen2", tool_use_id="t2", tool_name="Write"))
        builder.handle(_event("agent_response", gen="gen2", response_text="done 2"))
        builder.handle(_event("stop", gen="gen2"))

        spans = exporter.get_finished_spans()
        trace_ids = {s.context.trace_id for s in spans}
        assert len(trace_ids) == 2, f"Expected 2 traces (one per turn), got {len(trace_ids)}"

        # Each trace should have exactly 1 invoke_agent root
        agent_spans = [s for s in spans if "invoke_agent" in s.name]
        assert len(agent_spans) == 2

        # Both should share the same conversation_id
        conv_ids = {s.attributes["gen_ai.conversation.id"] for s in spans}
        assert conv_ids == {"test-conv"}


class TestShellAndFileDedup:
    """shell_exec and file_edit events should NOT create extra spans when
    a tool span is already open for the same operation.
    """

    def test_shell_exec_suppressed_when_tool_span_open(self) -> None:
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="run cmd"))
        # preToolUse fires first
        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Shell",
                              tool_input={"command": "ls -la"}))
        # afterShellExecution fires while Shell tool span is still open
        builder.handle(_event("shell_exec", shell_command="ls -la",
                              shell_output="total 8\ndrwx...", shell_exit_code=0))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Shell",
                              tool_output="total 8\ndrwx..."))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        tool_spans = [s for s in spans if s.attributes.get("gen_ai.operation.name") == "execute_tool"]
        assert len(tool_spans) == 1, (
            f"Expected 1 tool span (Shell), got {len(tool_spans)}: "
            f"{[s.name for s in tool_spans]}"
        )
        assert tool_spans[0].attributes["gen_ai.tool.name"] == "Shell"

    def test_file_edit_suppressed_when_tool_span_open(self) -> None:
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="edit file"))
        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Write",
                              tool_input={"path": "/foo.py", "contents": "x=1"}))
        # afterFileEdit fires while Write tool span is still open
        builder.handle(_event("file_edit", file_path="/foo.py",
                              file_edits=[{"old": "", "new": "x=1"}]))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Write",
                              tool_output="File written"))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        tool_spans = [s for s in spans if s.attributes.get("gen_ai.operation.name") == "execute_tool"]
        assert len(tool_spans) == 1
        assert tool_spans[0].attributes["gen_ai.tool.name"] == "Write"


class TestOrphanEventsDropped:
    """Events that arrive without a prior user_prompt should be silently
    dropped — they must NOT create spurious root traces.
    """

    def test_bare_shell_exec_dropped(self) -> None:
        """A shell_exec with no prior user_prompt produces no spans."""
        builder, exporter = _make_builder()

        builder.handle(_event("shell_exec", shell_command="echo hi",
                              shell_output="hi", shell_exit_code=0))
        builder.handle(_event("session_end"))

        spans = exporter.get_finished_spans()
        assert len(spans) == 0, f"Expected 0 spans, got {[s.name for s in spans]}"

    def test_tool_use_without_prompt_dropped(self) -> None:
        """Tool events with no prior user_prompt produce no spans."""
        builder, exporter = _make_builder()

        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Read",
                              tool_input={"path": "/x.py"}))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Read",
                              tool_output="contents"))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        assert len(spans) == 0, f"Expected 0 spans, got {[s.name for s in spans]}"

    def test_events_after_stop_dropped_until_next_prompt(self) -> None:
        """Events between stop and the next user_prompt are dropped."""
        builder, exporter = _make_builder()

        # Turn 1
        builder.handle(_event("user_prompt", gen="gen1", prompt_text="hello"))
        builder.handle(_event("stop", gen="gen1"))

        # Orphan events (no user_prompt yet)
        builder.handle(_event("tool_use_start", gen="gen1", tool_use_id="t1",
                              tool_name="Shell", tool_input={"command": "ls"}))
        builder.handle(_event("shell_exec", gen="gen1", shell_command="ls"))
        builder.handle(_event("tool_use_end", gen="gen1", tool_use_id="t1",
                              tool_name="Shell"))

        # Turn 2 — only this should produce a trace
        builder.handle(_event("user_prompt", gen="gen2", prompt_text="world"))
        builder.handle(_event("stop", gen="gen2"))

        spans = exporter.get_finished_spans()
        agent_spans = [s for s in spans if "invoke_agent" in s.name]
        assert len(agent_spans) == 2, (
            f"Expected 2 invoke_agent spans (one per prompt), got "
            f"{len(agent_spans)}: {[s.name for s in spans]}"
        )
        # No orphan tool spans
        tool_spans = [s for s in spans if "execute_tool" in s.name]
        assert len(tool_spans) == 0


class TestSubagentEvents:
    """Subagent start/stop should create child invoke_agent spans."""

    def test_subagent_creates_child_span(self) -> None:
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="do research"))
        builder.handle(_event("subagent_start", subagent_id="sub1",
                              subagent_type="explore", subagent_task="find files"))
        builder.handle(_event("subagent_stop", subagent_id="sub1",
                              subagent_status="completed", subagent_duration_ms=5000,
                              subagent_tool_call_count=3))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        subagent_span = next(s for s in spans if "explore" in s.name)
        root_span = next(s for s in spans if "cursor-agent" in s.name)

        assert subagent_span.parent is not None
        assert subagent_span.parent.span_id == root_span.context.span_id
        assert subagent_span.attributes["gen_ai.operation.name"] == "invoke_agent"


class TestAgentThoughtsAndResponses:
    """Thoughts and responses should be emitted as individual child chat spans."""

    def test_thoughts_and_response_as_child_spans(self) -> None:
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="think about this"))
        builder.handle(_event("agent_thought", thought_text="Let me consider..."))
        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Read",
                              tool_input={"path": "/f.py"}))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Read",
                              tool_output="content"))
        builder.handle(_event("agent_thought", thought_text="Now I know."))
        builder.handle(_event("agent_response", response_text="The answer is 42."))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        agent_span = next(s for s in spans if "invoke_agent" in s.name)
        chat_spans = [s for s in spans if s.name == "chat"]
        tool_spans = [s for s in spans if "Read" in s.name]

        # 4 chat spans: user prompt + 2 thoughts + 1 response
        assert len(chat_spans) == 4, (
            f"Expected 4 chat spans, got {len(chat_spans)}: {[s.name for s in spans]}"
        )
        assert len(tool_spans) == 1

        # All chat spans are children of the agent span
        for cs in chat_spans:
            assert cs.parent is not None
            assert cs.parent.span_id == agent_span.context.span_id

        # Chat spans with model output (thoughts + final response)
        output_chats = [
            s for s in chat_spans if "gen_ai.output.messages" in s.attributes
        ]
        assert len(output_chats) == 3
        texts = []
        for cs in output_chats:
            msgs = json.loads(cs.attributes["gen_ai.output.messages"])
            texts.append(msgs[0]["content"])
        assert "Let me consider" in texts[0]
        assert "Now I know" in texts[1]
        assert "The answer is 42" in texts[2]

    def test_thoughts_interleaved_chronologically(self) -> None:
        """Thought/tool/thought/response should appear in timestamp order."""
        builder, exporter = _make_builder()

        builder.handle(_event("user_prompt", prompt_text="do work"))
        builder.handle(_event("agent_thought", thought_text="First thought"))
        builder.handle(_event("tool_use_start", tool_use_id="t1", tool_name="Shell",
                              tool_input={"command": "ls"}))
        builder.handle(_event("tool_use_end", tool_use_id="t1", tool_name="Shell",
                              tool_output="files"))
        builder.handle(_event("agent_thought", thought_text="Second thought"))
        builder.handle(_event("agent_response", response_text="All done."))
        builder.handle(_event("stop"))

        spans = exporter.get_finished_spans()
        # Check chronological order: thought1, tool, thought2, response
        child_spans = sorted(
            [s for s in spans if s.parent is not None],
            key=lambda s: s.start_time,
        )
        names = [s.name for s in child_spans]
        assert names == ["chat", "chat", "execute_tool Shell", "chat", "chat"]
