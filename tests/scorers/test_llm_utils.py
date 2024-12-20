import pytest
from openai import AsyncOpenAI, OpenAI

from weave.scorers.llm_utils import (
    embed,
    instructor_client,
)
from weave.trace.autopatch import autopatch

# Ensure autopatch is applied for testing
autopatch()

# Mock classes for OpenAI clients with the expected structure


# Synchronous OpenAI Client Mock
class MockCompletions:
    def create(self, *args, **kwargs):
        return {"response": "sync response"}


class MockChat:
    def __init__(self):
        self.completions = MockCompletions()


class MockOpenAIEmbeddings:
    def create(self, model, input, **kwargs):
        class EmbeddingData:
            def __init__(self, embedding):
                self.embedding = embedding

        class EmbeddingResponse:
            def __init__(self, data):
                self.data = data

        return EmbeddingResponse([EmbeddingData([0.1, 0.2, 0.3]) for _ in input])


class MockSyncOpenAI(OpenAI):
    def __init__(self):
        self.chat = MockChat()
        self.embeddings = MockOpenAIEmbeddings()


# Asynchronous OpenAI Client Mock
class MockAsyncCompletions:
    async def create(self, *args, **kwargs):
        return {"response": "async response"}


class MockAsyncChat:
    def __init__(self):
        self.completions = MockAsyncCompletions()


class MockAsyncOpenAIEmbeddings:
    async def create(self, model, input, **kwargs):
        class EmbeddingData:
            def __init__(self, embedding):
                self.embedding = embedding

        class EmbeddingResponse:
            def __init__(self, data):
                self.data = data

        return EmbeddingResponse([EmbeddingData([0.4, 0.5, 0.6]) for _ in input])


class MockAsyncOpenAI(AsyncOpenAI):
    def __init__(self):
        self.chat = MockAsyncChat()
        self.embeddings = MockAsyncOpenAIEmbeddings()


# Fixtures to provide mock clients
@pytest.fixture
def sync_client():
    return MockSyncOpenAI()


@pytest.fixture
def async_client():
    return MockAsyncOpenAI()


# Test to ensure instructor_client returns a valid instructor client for synchronous clients
def test_instructor_client_sync(sync_client):
    try:
        client = instructor_client(sync_client)
    except Exception as e:
        pytest.fail(f"instructor_client raised an exception for sync_client: {e}")
    assert client is not None, "Instructor client should not be None for sync_client."


# Test to ensure instructor_client returns a valid instructor client for asynchronous clients
def test_instructor_client_async(async_client):
    try:
        client = instructor_client(async_client)
    except Exception as e:
        pytest.fail(f"instructor_client raised an exception for async_client: {e}")
    assert client is not None, "Instructor client should not be None for async_client."


# Test the embed function with a synchronous client
def test_embed_sync(sync_client):
    model_id = "text-embedding-3-small"
    texts = ["Hello world", "OpenAI"]
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


# Test the embed function with an unsupported client type
@pytest.mark.asyncio
async def test_embed_unsupported_client():
    class UnsupportedClient:
        pass

    unsupported_client = UnsupportedClient()
    with pytest.raises(ValueError, match="Unsupported client type: unsupportedclient"):
        await embed(unsupported_client, "unknown-model", ["test"])
