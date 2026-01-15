import asyncio
import os
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from google import genai
from google.genai.types import GenerateImagesConfig
from pydantic import BaseModel

from weave.integrations.google_genai.gemini_utils import (
    google_genai_gemini_accumulator,
    google_genai_gemini_postprocess_inputs,
)
from weave.integrations.google_genai.google_genai_sdk import get_google_genai_patcher
from weave.integrations.integration_utilities import op_name_from_ref


@pytest.fixture(autouse=True)
def patch_google_genai() -> Generator[None, None, None]:
    """Patch Google GenAI for all tests in this file."""
    patcher = get_google_genai_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


class Recipe(BaseModel):
    recipe_name: str
    recipe_description: str
    recipe_ingredients: list[str]


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_sync(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = google_client.models.generate_content(
        model="gemini-2.0-flash",
        contents="What's the capital of France?",
    )

    assert "paris" in response.text.lower()

    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content"
    assert call.output is not None
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0
    assert (
        call.output.usageMetadata.totalTokenCount
        == call.output.usageMetadata.candidatesTokenCount
        + call.output.usageMetadata.promptTokenCount
    )


@pytest.mark.asyncio
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
async def test_content_generation_async(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = await google_client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents="What's the capital of France?",
    )
    assert "paris" in response.text.lower()
    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.AsyncModels.generate_content"
    assert call.output is not None
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0
    assert (
        call.output.usageMetadata.totalTokenCount
        == call.output.usageMetadata.candidatesTokenCount
        + call.output.usageMetadata.promptTokenCount
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_sync_stream(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = google_client.models.generate_content_stream(
        model="gemini-2.0-flash",
        contents="What's the capital of France?",
    )
    response_text = ""
    try:
        for chunk in response:
            if hasattr(chunk, "text"):
                response_text += chunk.text
            else:
                raise ValueError(f"Unexpected chunk format: {chunk}")
    except Exception as e:
        raise AssertionError(f"Error processing stream: {e!s}") from e
    assert "paris" in response_text.lower()
    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content_stream"
    assert call.output is not None
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0
    assert (
        call.output.usageMetadata.totalTokenCount
        == call.output.usageMetadata.candidatesTokenCount
        + call.output.usageMetadata.promptTokenCount
    )


@pytest.mark.asyncio
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
async def test_content_generation_async_stream(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response_text = ""
    try:
        response = await google_client.aio.models.generate_content_stream(
            model="gemini-2.0-flash", contents="What's the capital of France?"
        )
        async for chunk in response:
            if hasattr(chunk, "text"):
                response_text += chunk.text
            else:
                raise ValueError(f"Unexpected chunk format: {chunk}")
    except Exception as e:
        raise AssertionError(f"Error processing stream: {e!s}") from e
    assert "paris" in response_text.lower()
    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.AsyncModels.generate_content_stream"
    assert call.output is not None
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0
    assert (
        call.output.usageMetadata.totalTokenCount
        == call.output.usageMetadata.candidatesTokenCount
        + call.output.usageMetadata.promptTokenCount
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_chat_session_sync(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    system_instruction = """
You are an expert software developer and a helpful coding assistant.
You are able to generate high-quality code in the Python programming language."""

    response = google_client.chats.create(
        model="gemini-2.0-flash",
        config=genai.types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.5,
        ),
    ).send_message(
        "Write a python function named `is_leap_year` that checks if a year is a leap year."
    )

    assert "def is_leap_year" in response.text.lower()

    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.chats.Chat.send_message"
    assert call.output is not None
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0
    assert (
        call.output.usageMetadata.totalTokenCount
        == call.output.usageMetadata.candidatesTokenCount
        + call.output.usageMetadata.promptTokenCount
    )


@pytest.mark.asyncio
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
async def test_chat_session_async(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = await google_client.aio.chats.create(
        model="gemini-2.0-flash",
        config=genai.types.GenerateContentConfig(
            system_instruction="""
You are an expert software developer and a helpful coding assistant.
You are able to generate high-quality code in the Python programming language.""",
            temperature=0.5,
        ),
    ).send_message(
        "Write a python function named `is_leap_year` that checks if a year is a leap year."
    )
    assert "def is_leap_year" in response.text.lower()
    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.chats.AsyncChat.send_message"
    assert call.output is not None
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0
    assert (
        call.output.usageMetadata.totalTokenCount
        == call.output.usageMetadata.candidatesTokenCount
        + call.output.usageMetadata.promptTokenCount
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_function_calling(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    get_destination = genai.types.FunctionDeclaration(
        name="get_destination",
        description="Get the destination that the user wants to go to",
        parameters={
            "type": "OBJECT",
            "properties": {
                "destination": {
                    "type": "STRING",
                    "description": "Destination that the user wants to go to",
                },
            },
        },
    )

    destination_tool = genai.types.Tool(
        function_declarations=[get_destination],
    )

    google_client.models.generate_content(
        model="gemini-2.0-flash",
        contents="I'd like to travel to Paris.",
        config=genai.types.GenerateContentConfig(
            tools=[destination_tool],
            temperature=0,
        ),
    )

    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content"
    assert call.output is not None
    assert (
        call.output.candidates[0]
        .content.parts[0]
        .functionCall.args["destination"]
        .lower()
        == "paris"
    )
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0
    assert (
        call.output.usageMetadata.totalTokenCount
        == call.output.usageMetadata.candidatesTokenCount
        + call.output.usageMetadata.promptTokenCount
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_image_generation_sync(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = google_client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt="Fuzzy bunnies in my kitchen",
        config=GenerateImagesConfig(number_of_images=1),
    )

    assert len(response.generated_images) == 1

    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_images"
    assert call.output is not None


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_image_generation_async(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = asyncio.run(
        google_client.aio.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt="Fuzzy bunnies in my kitchen",
            config=GenerateImagesConfig(number_of_images=1),
        )
    )

    assert len(response.generated_images) == 1

    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.AsyncModels.generate_images"
    assert call.output is not None


# Unit tests for gemini_utils functions


class TestGoogleGenaiGeminiAccumulator:
    """Tests for the google_genai_gemini_accumulator function."""

    def _make_mock_response(
        self,
        text: str | None = None,
        thought_text: str | None = None,
        prompt_token_count: int | None = None,
        candidates_token_count: int | None = None,
        total_token_count: int | None = None,
        cached_content_token_count: int | None = None,
        thoughts_token_count: int | None = None,
    ) -> MagicMock:
        """Create a mock GenerateContentResponse."""
        response = MagicMock()

        parts = []
        if text is not None:
            part = MagicMock()
            part.text = text
            part.thought = False
            parts.append(part)
        if thought_text is not None:
            thought_part = MagicMock()
            thought_part.text = thought_text
            thought_part.thought = True
            parts.append(thought_part)

        candidate = MagicMock()
        candidate.content.parts = parts
        response.candidates = [candidate]

        response.usage_metadata.prompt_token_count = prompt_token_count
        response.usage_metadata.candidates_token_count = candidates_token_count
        response.usage_metadata.total_token_count = total_token_count
        response.usage_metadata.cached_content_token_count = cached_content_token_count
        response.usage_metadata.thoughts_token_count = thoughts_token_count

        return response

    def test_returns_value_when_acc_is_none(self):
        """When acc is None, return value unchanged."""
        value = self._make_mock_response(text="Hello")
        result = google_genai_gemini_accumulator(None, value)
        assert result is value

    def test_token_counts_are_replaced_not_summed(self):
        """Token counts should be replaced with latest non-None values, not summed."""
        acc = self._make_mock_response(
            text="Hello ",
            prompt_token_count=10,
            candidates_token_count=5,
            total_token_count=15,
        )
        # Gemini returns cumulative counts, so the second chunk has larger values
        value = self._make_mock_response(
            text="world",
            prompt_token_count=10,
            candidates_token_count=15,
            total_token_count=25,
        )

        result = google_genai_gemini_accumulator(acc, value)

        # Token counts should be replaced (not summed: 10+10=20, 5+15=20, 15+25=40)
        assert result.usage_metadata.prompt_token_count == 10
        assert result.usage_metadata.candidates_token_count == 15
        assert result.usage_metadata.total_token_count == 25

    def test_token_counts_preserved_when_value_is_none(self):
        """Token counts from acc are preserved if value's counts are None."""
        acc = self._make_mock_response(
            text="Hello ",
            prompt_token_count=10,
            candidates_token_count=5,
            total_token_count=15,
        )
        value = self._make_mock_response(
            text="world",
            prompt_token_count=None,
            candidates_token_count=None,
            total_token_count=None,
        )

        result = google_genai_gemini_accumulator(acc, value)

        assert result.usage_metadata.prompt_token_count == 10
        assert result.usage_metadata.candidates_token_count == 5
        assert result.usage_metadata.total_token_count == 15

    def test_thoughts_token_count_accumulated(self):
        """thoughts_token_count should be accumulated for thinking models."""
        acc = self._make_mock_response(
            text="Hello ",
            thoughts_token_count=100,
        )
        value = self._make_mock_response(
            text="world",
            thoughts_token_count=250,  # Cumulative count
        )

        result = google_genai_gemini_accumulator(acc, value)

        assert result.usage_metadata.thoughts_token_count == 250

    def test_thinking_content_accumulated_separately(self):
        """Thinking content and response content should be accumulated by type."""
        # First chunk with thinking content
        acc = self._make_mock_response(thought_text="Let me think...")

        # Second chunk with response content at same index
        value = self._make_mock_response(text="The answer is 42")

        result = google_genai_gemini_accumulator(acc, value)

        # Both should be preserved
        parts = result.candidates[0].content.parts
        assert len(parts) == 2

        thought_parts = [p for p in parts if getattr(p, "thought", False)]
        response_parts = [p for p in parts if not getattr(p, "thought", False)]

        assert len(thought_parts) == 1
        assert thought_parts[0].text == "Let me think..."
        assert len(response_parts) == 1
        assert response_parts[0].text == "The answer is 42"

    def test_thinking_content_concatenated(self):
        """Multiple thinking chunks should be concatenated."""
        acc = self._make_mock_response(thought_text="Let me ")
        value = self._make_mock_response(thought_text="think about this...")

        result = google_genai_gemini_accumulator(acc, value)

        parts = result.candidates[0].content.parts
        thought_parts = [p for p in parts if getattr(p, "thought", False)]
        assert len(thought_parts) == 1
        assert thought_parts[0].text == "Let me think about this..."

    def test_text_accumulated_correctly(self):
        """Regular text content should be concatenated."""
        acc = self._make_mock_response(text="Hello ")
        value = self._make_mock_response(text="world!")

        result = google_genai_gemini_accumulator(acc, value)

        parts = result.candidates[0].content.parts
        response_parts = [p for p in parts if not getattr(p, "thought", False)]
        assert len(response_parts) == 1
        assert response_parts[0].text == "Hello world!"


class TestGoogleGenaiGeminiPostprocessInputs:
    """Tests for the google_genai_gemini_postprocess_inputs function."""

    def test_extracts_system_instruction_from_config(self):
        """System instruction should be extracted from config and surfaced at top level."""
        config = MagicMock()
        config.system_instruction = "You are a helpful assistant."

        self_obj = MagicMock()
        self_obj._model = "gemini-2.0-flash"

        inputs = {"self": self_obj, "config": config, "contents": "Hello"}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert result["system_instruction"] == "You are a helpful assistant."
        assert result["model"] == "gemini-2.0-flash"

    def test_no_system_instruction_when_not_present(self):
        """No system_instruction key added when config doesn't have one."""
        config = MagicMock(spec=["temperature"])  # No system_instruction attr

        self_obj = MagicMock()
        self_obj._model = "gemini-2.0-flash"

        inputs = {"self": self_obj, "config": config, "contents": "Hello"}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert "system_instruction" not in result

    def test_no_system_instruction_when_config_is_none(self):
        """No error when config is None."""
        self_obj = MagicMock()
        self_obj._model = "gemini-2.0-flash"

        inputs = {"self": self_obj, "config": None, "contents": "Hello"}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert "system_instruction" not in result

    def test_no_system_instruction_when_value_is_none(self):
        """No system_instruction key added when the value is None."""
        config = MagicMock()
        config.system_instruction = None

        self_obj = MagicMock()
        self_obj._model = "gemini-2.0-flash"

        inputs = {"self": self_obj, "config": config, "contents": "Hello"}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert "system_instruction" not in result
