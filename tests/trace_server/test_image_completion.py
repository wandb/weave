"""Tests for image completion functionality.

This test suite verifies the image generation completion functionality including:
1. Image data processing from URLs and base64 data
2. LiteLLM integration for image generation
3. Content object creation and storage
4. Error handling and edge cases
"""

import base64
from unittest.mock import Mock, patch

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.image_completion import (
    _process_image_data_item,
    lite_llm_image_generation,
)


def test_process_url_image_success():
    """URL-based image data is fetched via Content.from_url and stored."""
    with (
        patch("weave.trace_server.image_completion.Content.from_url") as mock_from_url,
        patch("weave.trace_server.image_completion.store_content_object") as mock_store,
    ):
        mock_content = Mock()
        mock_from_url.return_value = mock_content
        mock_store.return_value = {"type": "Content", "digest": "abc123"}

        trace_server = Mock()
        result = _process_image_data_item(
            {"url": "https://example.com/image.png"},
            0,
            trace_server,
            "test-project",
            "user123",
        )

        mock_from_url.assert_called_once_with(
            "https://example.com/image.png",
            metadata={"source_index": 0, "_original_schema": "url"},
        )
        mock_store.assert_called_once_with(mock_content, "test-project", trace_server)
        assert result["url"] == {"type": "Content", "digest": "abc123"}
        assert "error" not in result


def test_process_base64_image_success():
    """Base64 image data is decoded via Content.from_base64 and stored."""
    b64_data = base64.b64encode(b"fake image data").decode("ascii")
    with (
        patch(
            "weave.trace_server.image_completion.Content.from_base64"
        ) as mock_from_base64,
        patch("weave.trace_server.image_completion.store_content_object") as mock_store,
    ):
        mock_content = Mock()
        mock_from_base64.return_value = mock_content
        mock_store.return_value = {"type": "Content", "digest": "def456"}

        trace_server = Mock()
        result = _process_image_data_item(
            {"b64_json": b64_data}, 1, trace_server, "test-project", "user123"
        )

        mock_from_base64.assert_called_once_with(
            b64_data,
            mimetype="image/png",
            metadata={"source_index": 1, "_original_schema": "b64_json"},
        )
        mock_store.assert_called_once_with(mock_content, "test-project", trace_server)
        assert result["b64_json"] == {"type": "Content", "digest": "def456"}
        assert "error" not in result


@pytest.mark.parametrize(
    ("trace_server", "project_id"),
    [(None, "test-project"), (Mock(), None)],
    ids=["no_trace_server", "no_project_id"],
)
def test_process_no_processing_when_unconfigured(trace_server, project_id):
    """Without both a trace server and project id, the data item is returned unchanged."""
    data_item = {"url": "https://example.com/image.png"}
    result = _process_image_data_item(data_item, 0, trace_server, project_id, "user123")
    assert result == {"url": "https://example.com/image.png"}
    assert "error" not in result


@pytest.mark.parametrize(
    ("patch_target", "data_item", "exc", "preserved_key"),
    [
        (
            "Content.from_url",
            {"url": "https://example.com/image.png"},
            Exception("Connection failed"),
            "url",
        ),
        (
            "Content.from_base64",
            {"b64_json": "invalid_base64_data!@#"},
            ValueError("Invalid base64 data"),
            "b64_json",
        ),
        (
            "Content.from_url",
            {"url": "https://example.com/image.png"},
            RuntimeError("Unexpected error"),
            "url",
        ),
    ],
    ids=["url_error", "base64_decode_error", "unexpected_error"],
)
def test_process_errors_return_str_and_preserve_original(
    patch_target, data_item, exc, preserved_key
):
    """Any failure surfaces ``str(exc)`` as ``error`` and leaves the original value in place."""
    original = data_item[preserved_key]
    with patch(f"weave.trace_server.image_completion.{patch_target}") as mock_fn:
        mock_fn.side_effect = exc
        result = _process_image_data_item(
            dict(data_item), 0, Mock(), "test-project", "user123"
        )
    assert result["error"] == str(exc)
    assert result[preserved_key] == original


