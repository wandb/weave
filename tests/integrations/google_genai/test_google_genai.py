import os
import unittest.mock
from collections.abc import Generator
from unittest.mock import Mock

import pytest
from google import genai
from google.genai.types import GenerateImagesConfig
from pydantic import BaseModel

from weave.integrations.google_genai.gemini_utils import (
    _traverse_and_replace_blobs,
    google_genai_gemini_accumulator,
    google_genai_gemini_on_finish,
    google_genai_gemini_postprocess_inputs,
    google_genai_gemini_postprocess_output,
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
@pytest.mark.asyncio
async def test_image_generation_async(client):
    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = await google_client.aio.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt="Fuzzy bunnies in my kitchen",
        config=GenerateImagesConfig(number_of_images=1),
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


def test_on_finish_includes_cached_content_token_count():
    """Test that cached_content_token_count is mapped to cache_read_input_tokens."""
    from weave.trace.call import Call

    call = Mock(spec=Call)
    call.inputs = {"model": "gemini-2.0-flash"}
    call.summary = {}

    usage_metadata = Mock()
    usage_metadata.prompt_token_count = 100
    usage_metadata.candidates_token_count = 50
    usage_metadata.total_token_count = 150
    usage_metadata.thoughts_token_count = None
    usage_metadata.cached_content_token_count = 30

    output = Mock()
    output.usage_metadata = usage_metadata

    google_genai_gemini_on_finish(call, output, None)

    model_usage = call.summary["usage"]["gemini-2.0-flash"]
    assert model_usage["cache_read_input_tokens"] == 30
    assert "thoughts_tokens" not in model_usage


def test_on_finish_excludes_cached_content_when_missing():
    """Test that cache_read_input_tokens is omitted when cached_content_token_count is absent."""
    from weave.trace.call import Call

    call = Mock(spec=Call)
    call.inputs = {"model": "gemini-2.0-flash"}
    call.summary = {}

    usage_metadata = Mock(
        spec=["prompt_token_count", "candidates_token_count", "total_token_count"]
    )
    usage_metadata.prompt_token_count = 100
    usage_metadata.candidates_token_count = 50
    usage_metadata.total_token_count = 150

    output = Mock()
    output.usage_metadata = usage_metadata

    google_genai_gemini_on_finish(call, output, None)

    model_usage = call.summary["usage"]["gemini-2.0-flash"]
    assert "cache_read_input_tokens" not in model_usage
    assert "thoughts_tokens" not in model_usage


def test_on_finish_with_inline_data_output():
    """Test that on_finish handles responses with inline_data (images) correctly."""
    from google.genai import types

    from weave.trace.call import Call

    call = Mock(spec=Call)
    call.inputs = {"model": "gemini-2.0-flash"}
    call.summary = {}

    # Build a real Pydantic response with inline_data (image) instead of text
    image_part = types.Part.from_bytes(data=b"fake_image_bytes", mime_type="image/png")
    candidate = types.Candidate(
        content=types.Content(role="model", parts=[image_part]),
    )
    output = types.GenerateContentResponse(
        candidates=[candidate],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10,
            candidates_token_count=0,
            total_token_count=10,
        ),
    )

    # on_finish should handle usage metadata without errors
    google_genai_gemini_on_finish(call, output, None)

    model_usage = call.summary["usage"]["gemini-2.0-flash"]
    assert model_usage["prompt_tokens"] == 10
    assert model_usage["total_tokens"] == 10


def test_postprocess_output_suppresses_non_text_warning():
    """Test that postprocess_output suppresses the non-text parts warning."""
    import logging

    from google.genai import types

    # Build a response with inline_data (image) that triggers the warning
    image_part = types.Part.from_bytes(data=b"fake_image_bytes", mime_type="image/png")
    candidate = types.Candidate(
        content=types.Content(role="model", parts=[image_part]),
    )
    output = types.GenerateContentResponse(
        candidates=[candidate],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10,
            candidates_token_count=0,
            total_token_count=10,
        ),
    )

    # Reset the SDK's internal warning flag so it would warn again
    import google.genai.types as genai_types

    genai_types._response_text_non_text_warning_logged = False

    # postprocess_output should suppress the warning
    result = google_genai_gemini_postprocess_output(output)
    assert result is output  # Returns unmodified output

    # Now access .text — the warning should NOT fire because the flag was set
    genai_logger = logging.getLogger("google.genai.types")
    with unittest.mock.patch.object(genai_logger, "warning") as mock_warn:
        _ = output.text
        mock_warn.assert_not_called()

    # Restore the flag
    genai_types._response_text_non_text_warning_logged = False


