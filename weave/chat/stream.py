import json
from collections.abc import Iterator
from contextlib import ExitStack

import httpx
from typing_extensions import Self

from weave.chat.types.chat_completion_chunk import ChatCompletionChunk


class ChatCompletionChunkStream:
    """A stream wrapper for ChatCompletionChunk objects from an httpx response.

    This class takes an httpx response object and yields ChatCompletionChunk
    objects by parsing the server-sent events stream. W&B ``_meta`` records are
    consumed internally and are not yielded as completion chunks.

    Args:
        response: The httpx.Response object from a streaming API call.
        exit_stack: Optional owned contexts for the response and its client.
        initial_conversation_id: Optional caller-supplied conversation context.

    Yields:
        ChatCompletionChunk: Parsed chat completion chunks from the stream.

    Raises:
        json.JSONDecodeError: If a line cannot be parsed as valid JSON.

    Examples:
        >>> with httpx.Client() as client:
        ...     with client.stream('POST', url, ...) as response:
        ...         stream = ChatCompletionChunkStream(response)
        ...         for chunk in stream:
        ...             print(chunk.choices[0].delta.content)
    """

    def __init__(
        self,
        response: httpx.Response,
        exit_stack: ExitStack | None = None,
        initial_conversation_id: str | None = None,
    ) -> None:
        self.response = response
        self._exit_stack = exit_stack
        self.conversation_id = initial_conversation_id

    def close(self) -> None:
        if self._exit_stack is None:
            self.response.close()
        else:
            self._exit_stack.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __iter__(self) -> Iterator[ChatCompletionChunk]:
        with self:
            for raw_line in self.response.iter_lines():
                if raw_line:  # skip keep-alive lines
                    line = raw_line
                    if raw_line.startswith("data: "):
                        # This is how OpenAI streams things back
                        line = raw_line[6:]
                    if line == "[DONE]":
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        # Preserve the existing Pydantic validation error for
                        # malformed completion chunks.
                        yield ChatCompletionChunk.model_validate_json(line)
                        continue
                    metadata = data.get("_meta") if isinstance(data, dict) else None
                    if isinstance(metadata, dict):
                        conversation_id = metadata.get("conversation_id")
                        if isinstance(conversation_id, str):
                            self.conversation_id = conversation_id
                        continue
                    yield ChatCompletionChunk.model_validate(data)
