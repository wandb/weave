import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from weave.chat.async_stream import AsyncChatCompletionChunkStream
from weave.chat.types.chat_completion_chunk import ChatCompletionChunk


class MockAsyncIterator:
    """Mock async iterator for simulating streaming response content."""
    
    def __init__(self, chunks):
        self.chunks = chunks
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        chunk = self.chunks[self.index]
        self.index += 1
        return chunk


@pytest.fixture
def mock_response():
    """Create a mock aiohttp ClientResponse."""
    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.closed = False
    response.close = MagicMock()
    return response


@pytest.mark.asyncio
async def test_async_stream_basic_iteration(mock_response):
    """Test basic streaming iteration."""
    # Create test chunks
    chunks = [
        b'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n',
        b'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1234567891,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}\n',
        b'data: {"id":"chunk-3","object":"chat.completion.chunk","created":1234567892,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n',
        b'data: [DONE]\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream and collect results
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    async for chunk in stream:
        collected_chunks.append(chunk)
    
    # Verify results
    assert len(collected_chunks) == 3  # [DONE] should be filtered out
    assert collected_chunks[0].choices[0].delta.content == "Hello"
    assert collected_chunks[1].choices[0].delta.content == " world"
    assert collected_chunks[2].choices[0].finish_reason == "stop"


@pytest.mark.asyncio
async def test_async_stream_multiline_chunks(mock_response):
    """Test handling of multiple lines in a single chunk."""
    # Create test chunks with multiple lines
    chunks = [
        b'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Line 1"},"finish_reason":null}]}\n'
        b'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1234567891,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Line 2"},"finish_reason":null}]}\n',
        b'data: {"id":"chunk-3","object":"chat.completion.chunk","created":1234567892,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream and collect results
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    async for chunk in stream:
        collected_chunks.append(chunk)
    
    # Verify results
    assert len(collected_chunks) == 3
    assert collected_chunks[0].choices[0].delta.content == "Line 1"
    assert collected_chunks[1].choices[0].delta.content == "Line 2"


@pytest.mark.asyncio
async def test_async_stream_partial_chunks(mock_response):
    """Test handling of partial chunks that need buffering."""
    # Create test chunks that split JSON across boundaries
    chunks = [
        b'data: {"id":"chunk-1","object":"chat.completion.chunk",',
        b'"created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,',
        b'"delta":{"content":"Hello"},"finish_reason":null}]}\n',
        b'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1234567891,',
        b'"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":" world"},',
        b'"finish_reason":null}]}\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream and collect results
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    async for chunk in stream:
        collected_chunks.append(chunk)
    
    # Verify results
    assert len(collected_chunks) == 2
    assert collected_chunks[0].choices[0].delta.content == "Hello"
    assert collected_chunks[1].choices[0].delta.content == " world"


@pytest.mark.asyncio
async def test_async_stream_empty_lines(mock_response):
    """Test handling of empty lines (keep-alive)."""
    # Create test chunks with empty lines
    chunks = [
        b'\n',  # Empty line
        b'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n',
        b'\n\n',  # Multiple empty lines
        b'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1234567891,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}\n',
        b'\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream and collect results
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    async for chunk in stream:
        collected_chunks.append(chunk)
    
    # Verify results
    assert len(collected_chunks) == 2
    assert collected_chunks[0].choices[0].delta.content == "Hello"
    assert collected_chunks[1].choices[0].delta.content == " world"


@pytest.mark.asyncio
async def test_async_stream_done_marker(mock_response):
    """Test handling of [DONE] marker."""
    # Create test chunks
    chunks = [
        b'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n',
        b'data: [DONE]\n',
        b'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1234567891,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Should not appear"},"finish_reason":null}]}\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream and collect results
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    async for chunk in stream:
        collected_chunks.append(chunk)
    
    # Verify results - should get all chunks except [DONE]
    assert len(collected_chunks) == 2
    assert collected_chunks[0].choices[0].delta.content == "Hello"
    assert collected_chunks[1].choices[0].delta.content == "Should not appear"


@pytest.mark.asyncio
async def test_async_stream_json_error(mock_response):
    """Test handling of JSON parsing errors."""
    # Create test chunks with invalid JSON
    chunks = [
        b'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n',
        b'data: {invalid json}\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    # Collect chunks and expect error
    with pytest.raises(json.JSONDecodeError):
        async for chunk in stream:
            collected_chunks.append(chunk)
    
    # Should have collected first valid chunk before error
    assert len(collected_chunks) == 1
    assert collected_chunks[0].choices[0].delta.content == "Hello"


@pytest.mark.asyncio
async def test_async_stream_context_manager(mock_response):
    """Test async context manager functionality."""
    # Create test chunks
    chunks = [
        b'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Use stream as async context manager
    async with AsyncChatCompletionChunkStream(mock_response) as stream:
        collected_chunks = []
        async for chunk in stream:
            collected_chunks.append(chunk)
        
        assert len(collected_chunks) == 1
        assert collected_chunks[0].choices[0].delta.content == "Hello"
    
    # Verify response was closed
    mock_response.close.assert_called_once()


@pytest.mark.asyncio
async def test_async_stream_no_data_prefix(mock_response):
    """Test handling of lines without 'data: ' prefix."""
    # Create test chunks without data: prefix
    chunks = [
        b'{"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"No prefix"},"finish_reason":null}]}\n',
        b'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1234567891,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"With prefix"},"finish_reason":null}]}\n',
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream and collect results
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    async for chunk in stream:
        collected_chunks.append(chunk)
    
    # Verify results
    assert len(collected_chunks) == 2
    assert collected_chunks[0].choices[0].delta.content == "No prefix"
    assert collected_chunks[1].choices[0].delta.content == "With prefix"


@pytest.mark.asyncio
async def test_async_stream_unicode_handling(mock_response):
    """Test handling of Unicode content."""
    # Create test chunks with Unicode
    chunks = [
        'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello 👋"},"finish_reason":null}]}\n'.encode('utf-8'),
        'data: {"id":"chunk-2","object":"chat.completion.chunk","created":1234567891,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":" 世界"},"finish_reason":null}]}\n'.encode('utf-8'),
    ]
    
    # Set up mock content iterator
    mock_response.content = MockAsyncIterator(chunks)
    
    # Create stream and collect results
    stream = AsyncChatCompletionChunkStream(mock_response)
    collected_chunks = []
    
    async for chunk in stream:
        collected_chunks.append(chunk)
    
    # Verify results
    assert len(collected_chunks) == 2
    assert collected_chunks[0].choices[0].delta.content == "Hello 👋"
    assert collected_chunks[1].choices[0].delta.content == " 世界"