def test_wrapper_sync_sets_postprocess_output():
    """Test that the sync wrapper sets postprocess_output on the op."""
    from weave.integrations.google_genai.gemini_utils import (
        google_genai_gemini_postprocess_output,
        google_genai_gemini_wrapper_sync,
    )
    from weave.trace.autopatch import OpSettings

    settings = OpSettings()
    wrapper = google_genai_gemini_wrapper_sync(settings)

    def dummy_fn(self, *args, **kwargs):
        return None

    wrapped = wrapper(dummy_fn)
    assert wrapped.postprocess_output is google_genai_gemini_postprocess_output


def test_wrapper_async_sets_postprocess_output():
    """Test that the async wrapper sets postprocess_output on the op."""
    from weave.integrations.google_genai.gemini_utils import (
        google_genai_gemini_postprocess_output,
        google_genai_gemini_wrapper_async,
    )
    from weave.trace.autopatch import OpSettings

    settings = OpSettings()
    wrapper = google_genai_gemini_wrapper_async(settings)

    async def dummy_fn(self, *args, **kwargs):
        return None

    wrapped = wrapper(dummy_fn)
    assert wrapped.postprocess_output is google_genai_gemini_postprocess_output


def _create_mock_part(text: str, thought: bool = False) -> Mock:
    """Helper to create a mock Part with text and optional thought attribute."""
    part = Mock()
    part.text = text
    part.thought = thought
    return part


def _create_mock_response(
    parts: list[Mock],
    prompt_token_count: int | None = None,
    candidates_token_count: int | None = None,
    total_token_count: int | None = None,
    cached_content_token_count: int | None = None,
    thoughts_token_count: int | None = None,
) -> Mock:
    """Helper to create a mock GenerateContentResponse."""
    content = Mock()
    content.parts = parts

    candidate = Mock()
    candidate.content = content

    usage_metadata = Mock()
    usage_metadata.prompt_token_count = prompt_token_count
    usage_metadata.candidates_token_count = candidates_token_count
    usage_metadata.total_token_count = total_token_count
    usage_metadata.cached_content_token_count = cached_content_token_count
    # Only set thoughts_token_count if provided to test getattr fallback
    if thoughts_token_count is not None:
        usage_metadata.thoughts_token_count = thoughts_token_count
    else:
        # Delete the attribute so getattr returns None
        del usage_metadata.thoughts_token_count

    response = Mock()
    response.candidates = [candidate]
    response.usage_metadata = usage_metadata

    return response


def test_accumulator_returns_value_when_acc_is_none():
    """Test that accumulator returns the value when acc is None (first chunk)."""
    part = _create_mock_part("Hello")
    response = _create_mock_response([part])

    result = google_genai_gemini_accumulator(None, response)

    assert result is response


def test_accumulator_accumulates_regular_text_parts():
    """Test that regular text parts are accumulated correctly."""
    # First chunk
    acc_part = _create_mock_part("Hello ")
    acc = _create_mock_response([acc_part], prompt_token_count=10)

    # Second chunk
    value_part = _create_mock_part("World")
    value = _create_mock_response([value_part], prompt_token_count=20)

    result = google_genai_gemini_accumulator(acc, value)

    assert result is acc
    assert acc_part.text == "Hello World"


def test_accumulator_separates_thought_and_regular_parts():
    """Test that thought parts are accumulated separately from regular parts."""
    # Accumulator has both thought and regular parts
    acc_thought_part = _create_mock_part("Thinking: ", thought=True)
    acc_regular_part = _create_mock_part("Answer: ")
    acc = _create_mock_response([acc_thought_part, acc_regular_part])

    # Value has a new thought chunk
    value_thought_part = _create_mock_part("still thinking...", thought=True)
    value = _create_mock_response([value_thought_part])

    result = google_genai_gemini_accumulator(acc, value)

    # Thought part should be accumulated to the thought part
    assert acc_thought_part.text == "Thinking: still thinking..."
    # Regular part should remain unchanged
    assert acc_regular_part.text == "Answer: "
    assert result is acc


def test_accumulator_adds_new_thought_part_when_not_present():
    """Test that a new thought part is appended when no matching part exists."""
    # Accumulator starts with only regular part
    acc_regular_part = _create_mock_part("Answer: ")
    acc = _create_mock_response([acc_regular_part])

    # Value has a thought part
    value_thought_part = _create_mock_part("Let me think...", thought=True)
    value = _create_mock_response([value_thought_part])

    result = google_genai_gemini_accumulator(acc, value)

    # Regular part should remain unchanged
    assert acc_regular_part.text == "Answer: "
    # New thought part should be appended
    assert len(acc.candidates[0].content.parts) == 2
    assert acc.candidates[0].content.parts[1].text == "Let me think..."
    assert acc.candidates[0].content.parts[1].thought is True
    assert result is acc


