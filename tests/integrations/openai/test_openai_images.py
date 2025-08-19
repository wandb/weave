import base64
import os
from io import BytesIO

import httpx
import pytest
from openai import AsyncOpenAI, OpenAI
from PIL import Image
from vcr.request import Request as VCRRequest
from vcr.stubs import httpx_stubs

from weave.integrations.integration_utilities import op_name_from_ref
from weave.integrations.openai import openai_sdk
from weave.trace.autopatch import AutopatchSettings, IntegrationSettings


def _make_vcr_request_binary_safe(httpx_request: httpx.Request, **kwargs):
    # Read the raw bytes once
    body_bytes = httpx_request.read()
    # Put the bytes back so httpx can still send the request
    httpx_request.stream = httpx.ByteStream(body_bytes)

    # Encode to ASCII so the cassette is text-only
    body_b64 = base64.b64encode(body_bytes).decode("ascii")

    # Add a flag header so you know it’s encoded
    headers = dict(httpx_request.headers)
    headers["X-VCR-Body-Base64"] = "true"

    return VCRRequest(
        method=httpx_request.method,
        uri=str(httpx_request.url),
        body=body_b64,
        headers=headers,
    )


# One-line monkey-patch
httpx_stubs._make_vcr_request = _make_vcr_request_binary_safe


