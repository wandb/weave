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


class TestProcessImageDataItem:
    """Tests for _process_image_data_item function."""

    def test_process_url_image_success(self):
        """Test successful processing of URL-based image data."""
        # Mock Content.from_url to return a mock content object
        with (
            patch(
                "weave.trace_server.image_completion.Content.from_url"
            ) as mock_from_url,
            patch(
                "weave.trace_server.image_completion.store_content_object"
            ) as mock_store,
        ):
            mock_content = Mock()
            mock_from_url.return_value = mock_content
            mock_store.return_value = {"type": "Content", "digest": "abc123"}

            data_item = {"url": "https://example.com/image.png"}
            trace_server = Mock()
            project_id = "test-project"

            result = _process_image_data_item(
                data_item, 0, trace_server, project_id, "user123"
            )

            # Verify Content.from_url was called with correct parameters
            mock_from_url.assert_called_once_with(
                "https://example.com/image.png",
                metadata={"source_index": 0, "_original_schema": "url"},
            )

            # Verify store_content_object was called
            mock_store.assert_called_once_with(mock_content, project_id, trace_server)

            # Verify the result contains the content dict
            assert result["url"] == {"type": "Content", "digest": "abc123"}
            assert "error" not in result

    def test_process_base64_image_success(self):
        """Test successful processing of base64 image data."""
        # Create valid base64 image data
        test_image_data = b"fake image data"
        b64_data = base64.b64encode(test_image_data).decode("ascii")

        with (
            patch(
                "weave.trace_server.image_completion.Content.from_base64"
            ) as mock_from_base64,
            patch(
                "weave.trace_server.image_completion.store_content_object"
            ) as mock_store,
        ):
            mock_content = Mock()
            mock_from_base64.return_value = mock_content
            mock_store.return_value = {"type": "Content", "digest": "def456"}

            data_item = {"b64_json": b64_data}
            trace_server = Mock()
            project_id = "test-project"

            result = _process_image_data_item(
                data_item, 1, trace_server, project_id, "user123"
            )

            # Verify Content.from_base64 was called with correct parameters
            mock_from_base64.assert_called_once_with(
                b64_data,
                mimetype="image/png",
                metadata={"source_index": 1, "_original_schema": "b64_json"},
            )

            # Verify store_content_object was called
            mock_store.assert_called_once_with(mock_content, project_id, trace_server)

            # Verify the result contains the content dict
            assert result["b64_json"] == {"type": "Content", "digest": "def456"}
            assert "error" not in result

    def test_process_no_trace_server(self):
        """Test that no processing occurs when trace_server is None."""
        data_item = {"url": "https://example.com/image.png"}

        result = _process_image_data_item(data_item, 0, None, "test-project", "user123")

        # Should return original data unchanged
        assert result == {"url": "https://example.com/image.png"}
        assert "error" not in result

    def test_process_no_project_id(self):
        """Test that no processing occurs when project_id is None."""
        data_item = {"url": "https://example.com/image.png"}
        trace_server = Mock()

        result = _process_image_data_item(data_item, 0, trace_server, None, "user123")

        # Should return original data unchanged
        assert result == {"url": "https://example.com/image.png"}
        assert "error" not in result

    def test_process_url_error(self):
        """Test handling of errors when fetching URL-based images."""
        with patch(
            "weave.trace_server.image_completion.Content.from_url"
        ) as mock_from_url:
            mock_from_url.side_effect = Exception("Connection failed")

            data_item = {"url": "https://example.com/image.png"}
            trace_server = Mock()
            project_id = "test-project"

            result = _process_image_data_item(
                data_item, 0, trace_server, project_id, "user123"
            )

            # Should contain error information
            assert "error" in result
            assert result["error"] == "Connection failed"  # Returns str(e) directly
            # Original URL should still be present
            assert result["url"] == "https://example.com/image.png"

    def test_process_base64_decode_error(self):
        """Test handling of base64 decoding errors."""
        with patch(
            "weave.trace_server.image_completion.Content.from_base64"
        ) as mock_from_base64:
            mock_from_base64.side_effect = ValueError("Invalid base64 data")

            data_item = {"b64_json": "invalid_base64_data!@#"}
            trace_server = Mock()
            project_id = "test-project"

            result = _process_image_data_item(
                data_item, 0, trace_server, project_id, "user123"
            )

            # Should contain error information
            assert "error" in result
            assert result["error"] == "Invalid base64 data"  # Returns str(e) directly
            # Original b64_json should still be present
            assert result["b64_json"] == "invalid_base64_data!@#"

    def test_process_unexpected_error(self):
        """Test handling of unexpected errors during processing."""
        with patch(
            "weave.trace_server.image_completion.Content.from_url"
        ) as mock_from_url:
            mock_from_url.side_effect = RuntimeError("Unexpected error")

            data_item = {"url": "https://example.com/image.png"}
            trace_server = Mock()
            project_id = "test-project"

            result = _process_image_data_item(
                data_item, 0, trace_server, project_id, "user123"
            )

            # Should contain generic error message
            assert "error" in result
            assert result["error"] == "Unexpected error"  # Returns str(e) directly