def test_accumulator_adds_new_regular_part_when_only_thought_exists():
    """Test that a new regular part is appended when only thought part exists."""
    # Accumulator starts with only thought part
    acc_thought_part = _create_mock_part("Thinking...", thought=True)
    acc = _create_mock_response([acc_thought_part])

    # Value has a regular (non-thought) part
    value_regular_part = _create_mock_part("Here's my answer")
    value = _create_mock_response([value_regular_part])

    result = google_genai_gemini_accumulator(acc, value)

    # Thought part should remain unchanged
    assert acc_thought_part.text == "Thinking..."
    # New regular part should be appended
    assert len(acc.candidates[0].content.parts) == 2
    assert acc.candidates[0].content.parts[1].text == "Here's my answer"
    assert acc.candidates[0].content.parts[1].thought is False
    assert result is acc


def test_accumulator_handles_thoughts_token_count():
    """Test that thoughts_token_count is accumulated correctly."""
    acc_part = _create_mock_part("Hello")
    acc = _create_mock_response([acc_part], thoughts_token_count=100)

    value_part = _create_mock_part(" World")
    value = _create_mock_response([value_part], thoughts_token_count=200)

    result = google_genai_gemini_accumulator(acc, value)

    assert result.usage_metadata.thoughts_token_count == 200


def test_accumulator_ignores_none_thoughts_token_count():
    """Test that thoughts_token_count is not updated when value has None."""
    acc_part = _create_mock_part("Hello")
    acc = _create_mock_response([acc_part], thoughts_token_count=100)

    value_part = _create_mock_part(" World")
    # Create value without thoughts_token_count
    value = _create_mock_response([value_part])

    result = google_genai_gemini_accumulator(acc, value)

    # thoughts_token_count should remain at original value
    assert result.usage_metadata.thoughts_token_count == 100


def test_accumulator_updates_all_token_counts():
    """Test that all token counts are updated from value when present."""
    acc_part = _create_mock_part("Hello")
    acc = _create_mock_response(
        [acc_part],
        prompt_token_count=10,
        candidates_token_count=5,
        total_token_count=15,
        cached_content_token_count=2,
        thoughts_token_count=50,
    )

    value_part = _create_mock_part(" World")
    value = _create_mock_response(
        [value_part],
        prompt_token_count=20,
        candidates_token_count=15,
        total_token_count=35,
        cached_content_token_count=5,
        thoughts_token_count=100,
    )

    result = google_genai_gemini_accumulator(acc, value)

    assert result.usage_metadata.prompt_token_count == 20
    assert result.usage_metadata.candidates_token_count == 15
    assert result.usage_metadata.total_token_count == 35
    assert result.usage_metadata.cached_content_token_count == 5
    assert result.usage_metadata.thoughts_token_count == 100


def test_accumulator_preserves_non_text_parts():
    """Test that non-text parts (e.g. inline_data images) are preserved in the accumulator."""
    acc_part = _create_mock_part("Hello")
    acc = _create_mock_response([acc_part])

    # Value part has None text (e.g. an inline_data image part)
    value_part = Mock()
    value_part.text = None
    value = _create_mock_response([value_part])

    result = google_genai_gemini_accumulator(acc, value)

    # Text should remain unchanged since value part had None text
    assert acc_part.text == "Hello"
    # Non-text part should be appended to the accumulated parts
    assert value_part in result.candidates[0].content.parts
    assert result is acc


# ── _traverse_and_replace_blobs unit tests ────────────────────────────────────


def test_traverse_and_replace_blobs_converts_blob_dict_to_content():
    """Dict with 'data' bytes and 'mime_type' is converted to a Content object."""
    from weave import Content

    blob_dict = {"data": b"fake_image_bytes", "mime_type": "image/jpeg"}
    result = _traverse_and_replace_blobs(blob_dict)

    assert isinstance(result, Content)
    assert result.mimetype == "image/jpeg"


def test_traverse_and_replace_blobs_converts_part_with_inline_data():
    """types.Part.from_bytes (Pydantic BaseModel) has inline_data converted to Content."""
    from google.genai import types

    from weave import Content

    part = types.Part.from_bytes(data=b"fake_image_bytes", mime_type="image/jpeg")
    result = _traverse_and_replace_blobs(part)

    assert isinstance(result, dict)
    assert isinstance(result["inline_data"], Content)
    assert result["inline_data"].mimetype == "image/jpeg"


