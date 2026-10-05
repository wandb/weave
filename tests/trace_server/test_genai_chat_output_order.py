"""Request-only events retain their position within model output."""

import json

import pytest

from weave.trace_server.agents.chat_view import build_chat_messages
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import AgentSpanSchema


@pytest.mark.parametrize("operation_name", ["chat", "invoke_agent"])
@pytest.mark.parametrize("content_type", ["text", "reasoning"])
@pytest.mark.parametrize(
    "order",
    [
        ("content", "tool"),
        ("tool", "content"),
        ("content", "tool", "content", "tool", "content"),
    ],
)
@pytest.mark.parametrize("separate_messages", [False, True])
def test_model_output_retains_source_order(
    operation_name: str,
    content_type: str,
    order: tuple[str, ...],
    separate_messages: bool,
) -> None:
    parts: list[dict[str, str]] = []
    expected: list[tuple[str, str]] = []
    reasoning: list[str] = []
    for index, kind in enumerate(order):
        value = f"part-{index}"
        if kind == "tool":
            parts.append({"type": "tool_call", "id": value, "name": value})
            expected.append(("tool_call", value))
        else:
            parts.append({"type": content_type, "content": value})
            expected.append(("assistant_message", value))
            if content_type == "reasoning":
                reasoning.append(value)

    outputs = (
        [
            NormalizedMessage(role="assistant", content=json.dumps([part]))
            for part in parts
        ]
        if separate_messages
        else [NormalizedMessage(role="assistant", content=json.dumps(parts))]
    )
    span = AgentSpanSchema(
        project_id="project",
        trace_id="trace",
        span_id="model",
        operation_name=operation_name,
        output_messages=outputs,
        reasoning_content="\n".join(reasoning) or None,
        input_tokens=10,
        output_tokens=20,
        reasoning_tokens=5,
        total_cost_usd=0.25,
    )

    baseline = build_chat_messages([span])
    assert baseline == build_chat_messages([span], include_model_tool_calls=False)
    assert [message.type for message in baseline] == ["assistant_message"]
    messages = build_chat_messages([span], include_model_tool_calls=True)
    actual: list[tuple[str, str | None]] = []
    for message in messages:
        if message.tool_call is not None:
            tool = message.tool_call
            actual.append((message.type, tool.tool_name))
            assert (tool.status, tool.duration_ms, tool.tool_result) == (
                None,
                None,
                None,
            )
        elif message.assistant_message is not None:
            assistant = message.assistant_message
            value = (
                assistant.text
                if content_type == "text"
                else assistant.reasoning_content
            )
            actual.append((message.type, value))
        else:
            raise AssertionError(f"Unexpected event: {message.type}")

    assert actual == expected
    assistants = [
        message.assistant_message for message in messages if message.assistant_message
    ]
    assert sum(item.input_tokens or 0 for item in assistants) == 10
    assert sum(item.output_tokens or 0 for item in assistants) == 20
    assert sum(item.reasoning_tokens or 0 for item in assistants) == 5
    assert sum(item.total_cost_usd or 0 for item in assistants) == 0.25

    executions = [
        AgentSpanSchema(
            project_id="project",
            trace_id="trace",
            span_id=part["id"],
            operation_name="execute_tool",
            tool_call_id=part["id"],
            tool_name=part["name"],
            status_code="OK",
        )
        for part in parts
        if part["type"] == "tool_call"
    ]
    recorded = [span, *executions]
    assert build_chat_messages(
        recorded, include_model_tool_calls=True
    ) == build_chat_messages(recorded)
