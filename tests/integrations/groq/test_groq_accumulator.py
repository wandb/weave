from __future__ import annotations

from typing import Any

from groq.types.chat import ChatCompletionChunk

from weave.integrations.groq.groq_sdk import groq_accumulator

USAGE = {
    "id": "req_1",
    "usage": {
        "completion_tokens": 20,
        "prompt_tokens": 50,
        "total_tokens": 70,
        "completion_time": 0.1,
        "prompt_time": 0.1,
        "queue_time": 0.0,
        "total_time": 0.2,
    },
}


def _chunk(
    delta: dict[str, Any],
    finish_reason: str | None = None,
    x_groq: dict[str, Any] | None = None,
) -> ChatCompletionChunk:
    data: dict[str, Any] = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
                "logprobs": None,
            }
        ],
    }
    if x_groq is not None:
        data["x_groq"] = x_groq
    return ChatCompletionChunk.model_validate(data)


def _accumulate(chunks: list[ChatCompletionChunk]) -> Any:
    acc = None
    for chunk in chunks:
        acc = groq_accumulator(acc, chunk)
    return acc


def _tool_call(index: int, **fields: Any) -> dict[str, Any]:
    return {"index": index, **fields}


def test_accumulator_keeps_reasoning_tool_calls_and_finish_reason() -> None:
    acc = _accumulate(
        [
            _chunk({"role": "assistant", "content": ""}),
            _chunk({"reasoning": "User wants "}),
            _chunk({"reasoning": "the weather."}),
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(
                            0,
                            id="call_1",
                            type="function",
                            function={"name": "get_weather", "arguments": '{"ci'},
                        )
                    ]
                }
            ),
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(0, function={"arguments": 'ty": "Paris"}'}),
                        _tool_call(
                            1,
                            id="call_2",
                            type="function",
                            function={"name": "get_time", "arguments": "{}"},
                        ),
                    ]
                }
            ),
            _chunk({}, finish_reason="tool_calls", x_groq=USAGE),
        ]
    )

    choice = acc.choices[0]
    assert choice.finish_reason == "tool_calls"
    assert choice.message.model_dump(exclude_none=True) == {
        "role": "assistant",
        "content": "",
        "reasoning": "User wants the weather.",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "get_time", "arguments": "{}"},
            },
        ],
    }
    assert acc.usage.total_tokens == 70


def test_accumulator_tool_call_in_first_chunk() -> None:
    acc = _accumulate(
        [
            _chunk(
                {
                    "role": "assistant",
                    "tool_calls": [
                        _tool_call(
                            0,
                            id="call_1",
                            type="function",
                            function={
                                "name": "get_weather",
                                "arguments": '{"city": "Paris"}',
                            },
                        )
                    ],
                }
            ),
            _chunk({}, finish_reason="tool_calls", x_groq=USAGE),
        ]
    )

    choice = acc.choices[0]
    assert choice.finish_reason == "tool_calls"
    assert choice.message.model_dump(exclude_none=True) == {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
            }
        ],
    }


def test_accumulator_text_stream() -> None:
    acc = _accumulate(
        [
            _chunk({"role": "assistant", "content": ""}),
            _chunk({"content": "Hello"}),
            _chunk({"content": " there"}),
            _chunk({}, finish_reason="length", x_groq=USAGE),
        ]
    )

    choice = acc.choices[0]
    assert choice.finish_reason == "length"
    assert choice.message.model_dump(exclude_none=True) == {
        "role": "assistant",
        "content": "Hello there",
    }
    assert acc.usage.model_dump(exclude_none=True) == USAGE["usage"]
