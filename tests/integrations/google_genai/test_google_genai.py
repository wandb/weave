import asyncio
import os
from collections.abc import Generator
from unittest.mock import Mock

import pytest
from google import genai
from google.genai.types import GenerateImagesConfig
from pydantic import BaseModel

from weave.integrations.google_genai.gemini_utils import google_genai_gemini_on_finish
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
def test_system_instruction_extracted_from_config(client):
    """Test that system_instruction is extracted from config and surfaced at top level of inputs."""
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    system_instruction = (
        "You are a helpful assistant that always responds in haiku format."
    )

    google_client.models.generate_content(
        model="gemini-2.0-flash",
        contents="What's the capital of France?",
        config=genai.types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.5,
        ),
    )

    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content"

    # Verify that system_instruction is surfaced at the top level of inputs
    assert "system_instruction" in call.inputs
    assert call.inputs["system_instruction"] == system_instruction

    # Verify that the call was successful
    assert call.output is not None
    assert call.output.usageMetadata.candidatesTokenCount > 0
    assert call.output.usageMetadata.promptTokenCount > 0


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


def test_thoughts_token_count_included_in_usage():
    """Test that thoughts_token_count is included in usage data when available."""
    from weave.trace.call import Call

    # Create a mock call with model name in inputs
    call = Mock(spec=Call)
    call.inputs = {"model": "gemini-2.0-flash-thinking-exp"}
    call.summary = {}

    # Create a mock output with usage_metadata including thoughts_token_count
    usage_metadata = Mock()
    usage_metadata.prompt_token_count = 100
    usage_metadata.candidates_token_count = 50
    usage_metadata.total_token_count = 200
    usage_metadata.thoughts_token_count = 50  # Thinking model token count

    output = Mock()
    output.usage_metadata = usage_metadata

    # Call the on_finish handler
    google_genai_gemini_on_finish(call, output, None)

    # Verify that thoughts_tokens is included in the usage data
    assert call.summary is not None
    assert "usage" in call.summary
    model_usage = call.summary["usage"]["gemini-2.0-flash-thinking-exp"]
    assert model_usage["prompt_tokens"] == 100
    assert model_usage["completion_tokens"] == 50
    assert model_usage["total_tokens"] == 200
    assert model_usage["thoughts_tokens"] == 50
    assert model_usage["requests"] == 1


def test_thoughts_token_count_not_included_when_missing():
    """Test that thoughts_tokens is not included when thoughts_token_count is not available."""
    from weave.trace.call import Call

    # Create a mock call with model name in inputs
    call = Mock(spec=Call)
    call.inputs = {"model": "gemini-2.0-flash"}
    call.summary = {}

    # Create a mock output with usage_metadata without thoughts_token_count
    # Use spec_set to prevent Mock from auto-creating attributes
    usage_metadata = Mock(
        spec=["prompt_token_count", "candidates_token_count", "total_token_count"]
    )
    usage_metadata.prompt_token_count = 100
    usage_metadata.candidates_token_count = 50
    usage_metadata.total_token_count = 150
    # thoughts_token_count is not in spec, so getattr will return None

    output = Mock()
    output.usage_metadata = usage_metadata

    # Call the on_finish handler
    google_genai_gemini_on_finish(call, output, None)

    # Verify that thoughts_tokens is NOT included in the usage data
    assert call.summary is not None
    assert "usage" in call.summary
    model_usage = call.summary["usage"]["gemini-2.0-flash"]
    assert model_usage["prompt_tokens"] == 100
    assert model_usage["completion_tokens"] == 50
    assert model_usage["total_tokens"] == 150
    assert "thoughts_tokens" not in model_usage
    assert model_usage["requests"] == 1
