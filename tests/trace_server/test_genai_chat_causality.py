"""Recorded tool dependencies take precedence over producer clocks."""

import datetime
import json

import pytest

from weave.trace_server.agents.chat_view import build_chat_messages
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import AgentChatToolCall, AgentSpanSchema

START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
pytestmark = pytest.mark.trace_server


@pytest.mark.parametrize("clock_offset", [-120, 0, 120])
@pytest.mark.parametrize("reverse", [False, True])
def test_execution_precedes_model_that_consumed_its_result(
    clock_offset: int, reverse: bool
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
    spans = [request, execution, reply]
    if reverse:
        spans.reverse()

    messages = build_chat_messages(spans, include_model_tool_calls=True)
    calls = [message for message in messages if message.tool_call]

    assert [message.span_id for message in calls] == ["execution", "reply"]
    assert calls[0].tool_call == AgentChatToolCall(
        tool_name="lookup",
        tool_result="found",
        duration_ms=1000,
        status="OK",
    )
    assert calls[0].started_at == execution.started_at
    assert calls[1].tool_call == AgentChatToolCall(
        tool_name="deliver", tool_arguments="{}"
    )


@pytest.mark.parametrize("has_result", [False, True])
def test_continuation_retains_paired_history_without_claiming_success(
    has_result: bool,
) -> None:
    model = _span("continuation", 3)
    model.input_messages = [
        _call("old", "lookup"),
        _result("old"),
        NormalizedMessage(role="user", content="Prepare the report."),
        _call("current", "lookup"),
    ]
    if has_result:
        model.input_messages.append(_result("current"))
    model.output_messages = [_call("reply", "deliver")]

    messages = build_chat_messages([model], include_model_tool_calls=True)
    calls = [message.tool_call for message in messages if message.tool_call]

    expected = []
    if has_result:
        expected.append(
            AgentChatToolCall(
                tool_name="lookup", tool_arguments="{}", tool_result="found"
            )
        )
    expected.append(AgentChatToolCall(tool_name="deliver", tool_arguments="{}"))
    assert calls == expected
    assert [
        message.tool_call
        for message in build_chat_messages([model])
        if message.tool_call
    ] == []


@pytest.mark.parametrize("scope", ["project_id", "trace_id"])
def test_unrelated_execution_does_not_reorder_or_hide_request(scope: str) -> None:
    reply = _span("reply", 1)
    reply.input_messages = [_result("same-id")]
    reply.output_messages = [_call("same-id", "lookup")]
    execution = _span("execution", 120)
    execution.operation_name = "execute_tool"
    execution.tool_call_id = "same-id"
    execution.tool_name = "lookup"
    execution = execution.model_copy(update={scope: "unrelated"})

    messages = build_chat_messages([execution, reply], include_model_tool_calls=True)

    assert [message.span_id for message in messages if message.tool_call] == [
        "reply",
        "execution",
    ]


def test_repeated_names_and_conflicting_dependencies_preserve_evidence() -> None:
    first = _span("first", 1)
    first.output_messages = [_call("first-id", "lookup")]
    second = _span("second", 2)
    second.output_messages = [_call("second-id", "lookup")]
    second.input_messages = [_result("first-id")]
    final = _span("final", 3)
    final.input_messages = [_result("second-id")]
    final.output_messages = [_call("final-id", "deliver")]
    spans = [final, second, first]

    messages = build_chat_messages(spans, include_model_tool_calls=True)

    assert [message.span_id for message in messages if message.tool_call] == [
        "first",
        "second",
        "final",
    ]
    first.input_messages = [_result("final-id")]
    conflicted = build_chat_messages(spans, include_model_tool_calls=True)
    assert [message.span_id for message in conflicted if message.tool_call] == [
        "first",
        "second",
        "final",
    ]


def _span(span_id: str, seconds: int) -> AgentSpanSchema:
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