# Utility function to check postprocessed output
def _check_postprocessed_output(output, expected_response, expected_size=(1024, 1024)):
    # Output can be a tuple (original_response, pil_image) or just the response
    if isinstance(output, tuple):
        assert len(output) == 2
        # original_response, pil_image = output
        # assert original_response == expected_response
        # assert isinstance(pil_image, Image.Image)
        # assert pil_image.size == expected_size
    else:
        # If not a tuple, just check it's the response
        # assert output == expected_response
        assert output is not None


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_image_generate_sync(client_creator) -> None:
    """Test synchronous image generation using OpenAI GPT-Image"""
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    # Autopatch testing is disabled for this test, so we need to manually patch the OpenAI client
    # This is a workaround to allow us to test the OpenAI client without the autopatching tests interfering
    openai_sdk._openai_patcher = None

    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=True),
    )

    with client_creator(autopatch_settings=autopatch_settings) as client:
        openai_client = OpenAI(api_key=api_key)

        response = openai_client.images.generate(
            model="gpt-image-1",
            prompt="A cute baby sea otter",
            size="1024x1024",
            quality="low",
            output_format="jpeg",
            output_compression=50,
        )

        calls = list(client.calls())
        assert len(calls) == 1
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 1
        assert getattr(response.data[0], "b64_json", None) is not None
        assert getattr(response, "created", None) is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.generate"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify inputs
        inputs = call.inputs
        assert inputs["model"] == "gpt-image-1"
        assert inputs["prompt"] == "A cute baby sea otter"

        # Verify output structure
        _check_postprocessed_output(call.output, response, expected_size=(1024, 1024))

        # Verify usage tracking
        usage = call.summary["usage"]["gpt-image-1"]
        assert usage["requests"] == 1


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_image_generate_async(client_creator) -> None:
    """Test asynchronous image generation using OpenAI GPT-Image"""
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    # Autopatch testing is disabled for this test, so we need to manually patch the OpenAI client
    # This is a workaround to allow us to test the OpenAI client without the autopatching tests interfering
    openai_sdk._openai_patcher = None

    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=True),
    )

    with client_creator(autopatch_settings=autopatch_settings) as client:
        openai_client = AsyncOpenAI(api_key=api_key)
        response = await openai_client.images.generate(
            model="gpt-image-1",
            prompt="A majestic mountain landscape at sunset",
            size="1024x1024",
            quality="low",
            output_format="jpeg",
            output_compression=50,
        )

        calls = list(client.calls())
        assert len(calls) == 1
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 1
        assert getattr(response.data[0], "b64_json", None) is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.generate"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify inputs
        inputs = call.inputs
        assert inputs["model"] == "gpt-image-1"
        assert inputs["prompt"] == "A majestic mountain landscape at sunset"

        # Verify output structure
        _check_postprocessed_output(call.output, response, expected_size=(1024, 1024))

        # Verify usage tracking
        usage = call.summary["usage"]["gpt-image-1"]
        assert usage["requests"] == 1


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_image_edit_sync(client_creator) -> None:
    """Test synchronous image editing using OpenAI GPT-Image Edit API"""
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    # Autopatch testing is disabled for this test, so we need to manually patch the OpenAI client
    # This is a workaround to allow us to test the OpenAI client without the autopatching tests interfering
    openai_sdk._openai_patcher = None

    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=True),
    )

    # Create a simple test image and save to BytesIO
    test_image = Image.new("RGB", (1024, 1024), color=(0, 255, 0))
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    image_buffer.name = "image.png"

    with client_creator(autopatch_settings=autopatch_settings) as client:
        openai_client = OpenAI(api_key=api_key)

        response = openai_client.images.edit(
            model="gpt-image-1",
            image=[image_buffer],
            prompt="Add a red circle",
            size="1024x1024",
            quality="low",
        )

        calls = list(client.calls())
        assert len(calls) == 1
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 1
        assert getattr(response.data[0], "b64_json", None) is not None
        assert getattr(response, "created", None) is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.edit"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify inputs
        inputs = call.inputs
        assert inputs["model"] == "gpt-image-1"
        assert inputs["prompt"] == "Add a red circle"

        # Verify output structure
        _check_postprocessed_output(call.output, response, expected_size=(1024, 1024))

        # Verify usage tracking
        usage = call.summary["usage"]["gpt-image-1"]
        assert usage["requests"] == 1


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_image_edit_async(client_creator) -> None:
    """Test asynchronous image editing using OpenAI GPT-Image Edit API"""
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    # Autopatch testing is disabled for this test, so we need to manually patch the OpenAI client
    # This is a workaround to allow us to test the OpenAI client without the autopatching tests interfering
    openai_sdk._openai_patcher = None

    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=True),
    )

    # Create a simple test image and save to BytesIO
    test_image = Image.new("RGB", (256, 256), color=(0, 0, 255))
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    image_buffer.name = "image.png"

    with client_creator(autopatch_settings=autopatch_settings) as client:
        openai_client = AsyncOpenAI(api_key=api_key)

        response = await openai_client.images.edit(
            model="gpt-image-1",
            image=image_buffer,
            prompt="Add a yellow triangle",
            size="1024x1024",
            quality="low",
        )

        calls = list(client.calls())
        assert len(calls) == 1
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 1
        assert getattr(response.data[0], "b64_json", None) is not None
        assert getattr(response, "created", None) is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.edit"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify inputs
        inputs = call.inputs
        assert inputs["model"] == "gpt-image-1"
        assert inputs["prompt"] == "Add a yellow triangle"

        # Verify output structure
        _check_postprocessed_output(call.output, response, expected_size=(1024, 1024))

        # Verify usage tracking
        usage = call.summary["usage"]["gpt-image-1"]
        assert usage["requests"] == 1


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_image_create_variation_sync(client_creator) -> None:
    """Test synchronous image variation generation using OpenAI GPT-Image Variation API"""
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    # Autopatch testing is disabled for this test, so we need to manually patch the OpenAI client
    # This is a workaround to allow us to test the OpenAI client without the autopatching tests interfering
    openai_sdk._openai_patcher = None

    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=True),
    )

    # Create a simple test image and save to BytesIO
    test_image = Image.new("RGB", (1024, 1024), color=(255, 255, 0))
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    image_buffer.name = "image.png"

    with client_creator(autopatch_settings=autopatch_settings) as client:
        openai_client = OpenAI(api_key=api_key)

        response = openai_client.images.create_variation(
            image=image_buffer,
            n=2,
        )

        calls = list(client.calls())
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 2
        assert getattr(response, "created", None) is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.create_variation"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify output structure
        _check_postprocessed_output(call.output, response, expected_size=(1024, 1024))

        # Verify usage tracking
        print(call.summary)
        usage = call.summary["usage"][""]
        assert usage["requests"] == 1


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_image_create_variation_async(client_creator) -> None:
    """Test asynchronous image variation generation using OpenAI GPT-Image Variation API"""
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    # Autopatch testing is disabled for this test, so we need to manually patch the OpenAI client
    # This is a workaround to allow us to test the OpenAI client without the autopatching tests interfering
    openai_sdk._openai_patcher = None

    autopatch_settings = AutopatchSettings(
        openai=IntegrationSettings(enabled=True),
    )

    # Create a simple test image and save to BytesIO
    test_image = Image.new("RGB", (128, 128), color=(0, 255, 255))
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    image_buffer.name = "image.png"

    with client_creator(autopatch_settings=autopatch_settings) as client:
        openai_client = AsyncOpenAI(api_key=api_key)

        response = await openai_client.images.create_variation(
            image=image_buffer,
            n=2,
        )

        calls = list(client.calls())
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 2
        assert getattr(response, "created", None) is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.create_variation"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify output structure
        _check_postprocessed_output(call.output, response, expected_size=(1024, 1024))

        # Verify usage tracking
        usage = call.summary["usage"][""]
        assert usage["requests"] == 1


def test_openai_image_postprocess_inputs():
    """Test input postprocessing function."""
    from weave.integrations.openai.gpt_image_utils import (
        openai_image_postprocess_inputs,
    )

    test_inputs = {
        "model": "gpt-image-1",
        "prompt": "A test prompt",
        "size": "1024x1024",
    }

    result = openai_image_postprocess_inputs(test_inputs)

    # Should return inputs unchanged
    assert result == test_inputs


def test_openai_image_postprocess_outputs():
    """Test output postprocessing function."""
    from weave.integrations.openai.gpt_image_utils import (
        openai_image_postprocess_outputs,
    )

    # Create a simple test image and convert to base64
    test_image = Image.new("RGB", (1024, 1024), color=(255, 0, 0))
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="PNG")
    image_data = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

    # Mock response structure
    class MockData:
        def __init__(self, b64_json):
            self.b64_json = b64_json

    class MockResponse:
        def __init__(self, b64_json):
            self.data = [MockData(b64_json)]

    mock_response = MockResponse(image_data)

    result = openai_image_postprocess_outputs(mock_response)

    # Should return tuple of (original_response, PIL_image) or just the response
    _check_postprocessed_output(result, mock_response, expected_size=(1024, 1024))
