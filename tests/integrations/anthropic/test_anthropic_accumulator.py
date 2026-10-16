from __future__ import annotations

from typing import Any

import pytest
from anthropic.types import (
    InputJSONDelta,
    Message,
    MessageDeltaUsage,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    SignatureDelta,
    TextBlock,
    TextDelta,
    ThinkingBlock,
    ThinkingDelta,
    ToolUseBlock,
    Usage,
)
from anthropic.types.beta import (
    BetaInputJSONDelta,
    BetaMessage,
    BetaMessageDeltaUsage,
    BetaRawContentBlockDeltaEvent,
    BetaRawContentBlockStartEvent,
    BetaRawContentBlockStopEvent,
    BetaRawMessageDeltaEvent,
    BetaRawMessageStartEvent,
    BetaSignatureDelta,
    BetaTextBlock,
    BetaTextDelta,
    BetaThinkingBlock,
    BetaThinkingDelta,
    BetaToolUseBlock,
    BetaUsage,
)
from anthropic.types.beta.beta_raw_message_delta_event import Delta as BetaDelta
from anthropic.types.raw_message_delta_event import Delta

from weave.integrations.anthropic.anthropic_sdk import anthropic_accumulator

STANDARD = {
    "Message": Message,
    "Usage": Usage,
    "MessageDeltaUsage": MessageDeltaUsage,
    "Delta": Delta,
    "MessageStart": RawMessageStartEvent,
    "BlockStart": RawContentBlockStartEvent,
    "BlockDelta": RawContentBlockDeltaEvent,
    "BlockStop": RawContentBlockStopEvent,
    "MessageDelta": RawMessageDeltaEvent,
    "ThinkingBlock": ThinkingBlock,
    "TextBlock": TextBlock,
    "ToolUseBlock": ToolUseBlock,
    "ThinkingDelta": ThinkingDelta,
    "SignatureDelta": SignatureDelta,
    "TextDelta": TextDelta,
    "InputJSONDelta": InputJSONDelta,
}

BETA = {
    "Message": BetaMessage,
    "Usage": BetaUsage,
    "MessageDeltaUsage": BetaMessageDeltaUsage,
    "Delta": BetaDelta,
    "MessageStart": BetaRawMessageStartEvent,
    "BlockStart": BetaRawContentBlockStartEvent,
    "BlockDelta": BetaRawContentBlockDeltaEvent,
    "BlockStop": BetaRawContentBlockStopEvent,
    "MessageDelta": BetaRawMessageDeltaEvent,
    "ThinkingBlock": BetaThinkingBlock,
    "TextBlock": BetaTextBlock,
    "ToolUseBlock": BetaToolUseBlock,
    "ThinkingDelta": BetaThinkingDelta,
    "SignatureDelta": BetaSignatureDelta,
    "TextDelta": BetaTextDelta,
    "InputJSONDelta": BetaInputJSONDelta,
}


def _stream(t: dict[str, Any], blocks: list[tuple[Any, list[Any]]], stop_reason: str):
    start = t["Message"](
        id="msg_1",
        type="message",
        role="assistant",
        model="claude-sonnet-5",
        content=[],
        stop_reason=None,
        stop_sequence=None,
        usage=t["Usage"](input_tokens=10, output_tokens=0),
    )
    yield t["MessageStart"](type="message_start", message=start)
    for index, (block, deltas) in enumerate(blocks):
        yield t["BlockStart"](
            type="content_block_start", index=index, content_block=block
        )
        for delta in deltas:
            yield t["BlockDelta"](type="content_block_delta", index=index, delta=delta)
        yield t["BlockStop"](type="content_block_stop", index=index)
    yield t["MessageDelta"](
        type="message_delta",
        delta=t["Delta"](stop_reason=stop_reason, stop_sequence=None),
        usage=t["MessageDeltaUsage"](output_tokens=42),
    )


def _accumulate(events) -> Any:
    acc = None
    for event in events:
        acc = anthropic_accumulator(acc, event)
    return acc


@pytest.mark.parametrize("t", [STANDARD, BETA], ids=["messages", "beta.messages"])
def test_accumulator_keeps_thinking_text_and_tool_use_blocks(t: dict[str, Any]) -> None:
    events = _stream(
        t,
        [
            (
                t["ThinkingBlock"](type="thinking", thinking="", signature=""),
                [
                    t["ThinkingDelta"](type="thinking_delta", thinking="User wants "),
                    t["ThinkingDelta"](type="thinking_delta", thinking="weather."),
                    t["SignatureDelta"](type="signature_delta", signature="sig"),
                ],
            ),
            (
                t["TextBlock"](type="text", text=""),
                [t["TextDelta"](type="text_delta", text="Checking the weather.")],
            ),
            (
                t["ToolUseBlock"](
                    type="tool_use", id="toolu_1", name="get_weather", input={}
                ),
                [
                    t["InputJSONDelta"](type="input_json_delta", partial_json='{"ci'),
                    t["InputJSONDelta"](
                        type="input_json_delta", partial_json='ty": "Paris"}'
                    ),
                ],
            ),
        ],
        stop_reason="tool_use",
    )

    acc = _accumulate(events)

    assert acc.stop_reason == "tool_use"
    assert [block.model_dump(exclude_none=True) for block in acc.content] == [
        {"type": "thinking", "thinking": "User wants weather.", "signature": "sig"},
        {"type": "text", "text": "Checking the weather."},
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "get_weather",
            "input": {"city": "Paris"},
        },
    ]


def test_accumulator_tool_use_without_arguments_keeps_empty_input() -> None:
    events = _stream(
        STANDARD,
        [
            (
                ToolUseBlock(type="tool_use", id="toolu_1", name="get_time", input={}),
                [InputJSONDelta(type="input_json_delta", partial_json="")],
            )
        ],
        stop_reason="tool_use",
    )

    acc = _accumulate(events)

    assert [block.model_dump(exclude_none=True) for block in acc.content] == [
        {"type": "tool_use", "id": "toolu_1", "name": "get_time", "input": {}}
    ]


def test_accumulator_text_only_stream() -> None:
    events = _stream(
        STANDARD,
        [
            (
                TextBlock(type="text", text=""),
                [
                    TextDelta(type="text_delta", text="Hello"),
                    TextDelta(type="text_delta", text=" there"),
                ],
            )
        ],
        stop_reason="end_turn",
    )

    acc = _accumulate(events)

    assert acc.stop_reason == "end_turn"
    assert acc.usage.output_tokens == 42
    assert [block.model_dump(exclude_none=True) for block in acc.content] == [
        {"type": "text", "text": "Hello there"}
    ]
