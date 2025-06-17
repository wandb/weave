import base64
import os
from io import BytesIO

import pytest
from openai import AsyncOpenAI, OpenAI
from PIL import Image

from weave.integrations.integration_utilities import op_name_from_ref
from weave.trace.weave_client import WeaveClient
from weave.integrations.openai import openai_sdk
from weave.trace.autopatch import AutopatchSettings, IntegrationSettings, OpSettings



@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_image_generate_sync(client_creator) -> None:
    """Test synchronous image generation using OpenAI GPT-Image"""
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_sdk._openai_patcher = None

    # Autopatch testing is disabled for this test, so we need to manually patch the OpenAI client
    # This is a workaround to allow us to test the OpenAI client without the autopatching tests interfering
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
            output_compression=50
        )

        calls = list(client.calls())
        assert len(calls) == 1
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 1
        assert response.data[0].b64_json is not None
        assert response.created is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.generate"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify inputs
        inputs = call.inputs
        assert inputs["model"] == "gpt-image-1"
        assert inputs["prompt"] == "A cute baby sea otter"

        # Verify output structure
        output = call.output
        assert len(output) == 2
        
        # First element should be the original response
        original_response, pil_image = output
        assert original_response.created == response.created
        assert len(original_response.data) == 1
        assert original_response.data[0].b64_json is not None
        
        # Second element should be PIL Image
        assert isinstance(pil_image, Image.Image)
        assert pil_image.size == (1024, 1024)

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
            output_compression=50
        )

        calls = list(client.calls())
        assert len(calls) == 1
        call = calls[0]

        # Verify the response structure
        assert len(response.data) == 1
        assert response.data[0].b64_json is not None

        # Verify weave call tracking
        assert op_name_from_ref(call.op_name) == "openai.images.generate"
        assert call.started_at is not None
        assert call.started_at < call.ended_at

        # Verify inputs
        inputs = call.inputs
        assert inputs["model"] == "gpt-image-1"
        assert inputs["prompt"] == "A majestic mountain landscape at sunset"

        # Verify output structure
        output = call.output
        assert len(output) == 2
        
        # First element should be the original response
        original_response, pil_image = output
        assert original_response.created == response.created
        
        # Second element should be PIL Image
        assert isinstance(pil_image, Image.Image)
        assert pil_image.size == (1024, 1024)

        # Verify usage tracking
        usage = call.summary["usage"]["gpt-image-1"]
        assert usage["requests"] == 1


def test_openai_image_postprocess_inputs():
    """Test input postprocessing function."""
    from weave.integrations.openai.gpt_image_utils import openai_image_postprocess_inputs
    
    test_inputs = {
        "model": "gpt-image-1",
        "prompt": "A test prompt",
    }
    
    result = openai_image_postprocess_inputs(test_inputs)
    
    # Should return inputs unchanged
    assert result == test_inputs


def test_openai_image_postprocess_outputs():
    """Test output postprocessing function."""
    from weave.integrations.openai.gpt_image_utils import openai_image_postprocess_outputs
    
    # Create a simple test image and convert to base64
    test_image = Image.new('RGB', (100, 100), color=(255, 0, 0))
    image_buffer = BytesIO()
    test_image.save(image_buffer, format='PNG')
    image_data = base64.b64encode(image_buffer.getvalue()).decode('utf-8')
    
    # Mock response structure
    class MockData:
        def __init__(self, b64_json):
            self.b64_json = b64_json
    
    class MockResponse:
        def __init__(self, b64_json):
            self.data = [MockData(b64_json)]
    
    mock_response = MockResponse(image_data)
    
    result = openai_image_postprocess_outputs(mock_response)
    
    # Should return tuple of (original_response, PIL_image)
    assert isinstance(result, tuple)
    assert len(result) == 2
    
    original_response, pil_image = result
    assert original_response == mock_response
    assert isinstance(pil_image, Image.Image)
    assert pil_image.size == (100, 100)


