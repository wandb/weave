"""Tests for the Conversation SDK API surface."""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from weave.conversation.conversation import (
    LLM,
    Conversation,
    LogResult,
    Message,
    Reasoning,
    SubAgent,
    Tool,
    Turn,
    Usage,
    end_conversation,
    end_llm,
    end_turn,
    get_current_conversation,
    get_current_llm,
    get_current_turn,
    start_conversation,
    start_llm,
    start_tool,
    start_turn,
)

_fake_ref_counter = iter(range(1, 10_000))


def _fake_publish_media_content(**kwargs: object) -> str:
    return f"weave:///test/project/object/content:{next(_fake_ref_counter)}"


@pytest.fixture(autouse=True)
def _reset_contextvars():
    """Reset contextvar state after each test to prevent leakage."""
    yield
    if (llm := get_current_llm()) is not None:
        llm.end()
    if (turn := get_current_turn()) is not None:
        turn.end()
    if (conversation := get_current_conversation()) is not None:
        conversation.end()


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class TestMessage:
    def test_defaults(self) -> None:
        msg = Message(role="user")
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.tool_call_id == ""
        assert msg.tool_name == ""

    def test_all_fields(self) -> None:
        msg = Message(
            role="tool",
            content="result",
            tool_call_id="tc_1",
            tool_name="get_weather",
        )
        assert msg.role == "tool"
        assert msg.content == "result"
        assert msg.tool_call_id == "tc_1"
        assert msg.tool_name == "get_weather"


class TestUsage:
    def test_defaults(self) -> None:
        u = Usage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.reasoning_tokens == 0

    def test_set_fields(self) -> None:
        u = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=20)
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.reasoning_tokens == 20


class TestReasoning:
    def test_defaults(self) -> None:
        r = Reasoning()
        assert r.content == ""

    def test_set_content(self) -> None:
        r = Reasoning(content="thinking...")
        assert r.content == "thinking..."


class TestLogResult:
    def test_defaults(self) -> None:
        lr = LogResult()
        assert lr.conversation_id == ""
        assert lr.trace_ids == []
        assert lr.root_span_ids == []
        assert lr.span_count == 0


# ---------------------------------------------------------------------------
# Core classes
# ---------------------------------------------------------------------------


class TestTool:
    def test_defaults(self) -> None:
        t = Tool(name="get_weather")
        assert t.name == "get_weather"
        assert t.arguments == ""
        assert t.result == ""
        assert t.tool_call_id == ""
        assert t.duration_ms == 0

    def test_context_manager(self) -> None:
        with Tool(name="search", arguments='{"q":"test"}') as t:
            t.result = "found it"
        assert t.result == "found it"
        assert t.duration_ms >= 0

    def test_end_idempotent(self) -> None:
        t = Tool(name="x")
        t.end()
        t.end()  # second call is a no-op


class TestLLM:
    def test_defaults(self) -> None:
        c = LLM(model="gpt-4o")
        assert c.model == "gpt-4o"
        assert c.provider_name == ""
        assert c.response_id == ""
        assert c.system_instructions == []
        assert isinstance(c.usage, Usage)
        assert isinstance(c.reasoning, Reasoning)
        assert c.finish_reasons == []
        assert c.input_messages == []
        assert c.output_messages == []

    def test_fluent_builders(self) -> None:
        c = LLM(model="gpt-4o")
        assert c.output("Hello!") is c
        assert len(c.output_messages) == 1
        assert c.output_messages[0].role == "assistant"
        assert c.output_messages[0].content == "Hello!"
        assert c.think("Let me consider...") is c
        assert c.reasoning.content == "Let me consider..."

    def test_attach_media_returns_self(self) -> None:
        with patch(
            "weave.conversation.conversation._publish_media_content",
            side_effect=_fake_publish_media_content,
        ):
            c = LLM(model="gpt-4o")
            assert c.attach_media(content=b"png_bytes", mime_type="image/png") is c
            c._await_uploads()

    def test_context_manager_sets_timestamps(self) -> None:
        with LLM(model="gpt-4o") as c:
            assert c.started_at is not None
        assert c.ended_at is not None

    def test_usage_assignment(self) -> None:
        c = LLM(model="gpt-4o")
        c.usage = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=20)
        assert c.usage.input_tokens == 100


