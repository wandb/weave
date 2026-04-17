"""Unit tests for genai_structured_ingest.py, genai_ingest_atif.py, and
genai_ingest_openhands.py — the structured conversation ingest pipeline.

Tests verify that structured conversation data is correctly converted to
GenAISpanCHInsertable rows that will render properly through the existing
build_chat_messages pipeline.
"""

from weave.trace_server.genai_chat_view import build_chat_messages, build_trace_chat
from weave.trace_server.genai_ingest_atif import atif_to_conversation_req
from weave.trace_server.genai_ingest_openhands import openhands_to_conversation_req
from weave.trace_server.genai_structured_ingest import (
    build_conversation_ingest_response,
    structured_turns_to_spans,
)
from weave.trace_server.trace_server_interface import (
    ATIFAgent,
    ATIFMetrics,
    ATIFObservation,
    ATIFObservationResult,
    ATIFStep,
    ATIFTrajectory,
    GenAIATIFIngestReq,
    GenAIConversationIngestReq,
    GenAIOpenHandsIngestReq,
    GenAISpanSchema,
    GenAIStructuredMessage,
    GenAIStructuredToolCall,
    GenAIStructuredTurn,
    OpenHandsEvent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spans_to_schema(spans):
    """Convert GenAISpanCHInsertable rows to GenAISpanSchema for chat view."""
    result = []
    for s in spans:
        d = s.model_dump()
        d["input_messages"] = [m.model_dump() for m in s.input_messages]
        d["output_messages"] = [m.model_dump() for m in s.output_messages]
        result.append(GenAISpanSchema(**d))
    return result


# ---------------------------------------------------------------------------
# Native structured ingest
# ---------------------------------------------------------------------------


class TestStructuredTurnsToSpans:
    """Test conversion of native structured turns to spans."""

    def test_single_turn_basic(self):
        req = GenAIConversationIngestReq(
            project_id="proj1",
            conversation_name="Test Chat",
            agent_name="my-agent",
            provider_name="openai",
            turns=[
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(role="user", content="Hello!"),
                        GenAIStructuredMessage(
                            role="assistant", content="Hi there!"
                        ),
                    ],
                    model="gpt-4",
                    input_tokens=10,
                    output_tokens=20,
                )
            ],
        )

        conv_id, trace_ids, spans = structured_turns_to_spans(req)

        assert conv_id  # auto-generated
        assert len(trace_ids) == 1
        assert len(spans) == 1

        root = spans[0]
        assert root.operation_name == "invoke_agent"
        assert root.agent_name == "my-agent"
        assert root.provider_name == "openai"
        assert root.request_model == "gpt-4"
        assert root.conversation_id == conv_id
        assert root.conversation_name == "Test Chat"
        assert root.input_tokens == 10
        assert root.output_tokens == 20
        assert root.total_tokens == 30
        assert len(root.input_messages) == 1
        assert root.input_messages[0].role == "user"
        assert root.input_messages[0].content == "Hello!"
        assert len(root.output_messages) == 1
        assert root.output_messages[0].role == "assistant"

    def test_turn_with_tool_calls(self):
        req = GenAIConversationIngestReq(
            project_id="proj1",
            agent_name="agent",
            turns=[
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(role="user", content="Search for cats"),
                        GenAIStructuredMessage(
                            role="assistant", content="Found 5 cats."
                        ),
                    ],
                    tool_calls=[
                        GenAIStructuredToolCall(
                            tool_name="web_search",
                            arguments='{"query": "cats"}',
                            result="5 results about cats",
                            duration_ms=100,
                        ),
                    ],
                )
            ],
        )

        conv_id, trace_ids, spans = structured_turns_to_spans(req)

        assert len(spans) == 2
        root = spans[0]
        tool_span = spans[1]

        assert root.operation_name == "invoke_agent"
        assert tool_span.operation_name == "execute_tool"
        assert tool_span.parent_span_id == root.span_id
        assert tool_span.trace_id == root.trace_id
        assert tool_span.tool_name == "web_search"
        assert tool_span.tool_call_arguments == '{"query": "cats"}'
        assert tool_span.tool_call_result == "5 results about cats"

    def test_multi_turn_conversation(self):
        req = GenAIConversationIngestReq(
            project_id="proj1",
            conversation_id="conv-123",
            turns=[
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(role="user", content="Hi"),
                        GenAIStructuredMessage(role="assistant", content="Hello!"),
                    ],
                ),
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(role="user", content="How are you?"),
                        GenAIStructuredMessage(
                            role="assistant", content="I'm good!"
                        ),
                    ],
                ),
            ],
        )

        conv_id, trace_ids, spans = structured_turns_to_spans(req)

        assert conv_id == "conv-123"
        assert len(trace_ids) == 2
        assert trace_ids[0] != trace_ids[1]
        assert len(spans) == 2

        for span in spans:
            assert span.conversation_id == "conv-123"

        assert spans[0].trace_id == trace_ids[0]
        assert spans[1].trace_id == trace_ids[1]

    def test_system_messages_become_instructions(self):
        req = GenAIConversationIngestReq(
            project_id="proj1",
            turns=[
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(
                            role="system", content="You are helpful."
                        ),
                        GenAIStructuredMessage(role="user", content="Hi"),
                        GenAIStructuredMessage(role="assistant", content="Hello!"),
                    ],
                    system_instructions=["Be concise."],
                )
            ],
        )

        _, _, spans = structured_turns_to_spans(req)
        root = spans[0]

        assert "You are helpful." in root.system_instructions
        assert "Be concise." in root.system_instructions
        assert len(root.input_messages) == 1
        assert root.input_messages[0].role == "user"

    def test_explicit_ids_preserved(self):
        req = GenAIConversationIngestReq(
            project_id="proj1",
            conversation_id="my-conv",
            turns=[
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(role="user", content="Hi"),
                    ],
                    trace_id="my-trace",
                )
            ],
        )

        conv_id, trace_ids, spans = structured_turns_to_spans(req)

        assert conv_id == "my-conv"
        assert trace_ids[0] == "my-trace"
        assert spans[0].trace_id == "my-trace"

    def test_response_builder(self):
        conv_id = "c1"
        trace_ids = ["t1", "t2"]
        spans = [None, None, None]  # type: ignore[list-item]

        res = build_conversation_ingest_response(conv_id, trace_ids, spans)
        assert res.conversation_id == "c1"
        assert res.trace_ids == ["t1", "t2"]
        assert res.span_count == 3


