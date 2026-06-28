import asyncio

import pytest

from weave.chat.async_chat import AsyncChat
from weave.chat.async_completions import AsyncCompletions
from weave.trace.weave_client import WeaveClient


def test_async_chat_initialization():
    """Test that AsyncChat properly initializes with a WeaveClient."""
    # Create a mock WeaveClient
    mock_client = WeaveClient(
        entity="test-entity",
        project="test-project",
        server=None,
    )
    
    # Create AsyncChat instance
    async_chat = AsyncChat(mock_client)
    
    # Verify initialization
    assert isinstance(async_chat.completions, AsyncCompletions)
    assert async_chat.completions._client == mock_client


def test_async_chat_mirrors_sync_api():
    """Test that AsyncChat has the same API structure as the sync Chat class."""
    mock_client = WeaveClient(
        entity="test-entity",
        project="test-project",
        server=None,
    )
    
    async_chat = AsyncChat(mock_client)
    
    # Verify the completions attribute exists and has create method
    assert hasattr(async_chat, 'completions')
    assert hasattr(async_chat.completions, 'create')
    assert asyncio.iscoroutinefunction(async_chat.completions.create)