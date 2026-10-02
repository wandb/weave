"""Recorded tool dependencies take precedence over producer clocks."""

import datetime
import json

import pytest

from weave.trace_server.agents.chat_view import build_chat_messages
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import AgentChatToolCall, AgentSpanSchema

START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
pytestmark = pytest.mark.trace_server


@pytest.mark.parametrize(
    ("clock_offset", "later_at", "expected"),
    [
        (120, 4, ["execution", "reply", "later"]),
        (0, 4, ["execution", "reply", "later"]),
        (-120, 0.5, ["later", "execution", "reply"]),
    ],
)
def test_execution_follows_its_request_whatever_the_tool_clock(
    clock_offset: int, later_at: float, expected: list[str]
) -> None:
    request = _span("request", 1)
    request.output_messages = [_call("lookup-1", "lookup")]
    execution = _span("execution", 2 + clock_offset)
    execution.operation_name = "execute_tool"
    execution.tool_call_id = "lookup-1"
    execution.tool_name = "lookup"
    execution.tool_call_result = "found"
    execution.status_code = "OK"
    reply = _span("reply", 3)
    reply.input_messages = [_call("lookup-1", "lookup"), _result("lookup-1")]
    reply.output_messages = [_call("reply-1", "deliver")]
    later = _span("later", later_at)
    later.output_messages = [NormalizedMessage(role="assistant", content="Summary.")]

    messages = build_chat_messages(
        [request, execution, reply, later], include_model_tool_calls=True
    )

    assert [message.span_id for message in messages] == expected
    assert messages[expected.index("execution")].tool_call == AgentChatToolCall(
        tool_name="lookup", tool_result="found", duration_ms=1000, status="OK"
    )


@pytest.mark.parametrize("response_role", ["tool", "user"])
def test_later_input_completes_request_recorded_by_earlier_span(
    response_role: str,
) -> None:
    request = _span("request", 1)
    request.input_messages = [
        NormalizedMessage(role="user", content="Prepare the report.")
    ]
    request.output_messages = [_call("lookup-1", "lookup")]
    history = [
        *request.input_messages,
        _call("lookup-1", "lookup"),
        _result("lookup-1").model_copy(update={"role": response_role}),
    ]
    reply = _span("reply", 2)
    reply.input_messages = history
    reply.output_messages = [_call("deliver-1", "deliver")]
    final = _span("final", 3)
    final.input_messages = [*history, _call("deliver-1", "deliver")]
    final.output_messages = [NormalizedMessage(role="assistant", content="Done.")]

    messages = build_chat_messages(
        [final, reply, request], include_model_tool_calls=True
    )
    calls = [message for message in messages if message.tool_call]

    # A response proves the call returned, not that it succeeded: status stays unset.
    assert [(message.span_id, message.tool_call) for message in calls] == [
        (
            "request",
            AgentChatToolCall(
                tool_name="lookup", tool_arguments="{}", tool_result="found"
            ),
        ),
        ("reply", AgentChatToolCall(tool_name="deliver", tool_arguments="{}")),
    ]
    assert calls[0].started_at == request.ended_at
    assert [
        message.tool_call
        for message in build_chat_messages([final, reply, request])
        if message.tool_call
    ] == []


def test_unrelated_or_ambiguous_execution_keeps_clock_position() -> None:
    reply = _span("reply", 1)
    reply.input_messages = [_result("same-id")]
    reply.output_messages = [_call("same-id", "lookup")]
    retry = _span("retry", 2)
    retry.output_messages = [_call("dup-id", "lookup")]
    duplicate = _span("duplicate", 3)
    duplicate.output_messages = [_call("dup-id", "lookup")]
    unrelated = _span("unrelated", 120).model_copy(
        update={
            "trace_id": "unrelated",
            "operation_name": "execute_tool",
            "tool_call_id": "same-id",
            "tool_name": "lookup",
        }
    )
    ambiguous = _span("ambiguous", 121).model_copy(
        update={
            "operation_name": "execute_tool",
            "tool_call_id": "dup-id",
            "tool_name": "lookup",
        }
    )

    messages = build_chat_messages(
        [ambiguous, unrelated, duplicate, retry, reply], include_model_tool_calls=True
    )

    assert [message.span_id for message in messages if message.tool_call] == [
        "reply",
        "unrelated",
        "ambiguous",
    ]


def _span(span_id: str, seconds: float) -> AgentSpanSchema:
    return AgentSpanSchema(
        project_id="project",
        trace_id="trace",
        span_id=span_id,
        operation_name="chat",
        started_at=START + datetime.timedelta(seconds=seconds),
        ended_at=START + datetime.timedelta(seconds=seconds + 1),
    )


def _call(call_id: str, name: str) -> NormalizedMessage:
    return NormalizedMessage(
        role="assistant",
        content=json.dumps(
            [{"type": "tool_call", "id": call_id, "name": name, "arguments": "{}"}]
        ),
    )


def _result(call_id: str) -> NormalizedMessage:
    return NormalizedMessage(
        role="tool",
        content=json.dumps(
            [{"type": "tool_call_response", "id": call_id, "response": "found"}]
        ),
    )