class TestAttachMedia:
    @pytest.fixture(autouse=True)
    def _mock_publish(self) -> None:
        with patch(
            "weave.conversation.conversation._publish_media_content",
            side_effect=_fake_publish_media_content,
        ):
            yield  # type: ignore[misc]

    def test_attach_inline_image(self) -> None:
        llm = LLM(model="gpt-4o")
        result = llm.attach_media(content=b"png_bytes", mime_type="image/png")
        assert result is llm
        assert len(llm.media_attachments) == 1
        llm._await_uploads()
        att = llm.media_attachments[0]
        assert att.ref.startswith("weave:///")
        assert att.modality == "image"
        assert att.mime_type == "image/png"

    def test_attach_uri(self) -> None:
        llm = LLM(model="gpt-4o")
        llm.attach_media(
            uri="https://example.com/photo.jpg",
            modality="image",
            mime_type="image/jpeg",
        )
        assert len(llm.media_attachments) == 1
        llm._await_uploads()
        att = llm.media_attachments[0]
        assert att.ref.startswith("weave:///")
        assert att.modality == "image"
        assert att.mime_type == "image/jpeg"

    def test_attach_file_id(self) -> None:
        llm = LLM(model="gpt-4o")
        llm.attach_media(file_id="file-abc123", mime_type="audio/wav")
        assert len(llm.media_attachments) == 1
        llm._await_uploads()
        att = llm.media_attachments[0]
        assert att.ref.startswith("weave:///")
        assert att.modality == "audio"
        assert att.mime_type == "audio/wav"

    def test_modality_inferred_from_mime_type(self) -> None:
        llm = LLM(model="gpt-4o")
        llm.attach_media(content=b"data", mime_type="audio/wav")
        assert llm.media_attachments[0].modality == "audio"
        llm.attach_media(content=b"data", mime_type="video/mp4")
        assert llm.media_attachments[1].modality == "video"
        llm._await_uploads()

    def test_rejects_zero_sources(self) -> None:
        llm = LLM(model="gpt-4o")
        with pytest.raises(ValueError, match="Exactly one of"):
            llm.attach_media()

    def test_rejects_multiple_sources(self) -> None:
        llm = LLM(model="gpt-4o")
        with pytest.raises(ValueError, match="Exactly one of"):
            llm.attach_media(content=b"x", uri="http://x")


class TestAttachMediaAsync:
    """attach_media uploads off-thread, in parallel, joined before the span."""

    def test_attach_media_does_not_block(self) -> None:
        """The call returns before the (slow) upload finishes."""
        release = threading.Event()

        def slow_publish(**kwargs: object) -> str:
            release.wait(timeout=5)
            return "weave:///e/p/object/content:done"

        with patch(
            "weave.conversation.conversation._publish_media_content",
            side_effect=slow_publish,
        ):
            llm = LLM(model="gpt-4o")
            llm.attach_media(content=b"x", mime_type="image/png")
            # Upload still in flight: the placeholder exists but its ref is
            # not yet populated, even though the call already returned.
            assert llm.media_attachments[0].ref == ""
            release.set()
            llm._await_uploads()
            assert llm.media_attachments[0].ref == "weave:///e/p/object/content:done"

    def test_uploads_run_in_parallel(self) -> None:
        """Each attach_media gets its own thread; uploads overlap."""
        n = 4
        # A barrier of size n only releases once all n workers reach it, so
        # it can never fill if uploads ran serially on one thread.
        barrier = threading.Barrier(n, timeout=5)
        worker_threads: list[int] = []

        def publish(**kwargs: object) -> str:
            worker_threads.append(threading.get_ident())
            barrier.wait()
            return "weave:///e/p/object/content:v1"

        with patch(
            "weave.conversation.conversation._publish_media_content",
            side_effect=publish,
        ):
            llm = LLM(model="gpt-4o")
            for _ in range(n):
                llm.attach_media(content=b"x", mime_type="image/png")
            llm._await_uploads()

        assert len(llm.media_attachments) == n
        main_ident = threading.get_ident()
        assert all(ident != main_ident for ident in worker_threads)
        assert len(set(worker_threads)) == n  # one distinct thread per upload

    @pytest.mark.disable_logging_error_check
    def test_failed_upload_is_dropped(self) -> None:
        """An upload that raises is logged and its attachment removed."""

        def boom(**kwargs: object) -> str:
            raise RuntimeError("upload failed")

        with patch(
            "weave.conversation.conversation._publish_media_content",
            side_effect=boom,
        ):
            llm = LLM(model="gpt-4o")
            llm.attach_media(content=b"x", mime_type="image/png")
            llm._await_uploads()

        assert llm.media_attachments == []

    def test_end_awaits_uploads(self) -> None:
        """Refs are populated by the time the span is built at end()."""
        with patch(
            "weave.conversation.conversation._publish_media_content",
            side_effect=_fake_publish_media_content,
        ):
            llm = LLM(model="gpt-4o")
            llm.attach_media(content=b"x", mime_type="image/png")
            llm.end()
            assert llm.media_attachments[0].ref.startswith("weave:///")


