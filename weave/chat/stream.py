import json
from collections.abc import Iterator

import requests

from weave.chat.types.chat_completion_chunk import ChatCompletionChunk


class ChatCompletionChunkStream:
    """
    A stream wrapper for ChatCompletionChunk objects from a requests response.

    This class takes a requests response object and yields ChatCompletionChunk
    objects by parsing the server-sent events stream.

    Args:
        response: The requests.Response object from a streaming API call.

    Yields:
        ChatCompletionChunk: Parsed chat completion chunks from the stream.

    Raises:
        json.JSONDecodeError: If a line cannot be parsed as valid JSON.

    Examples:
        >>> response = requests.post(url, stream=True, ...)
        >>> stream = ChatCompletionChunkStream(response)
        >>> for chunk in stream:
        ...     print(chunk.choices[0].delta.content)
    """

    def __init__(self, response: requests.Response) -> None:
        self.response = response

    def __iter__(self) -> Iterator[ChatCompletionChunk]:
        if self.response.encoding is None:
            self.response.encoding = "utf-8"
        for line in self.response.iter_lines(decode_unicode=True):
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
