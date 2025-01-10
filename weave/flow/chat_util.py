from collections.abc import Iterator
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletion,
        ChatCompletionChunk,
    )


class OpenAIStream:
    """
    A class that reconstructs a ChatCompletion from an OpenAI stream.

    Usage: initialize this class, iterate through all the chunks, then
    call final_response to get the final ChatCompletion.

    Args:
        chunk_iter: The output of an openai chat completion streaming=True call.
    """

    def __init__(self, chunk_iter: Iterator["ChatCompletionChunk"]) -> None:
        self.chunk_iter = chunk_iter
        self.first_chunk: Optional[ChatCompletionChunk] = None
        self.output_choices: list[dict] = []

    def __next__(self) -> "ChatCompletionChunk":
        chunk = self.chunk_iter.__next__()
        self._process_chunk(chunk)
        return chunk

    def __iter__(self) -> Iterator["ChatCompletionChunk"]:
        for chunk in self.chunk_iter:
            self._process_chunk(chunk)
            yield chunk

    def _process_chunk(self, chunk: "ChatCompletionChunk") -> None:
        if self.first_chunk is None:
            self.first_chunk = chunk
        for chunk_choice in chunk.choices:
            for i in range(chunk_choice.index + 1 - len(self.output_choices)):
                self.output_choices.append(
                    {
                        "index": len(self.output_choices),
                        "message": {
                            "content": None,
                            "tool_calls": None,
                        },
                        "finish_reason": None,
                        "logprobs": None,
                    }
                )

            # choice fields
            choice = self.output_choices[chunk_choice.index]
            if chunk_choice.finish_reason:
                choice["finish_reason"] = chunk_choice.finish_reason
            if chunk_choice.logprobs:
                choice["logprobs"] = chunk_choice.logprobs

            # message
            if chunk_choice.delta.content:
                if choice["message"]["content"] is None:
                    choice["message"]["content"] = ""
                choice["message"]["content"] += chunk_choice.delta.content
            if chunk_choice.delta.role:
                choice["message"]["role"] = chunk_choice.delta.role

            # function call
            if chunk_choice.delta.function_call:
                raise NotImplementedError("Function calls not supported")

            # tool calls
            if chunk_choice.delta.tool_calls:
                if choice["message"]["tool_calls"] is None:
                    choice["message"]["tool_calls"] = []
                for tool_call_delta in chunk_choice.delta.tool_calls:
                    for i in range(
                        tool_call_delta.index + 1 - len(choice["message"]["tool_calls"])  # type: ignore
                    ):
                        choice["message"]["tool_calls"].append(  # type: ignore
                            {
                                "function": {"name": None, "arguments": ""},
                            }
                        )
                    tool_call = choice["message"]["tool_calls"][  # type: ignore
                        tool_call_delta.index
                    ]
                    if tool_call_delta.id is not None:
                        tool_call["id"] = tool_call_delta.id
                    if tool_call_delta.type is not None:
                        tool_call["type"] = tool_call_delta.type
                    if tool_call_delta.function is not None:
                        if tool_call_delta.function.name is not None:
                            tool_call["function"]["name"] = (
                                tool_call_delta.function.name
                            )
                        if tool_call_delta.function.arguments is not None:
                            tool_call["function"]["arguments"] += (
                                tool_call_delta.function.arguments
                            )

    def final_response(self) -> "ChatCompletion":
        from openai.types.chat import ChatCompletion

        if self.first_chunk is None:
            raise ValueError("No chunks received")
        return ChatCompletion(
            id=self.first_chunk.id,
            choices=self.output_choices,  # type: ignore
            created=self.first_chunk.created,
            model=self.first_chunk.model,
            object="chat.completion",
        )
