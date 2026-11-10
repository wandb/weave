from __future__ import annotations

from typing import Any

from openai.types.chat import ChatCompletionChunk

from weave.integrations.openai.openai_sdk import openai_accumulator


def _chunk(
    delta: dict[str, Any], finish_reason: str | None = None
) -> ChatCompletionChunk:
    # The openai client builds streamed chunks without validating them, so a tool
    # call delta the server sent without an index has `index=None`.
    return ChatCompletionChunk.construct(
        id="chatcmpl-1",
        object="chat.completion.chunk",
        created=1,
        model="gpt-5.6-terra",
        choices=[
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
                "logprobs": None,
            }
        ],
    )


def _accumulate(chunks: list[ChatCompletionChunk]) -> Any:
    acc = None
    for chunk in chunks:
        acc = openai_accumulator(acc, chunk)
    return acc


def _tool_call(index: int | None, **fields: Any) -> dict[str, Any]:
    return {"index": index, **fields}


def _call(id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def _tool_calls(acc: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": tc.id,
            "type": tc.type,
            "name": tc.function.name,
            "arguments": tc.function.arguments,
        }
        for tc in acc.choices[0].delta.tool_calls
    ]


def test_parallel_tool_calls_in_one_chunk_are_all_kept() -> None:
    acc = _accumulate(
        [
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(0, **_call("call_paris", "get_weather", "")),
                        _tool_call(1, **_call("call_london", "get_weather", "")),
                    ]
                }
            ),
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(0, function={"arguments": '{"city": "Paris"}'}),
                        _tool_call(1, function={"arguments": '{"city": "London"}'}),
                    ]
                }
            ),
            _chunk({}, finish_reason="tool_calls"),
        ]
    )

    assert _tool_calls(acc) == [
        {
            "id": "call_paris",
            "type": "function",
            "name": "get_weather",
            "arguments": '{"city": "Paris"}',
        },
        {
            "id": "call_london",
            "type": "function",
            "name": "get_weather",
            "arguments": '{"city": "London"}',
        },
    ]


def test_arguments_of_the_first_tool_call_delta_are_kept() -> None:
    acc = _accumulate(
        [
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(
                            0, **_call("call_paris", "get_weather", '{"city": "Pa')
                        ),
                    ]
                }
            ),
            _chunk({"tool_calls": [_tool_call(0, function={"arguments": 'ris"}'})]}),
        ]
    )

    assert _tool_calls(acc) == [
        {
            "id": "call_paris",
            "type": "function",
            "name": "get_weather",
            "arguments": '{"city": "Paris"}',
        }
    ]


def test_whole_tool_calls_without_index_stay_apart() -> None:
    acc = _accumulate(
        [
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(
                            None,
                            **_call("call_paris", "get_weather", '{"city": "Paris"}'),
                        )
                    ]
                }
            ),
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(
                            None,
                            **_call("call_london", "get_weather", '{"city": "London"}'),
                        )
                    ]
                }
            ),
            _chunk({}, finish_reason="tool_calls"),
        ]
    )

    assert _tool_calls(acc) == [
        {
            "id": "call_paris",
            "type": "function",
            "name": "get_weather",
            "arguments": '{"city": "Paris"}',
        },
        {
            "id": "call_london",
            "type": "function",
            "name": "get_weather",
            "arguments": '{"city": "London"}',
        },
    ]


def test_whole_tool_calls_without_index_or_id_stay_apart() -> None:
    acc = _accumulate(
        [
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(
                            None,
                            function={
                                "name": "get_weather",
                                "arguments": '{"city": "Paris"}',
                            },
                        )
                    ]
                }
            ),
            _chunk(
                {
                    "tool_calls": [
                        _tool_call(
                            None,
                            function={
                                "name": "get_weather",
                                "arguments": '{"city": "London"}',
                            },
                        )
                    ]
                }
            ),
            _chunk({}, finish_reason="tool_calls"),
        ]
    )

    assert _tool_calls(acc) == [
        {
            "id": None,
            "type": None,
            "name": "get_weather",
            "arguments": '{"city": "Paris"}',
        },
        {
            "id": None,
            "type": None,
            "name": "get_weather",
            "arguments": '{"city": "London"}',
        },
    ]