class TestSubAgent:
    def test_defaults(self) -> None:
        sa = SubAgent(name="research-bot")
        assert sa.name == "research-bot"
        assert sa.model == ""

    def test_llm_returns_llm_and_inherits_model(self) -> None:
        sa = SubAgent(name="research-bot", model="gpt-4o-mini")
        c = sa.llm(model="gpt-4o-mini")
        assert isinstance(c, LLM)
        assert c.model == "gpt-4o-mini"
        # inherits model when not specified
        c2 = sa.llm()
        assert c2.model == "gpt-4o-mini"

    def test_tool_returns_tool(self) -> None:
        sa = SubAgent(name="bot")
        t = sa.tool(name="web_search", arguments='{"q":"X"}', tool_call_id="tc_2")
        assert isinstance(t, Tool)
        assert t.name == "web_search"

    def test_context_manager_sets_timestamps(self) -> None:
        with SubAgent(name="bot") as sa:
            assert sa.started_at is not None
        assert sa.ended_at is not None

    def test_subagent_with_nested_tools(self) -> None:
        with Turn(agent_name="bot") as turn:
            with turn.subagent(name="sub") as sa:
                with sa.tool(name="tool1", arguments='{"x":1}') as t1:
                    t1.result = "result1"
                with sa.tool(name="tool2", arguments='{"x":2}') as t2:
                    t2.result = "result2"
        assert t1.result == "result1"
        assert t1.duration_ms >= 0
        assert t2.result == "result2"
        assert sa.ended_at is not None


# ---------------------------------------------------------------------------
# Turn and Conversation
# ---------------------------------------------------------------------------


class TestTurn:
    def test_defaults(self) -> None:
        t = Turn(agent_name="weather-bot")
        assert t.agent_name == "weather-bot"
        assert t.model == ""
        assert t.messages == []

    def test_user_appends_message_and_returns_self(self) -> None:
        t = Turn()
        result = t.user("Hello")
        assert result is t
        assert len(t.messages) == 1
        assert t.messages[0].role == "user"
        assert t.messages[0].content == "Hello"

    def test_llm_returns_llm_and_inherits_model(self) -> None:
        t = Turn(model="gpt-4o")
        c = t.llm(
            model="gpt-4o",
            provider_name="openai",
            system_instructions=["Be helpful"],
        )
        assert isinstance(c, LLM)
        assert c.model == "gpt-4o"
        assert c.provider_name == "openai"
        assert c.system_instructions == ["Be helpful"]
        # inherits model when not specified
        c2 = t.llm()
        assert c2.model == "gpt-4o"

    def test_tool_returns_tool(self) -> None:
        t = Turn()
        tool = t.tool(
            name="get_weather", arguments='{"city":"Tokyo"}', tool_call_id="tc_1"
        )
        assert isinstance(tool, Tool)
        assert tool.name == "get_weather"
        assert tool.tool_call_id == "tc_1"

    def test_subagent_returns_subagent_and_inherits_model(self) -> None:
        t = Turn(model="gpt-4o")
        sa = t.subagent(name="research-bot", model="gpt-4o-mini")
        assert isinstance(sa, SubAgent)
        assert sa.name == "research-bot"
        assert sa.model == "gpt-4o-mini"
        # inherits model when not specified
        sa2 = t.subagent(name="bot")
        assert sa2.model == "gpt-4o"

    def test_context_manager_sets_timestamps(self) -> None:
        with Turn() as t:
            assert t.started_at is not None
        assert t.ended_at is not None