def test_dalle3_successful_generation():
    """DALL-E 3 is pinned to n=1 with style/quality defaults and url response_format."""
    mock_response = Mock()
    mock_response.model_dump.return_value = {
        "data": [
            {"url": "https://example.com/generated1.png"},
            {"b64_json": "base64encodeddata"},
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
    }
    with (
        patch("litellm.image_generation") as mock_image_gen,
        patch(
            "weave.trace_server.image_completion._process_image_data_item"
        ) as mock_process,
    ):
        mock_image_gen.return_value = mock_response
        mock_process.side_effect = [
            {
                "url": "https://example.com/generated1.png",
                "content": {"digest": "abc123"},
            },
            {"b64_json": "base64encodeddata", "content": {"digest": "def456"}},
        ]

        result = lite_llm_image_generation(
            api_key="sk-test-key",
            inputs={"model": "dall-e-3", "prompt": "A beautiful sunset", "n": 2},
            trace_server=Mock(),
            project_id="test-project",
            wb_user_id="user123",
        )

        mock_image_gen.assert_called_once_with(
            model="dall-e-3",
            prompt="A beautiful sunset",
            api_key="sk-test-key",
            n=1,  # DALL-E 3 only supports n=1
            quality="standard",
            style="natural",
            size="1024x1024",
            response_format="url",
        )
        assert isinstance(result, tsi.ImageGenerationCreateRes)
        assert result.response["model"] == "dall-e-3"
        assert "data" in result.response
        assert len(result.response["data"]) == 2


def test_other_model_successful_generation():
    """Non-DALL-E models honor n and normalize input/output token usage keys."""
    mock_response = Mock()
    mock_response.model_dump.return_value = {
        "data": [{"url": "https://example.com/generated.png"}],
        "usage": {"input_tokens": 8, "output_tokens": 1, "total_tokens": 9},
    }
    with patch("litellm.image_generation") as mock_image_gen:
        mock_image_gen.return_value = mock_response
        result = lite_llm_image_generation(
            api_key="test-key",
            inputs={
                "model": "stable-diffusion-xl",
                "prompt": "A cat wearing a hat",
                "n": 3,
            },
        )

        mock_image_gen.assert_called_once_with(
            model="stable-diffusion-xl",
            prompt="A cat wearing a hat",
            api_key="test-key",
            n=3,  # Non-DALL-E 3 can support multiple images
            size="1024x1024",
            response_format="url",
        )
        assert result.response["usage"]["prompt_tokens"] == 8
        assert result.response["usage"]["completion_tokens"] == 1
        assert result.response["usage"]["total_tokens"] == 9


def test_gpt_image_1_generation():
    """gpt-image-1 uses high quality and omits the response_format parameter."""
    mock_response = Mock()
    mock_response.model_dump.return_value = {
        "data": [{"url": "https://example.com/generated.png"}]
    }
    with patch("litellm.image_generation") as mock_image_gen:
        mock_image_gen.return_value = mock_response
        lite_llm_image_generation(
            api_key="test-key",
            inputs={"model": "gpt-image-1", "prompt": "A robot painting"},
        )

        mock_image_gen.assert_called_once_with(
            model="gpt-image-1",
            prompt="A robot painting",
            api_key="test-key",
            n=1,
            quality="high",  # gpt-image-1 gets high quality
            size="1024x1024",
        )


def test_missing_model_error():
    """A missing model name raises InvalidRequest."""
    with pytest.raises(InvalidRequest, match="Model name is required"):
        lite_llm_image_generation(api_key="test-key", inputs={"prompt": "A test image"})


def test_litellm_exception_handling():
    """LiteLLM exceptions become an error response with the ``litellm.`` prefix stripped."""
    with patch("litellm.image_generation") as mock_image_gen:
        mock_image_gen.side_effect = Exception("litellm.APIError: Invalid API key")
        result = lite_llm_image_generation(
            api_key="invalid-key", inputs={"model": "dall-e-3", "prompt": "Test prompt"}
        )
        assert isinstance(result, tsi.ImageGenerationCreateRes)
        assert "error" in result.response
        assert "APIError: Invalid API key" in result.response["error"]
        assert "litellm." not in result.response["error"]


def test_image_generation_request_and_response_types():
    """ImageGenerationCreateReq/Res round-trip their fields."""
    req = tsi.ImageGenerationCreateReq(
        project_id="test-project",
        inputs=tsi.ImageGenerationRequestInputs(
            model="dall-e-3", prompt="A beautiful sunset", n=1
        ),
        track_llm_call=True,
    )
    assert req.project_id == "test-project"
    assert req.inputs.model == "dall-e-3"
    assert req.inputs.prompt == "A beautiful sunset"
    assert req.inputs.n == 1
    assert req.track_llm_call is True

    response_data = {
        "data": [{"url": "https://example.com/image.png"}],
        "model": "dall-e-3",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }
    res = tsi.ImageGenerationCreateRes(response=response_data, weave_call_id="call_123")
    assert res.response == response_data
    assert res.weave_call_id == "call_123"


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:6379/",
        "http://localhost:8123/",
        "file:///etc/passwd",
    ],
)
def test_unsafe_url_skips_from_url(unsafe_url):
    """Non-publicly-routable URLs in the provider response must not be fetched.

    URL classification itself is covered in tests/trace_server/test_url_safety.py;
    this checks that `_process_image_data_item` is wired to that gate.
    """
    with (
        patch("weave.trace_server.image_completion.Content.from_url") as mock_from_url,
        patch("weave.trace_server.image_completion.store_content_object") as mock_store,
    ):
        result = _process_image_data_item(
            {"url": unsafe_url}, 0, Mock(), "test-project", "user123"
        )
        mock_from_url.assert_not_called()
        mock_store.assert_not_called()
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__])
