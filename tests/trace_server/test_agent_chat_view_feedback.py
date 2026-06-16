"""Integration tests for include_feedback fold-in on agent chat endpoints.

Runs against the ClickHouse backend (the only supported backend).
"""

import datetime
import uuid

from tests.trace_server.helpers import make_project_id as _make_project_id
from weave.shared import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.helpers import genai_span_to_row
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)
from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentTraceChatReq,
)


def test_agent_traces_chat_feedback_fold_in_and_opt_out(ch_server):
    """include_feedback=True folds turn + step reactions; the default leaves
    every feedback field None for the same underlying spans/reactions.
    """
    project_id = _make_project_id("feedback")
    trace_id = uuid.uuid4().hex
    root_span_id = uuid.uuid4().hex[:16]
    child_span_id = uuid.uuid4().hex[:16]

    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id, trace_id, root_span_id, operation_name="invoke_agent"
            ),
            _make_span(
                project_id,
                trace_id,
                child_span_id,
                parent_span_id=root_span_id,
                operation_name="execute_tool",
                tool_name="get_weather",
            ),
        ],
    )

    turn_ref = ri.InternalAgentTurnRef(project_id=project_id, trace_id=trace_id).uri
    step_ref = ri.InternalAgentSpanRef(project_id=project_id, span_id=child_span_id).uri
    _create_reaction(ch_server, project_id, turn_ref, "👍")
    _create_reaction(ch_server, project_id, step_ref, "🔥")

    res = ch_server.agent_traces_chat(
        AgentTraceChatReq(
            project_id=project_id, trace_id=trace_id, include_feedback=True
        )
    )

    assert res.feedback is not None
    assert len(res.feedback) == 1
    assert res.feedback[0]["payload"] == {"emoji": "👍"}

    step_msgs = [m for m in res.messages if m.span_id == child_span_id and m.feedback]
    assert len(step_msgs) == 1
    assert step_msgs[0].feedback is not None
    assert step_msgs[0].feedback[0]["payload"] == {"emoji": "🔥"}

    off = ch_server.agent_traces_chat(
        AgentTraceChatReq(project_id=project_id, trace_id=trace_id)
    )
    assert off.feedback is None
    for m in off.messages:
        assert m.feedback is None


def test_agent_conversation_chat_folds_conversation_turn_and_step_feedback(ch_server):
    project_id = _make_project_id("conv_feedback")
    conv_id = f"conv-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    root_span_id = uuid.uuid4().hex[:16]
    child_span_id = uuid.uuid4().hex[:16]

    _insert_spans(
        ch_server.ch_client,
        [
            _make_span(
                project_id,
                trace_id,
                root_span_id,
                operation_name="invoke_agent",
                conversation_id=conv_id,
            ),
            _make_span(
                project_id,
                trace_id,
                child_span_id,
                parent_span_id=root_span_id,
                operation_name="execute_tool",
                tool_name="get_weather",
                conversation_id=conv_id,
            ),
        ],
    )

    conv_ref = ri.InternalAgentConversationRef(
        project_id=project_id, conversation_id=conv_id
    ).uri
    turn_ref = ri.InternalAgentTurnRef(project_id=project_id, trace_id=trace_id).uri
    step_ref = ri.InternalAgentSpanRef(project_id=project_id, span_id=child_span_id).uri
    _create_reaction(ch_server, project_id, conv_ref, "💬")
    _create_reaction(ch_server, project_id, turn_ref, "👍")
    _create_reaction(ch_server, project_id, step_ref, "🔥")

    res = ch_server.agent_conversation_chat(
        AgentConversationChatReq(
            project_id=project_id, conversation_id=conv_id, include_feedback=True
        )
    )

    assert res.feedback is not None
    assert len(res.feedback) == 1
    assert res.feedback[0]["payload"] == {"emoji": "💬"}

    assert len(res.turns) == 1
    turn = res.turns[0]
    assert turn.feedback is not None
    assert len(turn.feedback) == 1
    assert turn.feedback[0]["payload"] == {"emoji": "👍"}

    step_msgs = [m for m in turn.messages if m.span_id == child_span_id and m.feedback]
    assert len(step_msgs) == 1
    assert step_msgs[0].feedback is not None
    assert step_msgs[0].feedback[0]["payload"] == {"emoji": "🔥"}


def _make_span(
    project_id: str,
    trace_id: str,
    span_id: str,
    **overrides: object,
) -> AgentSpanCHInsertable:
    defaults = {
        "project_id": project_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "span_name": "test-span",
        "started_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "ended_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "status_code": "OK",
        "operation_name": "invoke_agent",
        "agent_name": "test-agent",
        "provider_name": "openai",
        "request_model": "gpt-4o",
    }
    defaults.update(overrides)
    return AgentSpanCHInsertable(**defaults)


def _insert_spans(ch_client, spans: list[AgentSpanCHInsertable]) -> None:
    rows = [genai_span_to_row(s) for s in spans]
    ch_client.insert("spans", data=rows, column_names=ALL_SPAN_INSERT_COLUMNS)


def _create_reaction(ch_server, project_id: str, weave_ref: str, emoji: str) -> None:
    ch_server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type="reaction",
            payload={"emoji": emoji},
            wb_user_id="test-user",
        )
    )