class TestConversation:
    def test_auto_generates_conversation_id(self) -> None:
        s = Conversation()
        assert s.conversation_id != ""
        assert len(s.conversation_id) == 36  # UUID format

    def test_explicit_conversation_id(self) -> None:
        s = Conversation(conversation_id="my-conversation-123")
        assert s.conversation_id == "my-conversation-123"

    def test_include_content_default_true(self) -> None:
        s = Conversation()
        assert s.include_content is True

    def test_include_content_false(self) -> None:
        s = Conversation(include_content=False)
        assert s.include_content is False

    def test_start_turn_returns_turn(self) -> None:
        s = Conversation(agent_name="weather-bot", model="gpt-4o")
        t = s.start_turn(user_message="What's the weather?")
        assert isinstance(t, Turn)
        assert t.agent_name == "weather-bot"
        assert t.model == "gpt-4o"
        assert len(t.messages) == 1
        assert t.messages[0].role == "user"
        assert t.messages[0].content == "What's the weather?"

    def test_start_turn_inherits_and_overrides_agent_name(self) -> None:
        s = Conversation(agent_name="weather-bot")
        t = s.start_turn()
        assert t.agent_name == "weather-bot"
        t2 = s.start_turn(agent_name="custom-bot")
        assert t2.agent_name == "custom-bot"

    def test_start_turn_no_user_message(self) -> None:
        s = Conversation()
        t = s.start_turn()
        assert t.messages == []

    def test_start_turn_auto_ends_previous(self) -> None:
        s = Conversation()
        t1 = s.start_turn()
        t2 = s.start_turn()
        assert t1._ended is True
        assert t2._ended is False

    def test_context_manager(self) -> None:
        with Conversation(agent_name="bot") as s:
            assert s.conversation_id != ""


# ---------------------------------------------------------------------------
# Contextvars and top-level functions
# ---------------------------------------------------------------------------


class TestContextVars:
    """Test contextvar-based cross-module tracing."""

    def test_start_conversation_sets_contextvar(self) -> None:
        s = start_conversation(agent_name="bot")
        try:
            assert get_current_conversation() is s
        finally:
            s.end()
        assert get_current_conversation() is None

    def test_conversation_context_manager_sets_contextvar(self) -> None:
        with Conversation(agent_name="bot") as s:
            assert get_current_conversation() is s
        assert get_current_conversation() is None

    def test_start_turn_sets_contextvar(self) -> None:
        s = start_conversation(agent_name="bot")
        try:
            t = start_turn(user_message="hi")
            assert get_current_turn() is t
            assert len(t.messages) == 1
            assert t.messages[0].content == "hi"
            assert t.agent_name == "bot"  # inherited from conversation
            t.end()
            assert get_current_turn() is None
        finally:
            s.end()

    def test_start_turn_without_conversation_returns_disconnected(self) -> None:
        t = start_turn(user_message="hi", agent_name="standalone")
        assert t.agent_name == "standalone"
        assert t.messages[0].content == "hi"
        assert get_current_turn() is None  # not set in contextvar

    def test_start_llm_sets_contextvar(self) -> None:
        s = start_conversation(agent_name="bot")
        try:
            t = start_turn()
            try:
                c = start_llm(model="gpt-4o")
                assert get_current_llm() is c
                assert c.model == "gpt-4o"
                c.end()
                assert get_current_llm() is None
            finally:
                t.end()
        finally:
            s.end()

    def test_start_llm_without_turn_returns_disconnected(self) -> None:
        c = start_llm(model="gpt-4o")
        assert c.model == "gpt-4o"
        assert get_current_llm() is None  # not set in contextvar

    def test_end_convenience_functions(self) -> None:
        s = start_conversation()
        start_turn()
        start_llm(model="gpt-4o")
        end_llm()
        assert get_current_llm() is None
        end_turn()
        assert get_current_turn() is None
        end_conversation()
        assert get_current_conversation() is None

    def test_end_when_nothing_active(self) -> None:
        # Should not raise
        end_llm()
        end_turn()
        end_conversation()

    def test_full_context_manager_pattern(self) -> None:
        with start_conversation(agent_name="weather-bot") as s:
            with s.start_turn(user_message="What's the weather?") as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("Let me check.")
                    llm.usage = Usage(input_tokens=100, output_tokens=50)
                with turn.tool(
                    name="get_weather",
                    arguments='{"city":"Tokyo"}',
                    tool_call_id="tc_1",
                ) as tool:
                    tool.result = "75F"
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("It's 75F in Tokyo!")

        assert get_current_conversation() is None
        assert get_current_turn() is None
        assert get_current_llm() is None

    def test_start_tool_returns_tool(self) -> None:
        t = start_tool(name="search", arguments='{"q":"test"}', tool_call_id="tc_1")
        assert isinstance(t, Tool)
        assert t.name == "search"
        assert t.arguments == '{"q":"test"}'
        assert t.tool_call_id == "tc_1"

    def test_start_tool_context_manager(self) -> None:
        with start_tool(name="get_weather", arguments='{"city":"Tokyo"}') as t:
            t.result = "75F"
        assert t.result == "75F"
        assert t.duration_ms >= 0
