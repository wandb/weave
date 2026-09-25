import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from pydantic import ValidationError

from weave.chat.async_completions import AsyncCompletions
from weave.chat.async_stream import AsyncChatCompletionChunkStream
from weave.chat.types.chat_completion import ChatCompletion
from weave.chat.types.chat_completion_chunk import ChatCompletionChunk
from weave.trace.weave_client import WeaveClient


@pytest.fixture
def mock_client():
    """Create a mock WeaveClient."""
    return WeaveClient(
        entity="test-entity",
        project="test-project",
        server=None,
    )


@pytest.fixture
def mock_wandb_context():
    """Mock the wandb API context."""
    with patch("weave.chat.async_completions.get_wandb_api_context") as mock_ctx:
        mock_context = MagicMock()
        mock_context.api_key = "test-api-key"
        mock_ctx.return_value = mock_context
        yield mock_ctx


@pytest.mark.asyncio
async def test_async_completions_create_non_streaming(mock_client, mock_wandb_context):
    """Test non-streaming completion creation."""
    completions = AsyncCompletions(mock_client)
    
    # Mock response data
    mock_response_data = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-3.5-turbo",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you today?"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }
    
    # Mock aiohttp session and response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()
    
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await completions.create(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-3.5-turbo",
            endpoint="inference",
            track_llm_call=False,
        )
    
    # Verify the result
    assert isinstance(result, ChatCompletion)
    assert result.id == "chatcmpl-123"
    assert result.choices[0].message.content == "Hello! How can I help you today?"
    
    # Verify the API call
    mock_session.post.assert_called_once()
    call_args = mock_session.post.call_args
    assert call_args[0][0] == f"https://trace.wandb.ai/v1/chat/completions"
    assert call_args[1]["json"]["messages"] == [{"role": "user", "content": "Hello"}]
    assert call_args[1]["headers"]["Authorization"] == "Bearer test-api-key"


@pytest.mark.asyncio
async def test_async_completions_create_streaming(mock_client, mock_wandb_context):
    """Test streaming completion creation."""
    completions = AsyncCompletions(mock_client)
    
    # Mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await completions.create(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-3.5-turbo",
            stream=True,
            endpoint="inference",
            track_llm_call=False,
        )
    
    # Verify the result is a stream
    assert isinstance(result, AsyncChatCompletionChunkStream)
    assert result.response == mock_response


@pytest.mark.asyncio
async def test_async_completions_playground_endpoint(mock_client, mock_wandb_context):
    """Test completion creation with playground endpoint."""
    completions = AsyncCompletions(mock_client)
    
    # Mock response data
    mock_response_data = {
        "response": {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-3.5-turbo",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello from playground!"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
    }
    
    # Mock aiohttp session and response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()
    
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        with patch("weave.chat.async_completions.weave_trace_server_url", return_value="http://localhost:1337"):
            result = await completions.create(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-3.5-turbo",
                endpoint="playground",
                track_llm_call=False,
            )
    
    # Verify the result
    assert isinstance(result, ChatCompletion)
    assert result.choices[0].message.content == "Hello from playground!"
    
    # Verify the API call
    mock_session.post.assert_called_once()
    call_args = mock_session.post.call_args
    assert call_args[0][0] == "http://localhost:1337/completions/create"
    assert call_args[1]["auth"].login == "api"
    assert call_args[1]["auth"].password == "test-api-key"
    assert call_args[1]["json"]["inputs"]["messages"] == [{"role": "user", "content": "Hello"}]
    assert call_args[1]["json"]["project_id"] == "test-entity/test-project"


@pytest.mark.asyncio
async def test_async_completions_with_op_tracking(mock_client, mock_wandb_context):
    """Test completion creation with op tracking enabled."""
    completions = AsyncCompletions(mock_client)
    
    # Mock response data
    mock_response_data = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-3.5-turbo",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Tracked response"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }
    
    # Mock aiohttp session and response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()
    
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await completions.create(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-3.5-turbo",
            endpoint="inference",
            track_llm_call=True,  # Enable tracking
        )
    
    # Verify the result
    assert isinstance(result, ChatCompletion)
    assert result.choices[0].message.content == "Tracked response"


@pytest.mark.asyncio
async def test_async_completions_error_handling(mock_client, mock_wandb_context):
    """Test error handling for 401 responses."""
    completions = AsyncCompletions(mock_client)
    
    # Mock 401 response
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.reason = "Unauthorized"
    mock_response.request_info = MagicMock()
    mock_response.history = []
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=mock_response.request_info,
            history=mock_response.history,
            status=401,
            message="Unauthorized",
            headers=mock_response.headers,
        )
    )
    
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(aiohttp.ClientResponseError) as exc_info:
            await completions.create(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-3.5-turbo",
                endpoint="inference",
                track_llm_call=False,
            )
        
        assert "please make sure inference is enabled for entity test-entity" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_completions_no_api_key(mock_client):
    """Test error when no API key is available."""
    completions = AsyncCompletions(mock_client)
    
    with patch("weave.chat.async_completions.get_wandb_api_context", return_value=None):
        with pytest.raises(ValueError, match="No context found"):
            await completions.create(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-3.5-turbo",
                track_llm_call=False,
            )


@pytest.mark.asyncio
async def test_async_completions_all_parameters(mock_client, mock_wandb_context):
    """Test completion creation with all optional parameters."""
    completions = AsyncCompletions(mock_client)
    
    # Mock response data
    mock_response_data = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-3.5-turbo",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Full params response"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }
    
    # Mock aiohttp session and response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = MagicMock()
    
    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await completions.create(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-3.5-turbo",
            frequency_penalty=0.5,
            max_tokens=100,
            n=2,
            presence_penalty=0.3,
            stream=False,
            stream_options={"include_usage": True},
            temperature=0.7,
            top_p=0.9,
            endpoint="inference",
            track_llm_call=False,
        )
    
    # Verify the result
    assert isinstance(result, ChatCompletion)
    
    # Verify all parameters were passed
    call_args = mock_session.post.call_args
    json_data = call_args[1]["json"]
    assert json_data["frequency_penalty"] == 0.5
    assert json_data["max_tokens"] == 100
    assert json_data["n"] == 2
    assert json_data["presence_penalty"] == 0.3
    assert json_data["stream"] == False
    assert json_data["stream_options"] == {"include_usage": True}
    assert json_data["temperature"] == 0.7
    assert json_data["top_p"] == 0.9