class TestLiteLLMImageGeneration:
    """Tests for lite_llm_image_generation function."""

    def test_dalle3_successful_generation(self):
        """Test successful image generation with DALL-E 3."""
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

            inputs = {"model": "dall-e-3", "prompt": "A beautiful sunset", "n": 2}

            result = lite_llm_image_generation(
                api_key="sk-test-key",
                inputs=inputs,
                trace_server=Mock(),
                project_id="test-project",
                wb_user_id="user123",
            )

            # Verify the API call was made with correct parameters
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

            # Verify the response structure
            assert isinstance(result, tsi.ImageGenerationCreateRes)
            assert result.response["model"] == "dall-e-3"
            assert "data" in result.response
            assert len(result.response["data"]) == 2

    def test_other_model_successful_generation(self):
        """Test successful image generation with non-DALL-E model."""
        mock_response = Mock()
        mock_response.model_dump.return_value = {
            "data": [{"url": "https://example.com/generated.png"}],
            "usage": {"input_tokens": 8, "output_tokens": 1, "total_tokens": 9},
        }

        with patch("litellm.image_generation") as mock_image_gen:
            mock_image_gen.return_value = mock_response

            inputs = {
                "model": "stable-diffusion-xl",
                "prompt": "A cat wearing a hat",
                "n": 3,
            }

            result = lite_llm_image_generation(api_key="test-key", inputs=inputs)

            # Verify the API call was made with correct parameters
            mock_image_gen.assert_called_once_with(
                model="stable-diffusion-xl",
                prompt="A cat wearing a hat",
                api_key="test-key",
                n=3,  # Non-DALL-E 3 can support multiple images
                size="1024x1024",
                response_format="url",
            )

            # Verify usage token normalization
            assert result.response["usage"]["prompt_tokens"] == 8
            assert result.response["usage"]["completion_tokens"] == 1
            assert result.response["usage"]["total_tokens"] == 9

    def test_gpt_image_1_generation(self):
        """Test image generation with gpt-image-1 model (no response_format parameter)."""
        mock_response = Mock()
        mock_response.model_dump.return_value = {
            "data": [{"url": "https://example.com/generated.png"}]
        }

        with patch("litellm.image_generation") as mock_image_gen:
            mock_image_gen.return_value = mock_response

            inputs = {"model": "gpt-image-1", "prompt": "A robot painting"}

            result = lite_llm_image_generation(api_key="test-key", inputs=inputs)

            # Verify the API call was made without response_format parameter
            mock_image_gen.assert_called_once_with(
                model="gpt-image-1",
                prompt="A robot painting",
                api_key="test-key",
                n=1,
                quality="high",  # gpt-image-1 gets high quality
                size="1024x1024",
                # Note: no response_format parameter for gpt-image-1
            )

    def test_missing_model_error(self):
        """Test error handling when model is not specified."""
        inputs = {"prompt": "A test image"}

        with pytest.raises(InvalidRequest, match="Model name is required"):
            lite_llm_image_generation(api_key="test-key", inputs=inputs)

    def test_litellm_exception_handling(self):
        """Test error handling when LiteLLM raises an exception."""
        with patch("litellm.image_generation") as mock_image_gen:
            mock_image_gen.side_effect = Exception("litellm.APIError: Invalid API key")

            inputs = {"model": "dall-e-3", "prompt": "Test prompt"}

            result = lite_llm_image_generation(api_key="invalid-key", inputs=inputs)

            # Should return error response with cleaned error message
            assert isinstance(result, tsi.ImageGenerationCreateRes)
            assert "error" in result.response
            assert "APIError: Invalid API key" in result.response["error"]
            assert "litellm." not in result.response["error"]  # Should be stripped


class TestRequestResponseTypes:
    """Tests for request and response type validation."""

    def test_image_generation_request_creation(self):
        """Test creating ImageGenerationCreateReq with valid inputs."""
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

    def test_image_generation_response_creation(self):
        """Test creating ImageGenerationCreateRes with response data."""
        response_data = {
            "data": [{"url": "https://example.com/image.png"}],
            "model": "dall-e-3",
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        }

        res = tsi.ImageGenerationCreateRes(
            response=response_data, weave_call_id="call_123"
        )

        assert res.response == response_data
        assert res.weave_call_id == "call_123"


if __name__ == "__main__":
    pytest.main([__file__])
