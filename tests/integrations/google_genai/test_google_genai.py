import asyncio
import os

import pytest
from pydantic import BaseModel

from weave.integrations.integration_utilities import op_name_from_ref


class Recipe(BaseModel):
    recipe_name: str
    recipe_description: str
    recipe_ingredients: list[str]


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_sync(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = google_client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents="What's the capital of France?",
    )

    assert "paris" in response.text.lower()

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content"
    assert call.output is not None
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_async(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = asyncio.run(
        google_client.aio.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents="What's the capital of France?",
        )
    )

    assert "paris" in response.text.lower()

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.AsyncModels.generate_content"
    assert call.output is not None
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_sync_stream(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = google_client.models.generate_content_stream(
        model="gemini-2.0-flash-exp",
        contents="What's the capital of France?",
    )

    response_text = ""
    for chunk in response:
        response_text += chunk.text

    assert "paris" in response_text.lower()

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content_stream"
    assert call.output is not None
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_async_stream(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))

    async def generate_content():
        response_text = ""
        response = await google_client.aio.models.generate_content_stream(
            model="gemini-2.0-flash-exp", contents="What's the capital of France?"
        )
        async for chunk in response:
            response_text += chunk.text
        return response_text

    response_text = asyncio.run(generate_content())
    assert "paris" in response_text.lower()

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.AsyncModels.generate_content_stream"
    assert call.output is not None
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_chat_session_sync(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    system_instruction = """
You are an expert software developer and a helpful coding assistant.
You are able to generate high-quality code in the Python programming language."""

    response = google_client.chats.create(
        model="gemini-2.0-flash-exp",
        config=genai.types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.5,
        ),
    ).send_message(
        "Write a python function named `is_leap_year` that checks if a year is a leap year."
    )

    assert "def is_leap_year" in response.text.lower()

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.chats.Chat.send_message"
    assert call.output is not None
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_chat_session_async(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    system_instruction = """
You are an expert software developer and a helpful coding assistant.
You are able to generate high-quality code in the Python programming language."""

    response = asyncio.run(
        google_client.aio.chats.create(
            model="gemini-2.0-flash-exp",
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.5,
            ),
        ).send_message(
            "Write a python function named `is_leap_year` that checks if a year is a leap year."
        )
    )

    assert "def is_leap_year" in response.text.lower()

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.chats.AsyncChat.send_message"
    assert call.output is not None
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_function_calling(client):
    from google import genai

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
        model="gemini-2.0-flash-exp",
        contents="I'd like to travel to Paris.",
        config=genai.types.GenerateContentConfig(
            tools=[destination_tool],
            temperature=0,
        ),
    )

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content"
    assert call.output is not None
    assert (
        call.output.candidates[0]
        .content.parts[0]
        .function_call.args["destination"]
        .lower()
        == "paris"
    )
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_image_generation_sync(client):
    from google import genai
    from google.genai.types import GenerateImagesConfig

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = google_client.models.generate_images(
        model='imagen-3.0-generate-002',
        prompt='Fuzzy bunnies in my kitchen',
        config=GenerateImagesConfig(number_of_images=1)
    )

    assert len(response.generated_images) == 1

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_images"
    assert call.output is not None


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_image_generation_async(client):
    from google import genai
    from google.genai.types import GenerateImagesConfig

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = asyncio.run(
        google_client.aio.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt='Fuzzy bunnies in my kitchen',
            config=GenerateImagesConfig(number_of_images=1)
        )
    )

    assert len(response.generated_images) == 1

    call = list(client.calls())[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.AsyncModels.generate_images"
    assert call.output is not None
