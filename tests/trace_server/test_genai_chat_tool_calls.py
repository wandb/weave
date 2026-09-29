"""Tool requests survive chat projection independently of execution tracing."""

import datetime
import json

import pytest

from weave.trace_server.agents.chat_view import build_chat_messages
from weave.trace_server.agents.schema import NormalizedMessage, StatusCodeLiteral
from weave.trace_server.agents.types import (
    AgentChatToolCall,
    AgentConversationChatReq,
    AgentSpanSchema,
    AgentTraceChatReq,
)

START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
END = START + datetime.timedelta(seconds=1)
ARGUMENTS = {"message": "The report is ready."}


@pytest.mark.parametrize("execution_status", [None, "OK", "ERROR"])
@pytest.mark.parametrize("arguments", [ARGUMENTS, json.dumps(ARGUMENTS)])
def test_model_call_and_rendered_reply_preserve_execution_evidence(
    execution_status: StatusCodeLiteral | None, arguments: dict[str, str] | str
) -> None:
    call = {
        "type": "tool_call",
        "id": "call-1",
        "name": "publish_answer",
        "arguments": arguments,
    }
    root = _span("root", operation_name="invoke_agent")
    root.agent_name = "report-agent"
    root.output_messages = [
        NormalizedMessage(
            role="assistant",
            content=json.dumps(
                [
                    call,
                    {"type": "text", "content": ARGUMENTS["message"]},
                ]
            ),
        )
    ]
    model = _span("model", parent_span_id="root")
    model.output_messages = [
        NormalizedMessage(role="assistant", content=json.dumps([call]))
    ]
    spans = [root, model]
    expected = AgentChatToolCall(
        tool_name="publish_answer", tool_arguments=json.dumps(ARGUMENTS)
    )

    if execution_status is not None:
        tool = _span("execution", operation_name="execute_tool", parent_span_id="root")
        tool.tool_call_id = "call-1"
        tool.tool_name = "publish_answer"
        tool.tool_call_arguments = json.dumps(ARGUMENTS)
        tool.tool_call_result = "delivery receipt"
        tool.status_code = execution_status
        spans.append(tool)
        expected = AgentChatToolCall(
            tool_name="publish_answer",
            tool_arguments=json.dumps(ARGUMENTS),
            tool_result="delivery receipt",
            status=execution_status,
            duration_ms=1000,
        )

    messages = build_chat_messages(list(reversed(spans)), include_model_tool_calls=True)

    assert [message.type for message in messages] == [
        "agent_start",
        "tool_call",
        "assistant_message",
    ]
    assert messages[1].tool_call == expected
    assert messages[1].span_id == ("model" if execution_status is None else "execution")
    assert messages[1].status_code == execution_status
    assert messages[1].agent_name == "report-agent"
    assert messages[2].assistant_message is not None
    assert messages[2].assistant_message.text == ARGUMENTS["message"]


@pytest.mark.parametrize("operation_name", ["chat", "invoke_agent"])
@pytest.mark.parametrize("call_ids", [("first", "second"), ("", "")])
def test_distinct_requests_survive_without_replaying_inputs(
    operation_name: str, call_ids: tuple[str, str]
) -> None:
    model = _span("model", operation_name=operation_name)
    parts = [
        {"type": "tool_call", "id": call_id, "name": "lookup", "arguments": "{}"}
        for call_id in call_ids
    ]
    content = json.dumps(parts)
    model.input_messages = [NormalizedMessage(role="assistant", content=content)]
    model.output_messages = [NormalizedMessage(role="assistant", content=content)]
    model.status_code = "ERROR"
    unrelated = _span("other-trace", operation_name="execute_tool")
    unrelated.trace_id = "other"
    unrelated.tool_call_id = "first"

    messages = build_chat_messages([model, unrelated], include_model_tool_calls=True)
    requests = [
        message
        for message in messages
        if message.tool_call and message.span_id == "model"
    ]

    assert [message.tool_call for message in requests] == [
        AgentChatToolCall(tool_name="lookup", tool_arguments="{}"),
        AgentChatToolCall(tool_name="lookup", tool_arguments="{}"),
    ]
    assert [message.status_code for message in requests] == [None, None]
    assert [message.started_at for message in requests] == [END, END]


@pytest.mark.parametrize(
    "content",
    [
        "[broken JSON",
        "[]",
        '[null, 1, "text"]',
        '[{"type": "tool_call", "name": 42}]',
        '[{"type": "tool_call", "name": ""}]',
        '[{"type": "text", "content": "answer"}]',
    ],
)
def test_non_calls_do_not_create_tool_activity(content: str) -> None:
    model = _span("model")
    history = '[{"type":"tool_call","id":"old","name":"lookup"}]'
    model.input_messages = [NormalizedMessage(role="assistant", content=history)]
    model.output_messages = [
        NormalizedMessage(role="assistant", content=content),
        NormalizedMessage(role="tool", content=history),
    ]

    messages = build_chat_messages([model], include_model_tool_calls=True)

    assert [message.tool_call for message in messages if message.tool_call] == []


@pytest.mark.parametrize("request_type", [AgentTraceChatReq, AgentConversationChatReq])
def test_tool_call_option_is_public_and_defaults_to_false(
    request_type: type[AgentTraceChatReq] | type[AgentConversationChatReq],
) -> None:
    payload = {
        "project_id": "project",
        "trace_id": "trace",
        "conversation_id": "conversation",
    }
    assert request_type.model_validate(payload).include_model_tool_calls is False
    enabled = request_type.model_validate({**payload, "include_model_tool_calls": True})
    assert (
        request_type.model_validate_json(
            enabled.model_dump_json()
        ).include_model_tool_calls
        is True
    )
    for schema in (
        request_type.model_json_schema(mode="validation"),
        request_type.model_json_schema(mode="serialization"),
    ):
        assert schema["properties"]["include_model_tool_calls"] == {
            "title": "Include Model Tool Calls",
            "type": "boolean",
            "default": False,
            "description": (
                "Include tool calls requested in model outputs, even when no execution span "
                "was recorded. Requests without execution evidence have no status, duration, "
                "or result. Defaults to false."
            ),
        }
        assert "include_model_tool_calls" not in schema["required"]


def _span(
    span_id: str, *, operation_name: str = "chat", parent_span_id: str = ""
) -> AgentSpanSchema:
    return AgentSpanSchema(
        project_id="project",
        trace_id="trace",
        span_id=span_id,
        operation_name=operation_name,
        parent_span_id=parent_span_id,
        started_at=START,
        ended_at=END,
    )