class TestStructuredIngestChatRendering:
    """Verify that spans from structured ingest render correctly through
    build_chat_messages (the same pipeline used by the OTel path).
    """

    def test_basic_turn_renders_user_and_agent(self):
        req = GenAIConversationIngestReq(
            project_id="proj1",
            agent_name="bot",
            turns=[
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(role="user", content="What is 2+2?"),
                        GenAIStructuredMessage(role="assistant", content="4"),
                    ],
                    model="gpt-4",
                )
            ],
        )

        _, trace_ids, spans = structured_turns_to_spans(req)
        schemas = _spans_to_schema(spans)
        chat = build_trace_chat(schemas, trace_ids[0])

        assert chat.trace_id == trace_ids[0]
        assert len(chat.messages) >= 2

        user_msgs = [m for m in chat.messages if m.type == "user_message"]
        agent_msgs = [m for m in chat.messages if m.type == "agent_message"]

        assert len(user_msgs) == 1
        assert user_msgs[0].text == "What is 2+2?"
        assert len(agent_msgs) == 1
        assert agent_msgs[0].text == "4"

    def test_tool_calls_render(self):
        req = GenAIConversationIngestReq(
            project_id="proj1",
            agent_name="agent",
            turns=[
                GenAIStructuredTurn(
                    messages=[
                        GenAIStructuredMessage(role="user", content="Search cats"),
                        GenAIStructuredMessage(
                            role="assistant", content="Found cats."
                        ),
                    ],
                    tool_calls=[
                        GenAIStructuredToolCall(
                            tool_name="search",
                            arguments='{"q":"cats"}',
                            result="cat results",
                        ),
                    ],
                )
            ],
        )

        _, trace_ids, spans = structured_turns_to_spans(req)
        schemas = _spans_to_schema(spans)
        msgs = build_chat_messages(schemas)

        tool_msgs = [m for m in msgs if m.type == "tool_call"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_name == "search"
        assert tool_msgs[0].tool_arguments == '{"q":"cats"}'
        assert tool_msgs[0].tool_result == "cat results"


# ---------------------------------------------------------------------------
# ATIF adapter
# ---------------------------------------------------------------------------


class TestATIFAdapter:
    """Test ATIF trajectory to native conversion."""

    def test_basic_trajectory(self):
        req = GenAIATIFIngestReq(
            project_id="proj1",
            provider_name="anthropic",
            trajectory=ATIFTrajectory(
                schema_version="ATIF-v1.4",
                session_id="session-abc",
                agent=ATIFAgent(
                    name="my-agent",
                    version="1.0",
                    model_name="claude-3.5-sonnet",
                ),
                steps=[
                    ATIFStep(
                        step_id=1,
                        source="user",
                        message="Hello agent!",
                    ),
                    ATIFStep(
                        step_id=2,
                        source="agent",
                        message="Hi! How can I help?",
                        metrics=ATIFMetrics(
                            prompt_tokens=100,
                            completion_tokens=50,
                        ),
                    ),
                ],
            ),
        )

        native = atif_to_conversation_req(req)

        assert native.project_id == "proj1"
        assert native.conversation_id == "session-abc"
        assert native.agent_name == "my-agent"
        assert native.provider_name == "anthropic"
        assert len(native.turns) == 1

        turn = native.turns[0]
        assert len(turn.messages) == 2
        assert turn.messages[0].role == "user"
        assert turn.messages[0].content == "Hello agent!"
        assert turn.messages[1].role == "assistant"
        assert turn.messages[1].content == "Hi! How can I help?"
        assert turn.input_tokens == 100
        assert turn.output_tokens == 50
        assert turn.model == "claude-3.5-sonnet"

    def test_multi_turn_trajectory(self):
        req = GenAIATIFIngestReq(
            project_id="proj1",
            trajectory=ATIFTrajectory(
                agent=ATIFAgent(name="bot"),
                steps=[
                    ATIFStep(step_id=1, source="user", message="First question"),
                    ATIFStep(step_id=2, source="agent", message="First answer"),
                    ATIFStep(step_id=3, source="user", message="Second question"),
                    ATIFStep(step_id=4, source="agent", message="Second answer"),
                ],
            ),
        )

        native = atif_to_conversation_req(req)
        assert len(native.turns) == 2

        assert native.turns[0].messages[0].content == "First question"
        assert native.turns[0].messages[1].content == "First answer"
        assert native.turns[1].messages[0].content == "Second question"
        assert native.turns[1].messages[1].content == "Second answer"

    def test_tool_calls_with_observations(self):
        req = GenAIATIFIngestReq(
            project_id="proj1",
            trajectory=ATIFTrajectory(
                agent=ATIFAgent(name="tool-agent"),
                steps=[
                    ATIFStep(step_id=1, source="user", message="Search for X"),
                    ATIFStep(
                        step_id=2,
                        source="agent",
                        message="I'll search for X.",
                        tool_calls=[
                            {
                                "tool_call_id": "call_1",
                                "function_name": "web_search",
                                "arguments": '{"query": "X"}',
                            }
                        ],
                        observation=ATIFObservation(
                            results=[
                                ATIFObservationResult(
                                    source_call_id="call_1",
                                    content="Found X at example.com",
                                )
                            ]
                        ),
                    ),
                ],
            ),
        )

        native = atif_to_conversation_req(req)
        assert len(native.turns) == 1

        turn = native.turns[0]
        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0].tool_name == "web_search"
        assert turn.tool_calls[0].arguments == '{"query": "X"}'
        assert turn.tool_calls[0].result == "Found X at example.com"

    def test_system_steps(self):
        req = GenAIATIFIngestReq(
            project_id="proj1",
            trajectory=ATIFTrajectory(
                agent=ATIFAgent(name="bot"),
                steps=[
                    ATIFStep(step_id=0, source="system", message="You are a helper."),
                    ATIFStep(step_id=1, source="user", message="Hi"),
                    ATIFStep(step_id=2, source="agent", message="Hello!"),
                ],
            ),
        )

        native = atif_to_conversation_req(req)
        assert len(native.turns) == 1
        assert "You are a helper." in native.turns[0].system_instructions

    def test_atif_end_to_end_renders(self):
        """Verify ATIF -> native -> spans -> chat messages works end-to-end."""
        req = GenAIATIFIngestReq(
            project_id="proj1",
            trajectory=ATIFTrajectory(
                session_id="s1",
                agent=ATIFAgent(name="bot", model_name="gpt-4"),
                steps=[
                    ATIFStep(step_id=1, source="user", message="What is AI?"),
                    ATIFStep(step_id=2, source="agent", message="AI is artificial intelligence."),
                ],
            ),
        )

        native = atif_to_conversation_req(req)
        conv_id, trace_ids, spans = structured_turns_to_spans(native)
        schemas = _spans_to_schema(spans)
        chat = build_trace_chat(schemas, trace_ids[0])

        user_msgs = [m for m in chat.messages if m.type == "user_message"]
        agent_msgs = [m for m in chat.messages if m.type == "agent_message"]

        assert len(user_msgs) == 1
        assert user_msgs[0].text == "What is AI?"
        assert len(agent_msgs) == 1
        assert agent_msgs[0].text == "AI is artificial intelligence."

    def test_reasoning_content_captured(self):
        req = GenAIATIFIngestReq(
            project_id="proj1",
            trajectory=ATIFTrajectory(
                agent=ATIFAgent(name="thinker"),
                steps=[
                    ATIFStep(step_id=1, source="user", message="Think about this"),
                    ATIFStep(
                        step_id=2,
                        source="agent",
                        message="Here's my answer.",
                        reasoning_content="Let me think step by step...",
                    ),
                ],
            ),
        )

        native = atif_to_conversation_req(req)
        assert native.turns[0].reasoning_content == "Let me think step by step..."


