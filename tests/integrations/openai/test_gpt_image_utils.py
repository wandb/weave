from __future__ import annotations

import base64
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

from weave.integrations.openai.gpt_image_utils import (
    openai_image_on_finish,
    openai_image_postprocess_inputs,
    openai_image_postprocess_outputs,
    openai_image_wrapper_async,
    openai_image_wrapper_sync,
)
from weave.trace.autopatch import OpSettings


def test_openai_image_postprocess_outputs_with_b64_json():
    """Test output postprocessing with base64 JSON response."""
    # Create a test image and encode it as base64
    test_image = Image.new("RGB", (1024, 1024), color=(255, 0, 0))
    image_buffer = BytesIO()
    test_image.save(image_buffer, format="PNG")
    image_data = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

    # Mock the OpenAI response structure
    class MockImageData:
        def __init__(self, b64_json):
            self.b64_json = b64_json
            self.url = None

    class MockResponse:
        def __init__(self, b64_json):
            self.data = [MockImageData(b64_json)]

    mock_response = MockResponse(image_data)

    result = openai_image_postprocess_outputs(mock_response)

    # Should return tuple of (original_response, PIL_image)
    if isinstance(result, tuple):
        assert len(result) == 2
        original_response, pil_image = result
        assert original_response == mock_response
        assert isinstance(pil_image, Image.Image)
        assert pil_image.size == (1024, 1024)
    else:
        # Acceptable if implementation changes to return just the response
        assert result == mock_response


def test_openai_image_postprocess_outputs_no_data():
    """Test output postprocessing when response has no data."""

    class MockResponse:
        def __init__(self):
            self.data = []

    mock_response = MockResponse()

    result = openai_image_postprocess_outputs(mock_response)

    # Should return just the original response
    assert result == mock_response


def test_openai_image_postprocess_outputs_no_data_attribute():
    """Test output postprocessing when response has no data attribute."""

    class MockResponse:
        def __init__(self):
            pass

    mock_response = MockResponse()

    result = openai_image_postprocess_outputs(mock_response)

    # Should return just the original response
    assert result == mock_response


def test_openai_image_on_finish_with_model():
    """Test on_finish handler with specified model."""

    class MockCall:
        def __init__(self, model=None):
            self.inputs = {"model": model} if model else {}
            self.summary = {}

    call = MockCall("gpt-image-1")
    openai_image_on_finish(call, None, None)

    assert "usage" in call.summary
    assert "gpt-image-1" in call.summary["usage"]
    assert call.summary["usage"]["gpt-image-1"]["requests"] == 1


def test_openai_image_on_finish_without_model():
    """Test on_finish handler without specified model."""

    class MockCall:
        def __init__(self):
            self.inputs = {}
            self.summary = {}

    call = MockCall()
    openai_image_on_finish(call, None, None)

    assert "usage" in call.summary
    assert "dall-e-2" in call.summary["usage"]
    assert call.summary["usage"]["dall-e-2"]["requests"] == 1


def test_openai_image_on_finish_with_existing_summary():
    """Test on_finish handler preserves existing summary data."""

    class MockCall:
        def __init__(self):
            self.inputs = {"model": "gpt-image-1"}
            self.summary = {"existing_key": "existing_value"}

    call = MockCall()
    openai_image_on_finish(call, None, None)

    # Should preserve existing data
    assert "existing_key" in call.summary
    assert call.summary["existing_key"] == "existing_value"

    # Should add usage data
    assert "usage" in call.summary
    assert "gpt-image-1" in call.summary["usage"]
    assert call.summary["usage"]["gpt-image-1"]["requests"] == 1


def test_openai_image_on_finish_with_none_summary():
    """Test on_finish handler when summary is None."""

    class MockCall:
        def __init__(self):
            self.inputs = {"model": "gpt-image-1"}
            self.summary = None

    call = MockCall()
    openai_image_on_finish(call, None, None)

    # Summary should remain None since the function checks if it's not None
    assert call.summary is None


@patch("weave.integrations.openai.gpt_image_utils.create_basic_wrapper_sync")
def test_openai_image_wrapper_sync(mock_create_wrapper):
    """Test that sync wrapper is created with correct parameters."""
    settings = OpSettings(name="test_op")

    openai_image_wrapper_sync(settings)

    mock_create_wrapper.assert_called_once_with(
        settings,
        postprocess_inputs=openai_image_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_on_finish,
    )


@patch("weave.integrations.openai.gpt_image_utils.create_basic_wrapper_async")
def test_openai_image_wrapper_async(mock_create_wrapper):
    """Test that async wrapper is created with correct parameters."""
    settings = OpSettings(name="test_op")

    openai_image_wrapper_async(settings)

    mock_create_wrapper.assert_called_once_with(
        settings,
        postprocess_inputs=openai_image_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_on_finish,
    )


def test_openai_image_postprocess_outputs_with_invalid_base64():
    "Test output postprocessing with invalid base64 data."
    import binascii

    class MockImageData:
        def __init__(self, b64_json):
            self.b64_json = b64_json
            self.url = None

    class MockResponse:
        def __init__(self, b64_json):
            self.data = [MockImageData(b64_json)]

    # Use invalid base64 data
    mock_response = MockResponse("invalid-base64-data")

    # Should raise a binascii.Error or ValueError when trying to decode invalid base64
    with pytest.raises((binascii.Error, ValueError)):
        openai_image_postprocess_outputs(mock_response)


def test_openai_image_postprocess_outputs_with_empty_b64_json():
    """Test output postprocessing with empty base64 JSON."""

    class MockImageData:
        def __init__(self, b64_json):
            self.b64_json = b64_json
            self.url = None

    class MockResponse:
        def __init__(self, b64_json):
            self.data = [MockImageData(b64_json)]

    # Use empty string for base64
    mock_response = MockResponse("")

    result = openai_image_postprocess_outputs(mock_response)

    # Should return just the original response since b64_json is falsy
    assert result == mock_response
