from __future__ import annotations

from functools import reduce

import pytest

pytest.importorskip("cohere")

from cohere.types import (
    ChatContentDeltaEventDelta,
    ChatContentDeltaEventDeltaMessage,
    ChatContentDeltaEventDeltaMessageContent,
    ChatContentStartEventDelta,
    ChatContentStartEventDeltaMessage,
    ChatContentStartEventDeltaMessageContent,
    ChatMessageEndEventDelta,
    ChatToolCallDeltaEventDelta,
    ChatToolCallDeltaEventDeltaMessage,
    ChatToolCallDeltaEventDeltaMessageToolCalls,
    ChatToolCallDeltaEventDeltaMessageToolCallsFunction,
    ChatToolCallStartEventDelta,
    ChatToolCallStartEventDeltaMessage,
    ChatToolPlanDeltaEventDelta,
    ChatToolPlanDeltaEventDeltaMessage,
    ToolCallV2,
    ToolCallV2Function,
    Usage,
)
from cohere.v2.types import (
    ContentDeltaV2ChatStreamResponse,
    ContentStartV2ChatStreamResponse,
    MessageEndV2ChatStreamResponse,
    ToolCallDeltaV2ChatStreamResponse,
    ToolCallEndV2ChatStreamResponse,
    ToolCallStartV2ChatStreamResponse,
    ToolPlanDeltaV2ChatStreamResponse,
)

from weave.integrations.cohere.cohere_sdk import cohere_accumulator_v2


def _tool_plan(text: str) -> ToolPlanDeltaV2ChatStreamResponse:
    return ToolPlanDeltaV2ChatStreamResponse(
        delta=ChatToolPlanDeltaEventDelta(
            message=ChatToolPlanDeltaEventDeltaMessage(tool_plan=text)
        )
    )


def _tool_call_start(
    index: int, call_id: str, name: str
) -> ToolCallStartV2ChatStreamResponse:
    return ToolCallStartV2ChatStreamResponse(
        index=index,
        delta=ChatToolCallStartEventDelta(
            message=ChatToolCallStartEventDeltaMessage(
                tool_calls=ToolCallV2(
                    id=call_id,
                    type="function",
                    function=ToolCallV2Function(name=name, arguments=""),
                )
            )
        ),
    )


def _tool_call_delta(index: int, arguments: str) -> ToolCallDeltaV2ChatStreamResponse:
    return ToolCallDeltaV2ChatStreamResponse(
        index=index,
        delta=ChatToolCallDeltaEventDelta(
            message=ChatToolCallDeltaEventDeltaMessage(
                tool_calls=ChatToolCallDeltaEventDeltaMessageToolCalls(
                    function=ChatToolCallDeltaEventDeltaMessageToolCallsFunction(
                        arguments=arguments
                    )
                )
            )
        ),
    )


def _accumulate(events: list) -> object:
    return reduce(cohere_accumulator_v2, events, None)


def test_streamed_tool_calls_are_kept() -> None:
    events = [
        _tool_plan("I will look up "),
        _tool_plan("both cities."),
        _tool_call_start(0, "call_0", "get_weather"),
        _tool_call_delta(0, '{"city":'),
        _tool_call_delta(0, '"Paris"}'),
        ToolCallEndV2ChatStreamResponse(index=0),
        _tool_call_start(1, "call_1", "get_weather"),
        _tool_call_delta(1, '{"city":"Rome"}'),
        ToolCallEndV2ChatStreamResponse(index=1),
        MessageEndV2ChatStreamResponse(
            delta=ChatMessageEndEventDelta(
                finish_reason="TOOL_CALL",
                usage=Usage(),
            )
        ),
    ]

    acc = _accumulate(events)

    assert acc.message.tool_plan == "I will look up both cities."
    assert acc.finish_reason == "TOOL_CALL"
    calls = acc.message.tool_calls
    assert calls is not None
    assert [(c.id, c.function.name, c.function.arguments) for c in calls] == [
        ("call_0", "get_weather", '{"city":"Paris"}'),
        ("call_1", "get_weather", '{"city":"Rome"}'),
    ]


def test_text_stream_is_unchanged() -> None:
    events = [
        ContentStartV2ChatStreamResponse(
            index=0,
            delta=ChatContentStartEventDelta(
                message=ChatContentStartEventDeltaMessage(
                    content=ChatContentStartEventDeltaMessageContent(
                        text="", type="text"
                    )
                )
            ),
        ),
        ContentDeltaV2ChatStreamResponse(
            index=0,
            delta=ChatContentDeltaEventDelta(
                message=ChatContentDeltaEventDeltaMessage(
                    content=ChatContentDeltaEventDeltaMessageContent(text="Hello")
                )
            ),
        ),
    ]

    acc = _accumulate(events)

    assert acc.message.content[0].text == "Hello"
    assert acc.message.tool_calls is None
    assert acc.message.tool_plan is None
