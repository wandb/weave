import json
from collections.abc import AsyncIterator
from typing import Optional

import aiohttp

from weave.chat.types.chat_completion_chunk import ChatCompletionChunk


class AsyncChatCompletionChunkStream:
    """
    An async stream wrapper for ChatCompletionChunk objects from an aiohttp response.

    This class takes an aiohttp ClientResponse object and yields ChatCompletionChunk
    objects by parsing the server-sent events stream asynchronously.

    Args:
        response: The aiohttp.ClientResponse object from a streaming API call.

    Yields:
        ChatCompletionChunk: Parsed chat completion chunks from the stream.

    Raises:
        json.JSONDecodeError: If a line cannot be parsed as valid JSON.

    Examples:
        >>> async with session.post(url, ...) as response:
        ...     stream = AsyncChatCompletionChunkStream(response)
        ...     async for chunk in stream:
        ...         print(chunk.choices[0].delta.content)
    """

    def __init__(self, response: aiohttp.ClientResponse) -> None:
        self.response = response
        self._iterator: Optional[AsyncIterator[str]] = None

    async def __aiter__(self) -> AsyncIterator[ChatCompletionChunk]:
        # Create the content iterator if not already created
        if self._iterator is None:
            self._iterator = self.response.content.__aiter__()
        
        buffer = ""
        
        async for chunk in self._iterator:
            # Decode bytes to string
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            
            buffer += chunk
            
            # Process complete lines
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
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
        
        # Process any remaining data in buffer
        if buffer.strip():
            line = buffer.strip()
            if line.startswith("data: "):
                line = line[6:]
            if line != "[DONE]":
                try:
                    yield ChatCompletionChunk.model_validate_json(line)
                except json.JSONDecodeError as e:
                    print(f"Error parsing line as JSON: {line}")
                    raise e

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Ensure response is properly closed
        if not self.response.closed:
            self.response.close()