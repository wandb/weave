import json
from collections.abc import Iterator

import httpx

from weave.chat.types.chat_completion_chunk import ChatCompletionChunk


class ChatCompletionChunkStream:
    """A stream wrapper for ChatCompletionChunk objects from an httpx response.

    This class takes an httpx response object and yields ChatCompletionChunk
    objects by parsing the server-sent events stream.

    Args:
        response: The httpx.Response object from a streaming API call.

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

    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    def __iter__(self) -> Iterator[ChatCompletionChunk]:
        for line in self.response.iter_lines():
            if line:  # skip keep-alive lines
                if line.startswith("data: "):
                    # This is how OpenAI streams things back
                    line = line[6:]
                if line == "[DONE]":
                    continue
                try:
                    yield ChatCompletionChunk.model_validate_json(line)
                except json.JSONDecodeError as e:
                    print(f"Error parsing line as JSON: {line}")
                    raise e
