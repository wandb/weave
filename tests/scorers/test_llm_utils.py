from unittest.mock import MagicMock

import pytest

from weave.scorers.llm_utils import (
    embed,
    instructor_client,
)
from weave.trace.autopatch import autopatch

# Ensure autopatch is applied for testing
autopatch()

# Mock classes for OpenAI clients with the expected structure


# Synchronous OpenAI Client Mock
class MockOpenAIChatCompletions:
    def create(self, *args, **kwargs):
        return {"response": "sync response"}


class MockOpenAIEmbeddings:
    def create(self, model, input, **kwargs):
        return type(
            "Response",
            (),
            {
                "data": [
                    type("Embedding", (), {"embedding": [0.1, 0.2, 0.3]}) for _ in input
                ]
            },
        )()


class MockSyncOpenAI:
    def __init__(self):
        self.chat = MockOpenAIChatCompletions()
        self.embeddings = MockOpenAIEmbeddings()


# Asynchronous OpenAI Client Mock
class MockAsyncOpenAIChatCompletions:
    async def create(self, *args, **kwargs):
        return {"response": "async response"}


class MockAsyncOpenAIEmbeddings:
    async def create(self, model, input, **kwargs):
        return type(
            "Response",
            (),
            {
                "data": [
                    type("Embedding", (), {"embedding": [0.4, 0.5, 0.6]}) for _ in input
                ]
            },
        )()


class MockAsyncOpenAI:
    def __init__(self):
        self.chat = MockAsyncOpenAIChatCompletions()
        self.embeddings = MockAsyncOpenAIEmbeddings()


# Fixtures to provide mock clients
@pytest.fixture
def sync_client():
    return MockSyncOpenAI()


@pytest.fixture
def async_client():
    return MockAsyncOpenAI()


# Test to ensure instructor_client returns a valid instructor client for synchronous clients
def test_instructor_client_sync(sync_client, monkeypatch):
    # Mock instructor module
    mock_instructor = MagicMock()
    mock_instructor_client = MagicMock()
    mock_instructor.from_openai = MagicMock(return_value=mock_instructor_client)
    mock_instructor.patch = MagicMock()
    monkeypatch.setattr("weave.scorers.llm_utils.instructor", mock_instructor)

    client = instructor_client(sync_client)
    assert client is not None, "Instructor client should not be None for sync_client."
    assert client == mock_instructor_client
    mock_instructor.from_openai.assert_called_once_with(sync_client)


# Test to ensure instructor_client returns a valid instructor client for asynchronous clients
def test_instructor_client_async(async_client, monkeypatch):
    # Mock instructor module
    mock_instructor = MagicMock()
    mock_instructor_client = MagicMock()
    mock_instructor.from_openai = MagicMock(return_value=mock_instructor_client)
    mock_instructor.patch = MagicMock()
    monkeypatch.setattr("weave.scorers.llm_utils.instructor", mock_instructor)

    client = instructor_client(async_client)
    assert client is not None, "Instructor client should not be None for async_client."
    assert client == mock_instructor_client
    mock_instructor.from_openai.assert_called_once_with(async_client)


# Test the embed function with a synchronous client
@pytest.mark.asyncio
async def test_embed_sync(sync_client):
    model_id = "text-embedding-3-small"
    texts = ["Hello world", "OpenAI"]
    try:
        embeddings = embed(sync_client, model_id, texts)
        assert len(embeddings) == 2, "Should return embeddings for both texts."
        assert embeddings[0] == [
            0.1,
            0.2,
            0.3,
        ], "First embedding does not match expected values."
        assert embeddings[1] == [
            0.1,
            0.2,
            0.3,
        ], "Second embedding does not match expected values."
    except ValueError as e:
        pytest.fail(f"embed() raised ValueError: {e}")


# Test the embed function with an asynchronous client
@pytest.mark.asyncio
async def test_embed_async(async_client):
    model_id = "text-embedding-3-small"
    texts = ["Hello world", "OpenAI"]
    with pytest.raises(ValueError, match="Async client used with sync function"):
        await embed(async_client, model_id, texts)


# Test the embed function with an unsupported client type
@pytest.mark.asyncio
async def test_embed_unsupported_client():
    class UnsupportedClient:
        pass

    unsupported_client = UnsupportedClient()
    with pytest.raises(ValueError, match="Unsupported client type: unsupportedclient"):
        await embed(unsupported_client, "unknown-model", ["test"])