# ---------------------------------------------------------------------------
# OpenHands adapter
# ---------------------------------------------------------------------------


class TestOpenHandsAdapter:
    """Test OpenHands event stream to native conversion."""

    def test_basic_conversation(self):
        req = GenAIOpenHandsIngestReq(
            project_id="proj1",
            session_id="oh-session-1",
            agent_name="CodeActAgent",
            events=[
                OpenHandsEvent(
                    id=1,
                    source="user",
                    event_type="message",
                    content="Write a hello world program",
                ),
                OpenHandsEvent(
                    id=2,
                    source="agent",
                    event_type="message",
                    content="Here's a hello world program in Python.",
                ),
            ],
        )

        native = openhands_to_conversation_req(req)

        assert native.project_id == "proj1"
        assert native.conversation_id == "oh-session-1"
        assert native.agent_name == "CodeActAgent"
        assert len(native.turns) == 1

        turn = native.turns[0]
        assert len(turn.messages) == 2
        assert turn.messages[0].role == "user"
        assert turn.messages[0].content == "Write a hello world program"
        assert turn.messages[1].role == "assistant"

    def test_tool_calls_and_observations(self):
        req = GenAIOpenHandsIngestReq(
            project_id="proj1",
            session_id="oh-2",
            agent_name="agent",
            events=[
                OpenHandsEvent(
                    id=1,
                    source="user",
                    event_type="message",
                    content="Run ls",
                ),
                OpenHandsEvent(
                    id=2,
                    source="agent",
                    event_type="action",
                    tool_name="bash",
                    tool_call_id="tc_1",
                    arguments='{"command": "ls"}',
                ),
                OpenHandsEvent(
                    id=3,
                    source="environment",
                    event_type="observation",
                    tool_call_id="tc_1",
                    observation_content="file1.py file2.py",
                ),
                OpenHandsEvent(
                    id=4,
                    source="agent",
                    event_type="message",
                    content="The directory contains file1.py and file2.py.",
                ),
            ],
        )

        native = openhands_to_conversation_req(req)
        assert len(native.turns) == 1

        turn = native.turns[0]
        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0].tool_name == "bash"
        assert turn.tool_calls[0].result == "file1.py file2.py"

        user_msgs = [m for m in turn.messages if m.role == "user"]
        asst_msgs = [m for m in turn.messages if m.role == "assistant"]
        assert len(user_msgs) == 1
        assert len(asst_msgs) == 1

    def test_multi_turn_conversation(self):
        req = GenAIOpenHandsIngestReq(
            project_id="proj1",
            session_id="oh-3",
            events=[
                OpenHandsEvent(
                    id=1, source="user", event_type="message", content="First"
                ),
                OpenHandsEvent(
                    id=2, source="agent", event_type="message", content="Reply 1"
                ),
                OpenHandsEvent(
                    id=3, source="user", event_type="message", content="Second"
                ),
                OpenHandsEvent(
                    id=4, source="agent", event_type="message", content="Reply 2"
                ),
            ],
        )

        native = openhands_to_conversation_req(req)
        assert len(native.turns) == 2

        assert native.turns[0].messages[0].content == "First"
        assert native.turns[0].messages[1].content == "Reply 1"
        assert native.turns[1].messages[0].content == "Second"
        assert native.turns[1].messages[1].content == "Reply 2"

    def test_system_prompt_events(self):
        req = GenAIOpenHandsIngestReq(
            project_id="proj1",
            session_id="oh-4",
            events=[
                OpenHandsEvent(
                    id=0,
                    event_type="system_prompt",
                    system_prompt="You are a coding assistant.",
                ),
                OpenHandsEvent(
                    id=1, source="user", event_type="message", content="Hi"
                ),
                OpenHandsEvent(
                    id=2, source="agent", event_type="message", content="Hello!"
                ),
            ],
        )

        native = openhands_to_conversation_req(req)
        assert len(native.turns) == 1
        assert "You are a coding assistant." in native.turns[0].system_instructions

    def test_unmatched_observation_creates_standalone_tool_call(self):
        req = GenAIOpenHandsIngestReq(
            project_id="proj1",
            session_id="oh-5",
            events=[
                OpenHandsEvent(
                    id=1, source="user", event_type="message", content="Do something"
                ),
                OpenHandsEvent(
                    id=2,
                    source="environment",
                    event_type="observation",
                    tool_call_id="orphan",
                    observation_content="some output",
                ),
            ],
        )

        native = openhands_to_conversation_req(req)
        assert len(native.turns) == 1
        assert len(native.turns[0].tool_calls) == 1
        assert native.turns[0].tool_calls[0].result == "some output"

    def test_openhands_end_to_end_renders(self):
        """Verify OpenHands -> native -> spans -> chat messages works end-to-end."""
        req = GenAIOpenHandsIngestReq(
            project_id="proj1",
            session_id="oh-e2e",
            agent_name="CodeAct",
            events=[
                OpenHandsEvent(
                    id=1, source="user", event_type="message", content="Explain Python"
                ),
                OpenHandsEvent(
                    id=2,
                    source="agent",
                    event_type="message",
                    content="Python is a programming language.",
                ),
            ],
        )

        native = openhands_to_conversation_req(req)
        conv_id, trace_ids, spans = structured_turns_to_spans(native)
        schemas = _spans_to_schema(spans)
        chat = build_trace_chat(schemas, trace_ids[0])

        user_msgs = [m for m in chat.messages if m.type == "user_message"]
        agent_msgs = [m for m in chat.messages if m.type == "agent_message"]

        assert len(user_msgs) == 1
        assert user_msgs[0].text == "Explain Python"
        assert len(agent_msgs) == 1
        assert agent_msgs[0].text == "Python is a programming language."