def test_traverse_and_replace_blobs_traverses_list_of_parts():
    """List of Parts with blobs are recursively traversed; text parts unchanged."""
    from google.genai import types

    from weave import Content

    parts = [
        types.Part.from_bytes(data=b"fake_image_bytes", mime_type="image/jpeg"),
        types.Part(text="Where was this photo taken?"),
    ]
    result = _traverse_and_replace_blobs(parts)

    assert isinstance(result, list)
    assert isinstance(result[0]["inline_data"], Content)
    assert result[1]["text"] == "Where was this photo taken?"
    assert result[1]["inline_data"] is None


def test_traverse_and_replace_blobs_traverses_tuple():
    """Tuples with blobs are traversed and returned as tuples."""
    from google.genai import types

    from weave import Content

    part = types.Part.from_bytes(data=b"fake_image_bytes", mime_type="image/jpeg")
    result = _traverse_and_replace_blobs((part,))

    assert isinstance(result, tuple)
    assert isinstance(result[0]["inline_data"], Content)


def test_traverse_and_replace_blobs_skips_empty_bytes():
    """Dict with empty bytes for 'data' is not converted to Content."""
    blob_dict = {"data": b"", "mime_type": "image/jpeg"}
    result = _traverse_and_replace_blobs(blob_dict)

    # Empty data → no Content conversion
    assert isinstance(result, dict)
    assert "data" in result


def test_traverse_and_replace_blobs_skips_missing_mime_type():
    """Dict with data but no mime_type is not converted to Content."""
    blob_dict = {"data": b"fake_bytes"}
    result = _traverse_and_replace_blobs(blob_dict)

    assert isinstance(result, dict)
    assert "data" in result


def test_traverse_and_replace_blobs_skips_missing_data():
    """Dict with mime_type but no data is not converted to Content."""
    blob_dict = {"mime_type": "image/jpeg"}
    result = _traverse_and_replace_blobs(blob_dict)

    assert isinstance(result, dict)
    assert "mime_type" in result


def test_traverse_and_replace_blobs_leaves_primitives_unchanged():
    """Primitive values pass through unmodified."""
    assert _traverse_and_replace_blobs("hello") == "hello"
    assert _traverse_and_replace_blobs(42) == 42
    assert _traverse_and_replace_blobs(None) is None


def test_traverse_and_replace_blobs_traverses_nested_dict():
    """Blobs nested inside dicts are replaced recursively."""
    from weave import Content

    nested = {
        "outer": {"inner": {"data": b"fake_image_bytes", "mime_type": "image/png"}}
    }
    result = _traverse_and_replace_blobs(nested)

    assert isinstance(result["outer"]["inner"], Content)
    assert result["outer"]["inner"].mimetype == "image/png"


# ── postprocess functions unit tests ─────────────────────────────────────────


def test_postprocess_inputs_converts_image_bytes_to_content():
    """Image bytes in 'contents' inputs are converted to Content for Weave UI display."""
    from google.genai import types

    from weave import Content

    mock_self = Mock()
    mock_self._model = "gemini-2.0-flash"

    inputs = {
        "self": mock_self,
        "contents": [
            types.Part.from_bytes(data=b"fake_jpeg_bytes", mime_type="image/jpeg"),
            "Where was this photo taken?",
        ],
    }

    result = google_genai_gemini_postprocess_inputs(inputs)

    image_part = result["contents"][0]
    assert isinstance(image_part, dict)
    assert isinstance(image_part["inline_data"], Content)
    assert image_part["inline_data"].mimetype == "image/jpeg"
    # Plain text string is unchanged
    assert result["contents"][1] == "Where was this photo taken?"


def test_postprocess_inputs_leaves_text_only_contents_unchanged():
    """Text-only 'contents' are not affected by postprocess_inputs."""
    mock_self = Mock()
    mock_self._model = "gemini-2.0-flash"

    inputs = {
        "self": mock_self,
        "contents": ["What's the capital of France?"],
    }

    result = google_genai_gemini_postprocess_inputs(inputs)

    assert result["contents"][0] == "What's the capital of France?"


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key", "x-goog-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_with_image_bytes(client):
    """Image bytes passed to generate_content are stored as Content in the Weave trace."""
    from google.genai import types

    from weave import Content

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    image_bytes = b"\xff\xd8\xff\xe0"  # minimal JPEG header bytes

    google_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            "Where was this photo taken?",
        ],
    )

    call = next(iter(client.get_calls()))
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content"

    # The image bytes in inputs must be converted to Content for Weave UI display
    contents = call.inputs.get("contents", [])
    image_part = contents[0]
    assert isinstance(image_part, dict), "Part should be dict after postprocessing"
    assert isinstance(image_part["inline_data"], Content), (
        "Image bytes must be converted to Content so they display in the Weave UI"
    )
    assert image_part["inline_data"].mimetype == "image/jpeg"
