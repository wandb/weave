"""
Unit tests for langchain integration helpers.

Tests the usage metadata extraction and processing functions that handle
different provider formats (OpenAI, Google GenAI, Google Vertex AI, Anthropic).
"""

from unittest.mock import Mock

from weave.integrations.langchain.helpers import (
    _extract_model_from_flattened_path,
    _extract_usage_data,
    _normalize_token_counts,
    _reconstruct_usage_data_from_flattened,
    _is_valid_usage_shape,
)
from weave.trace.weave_client import Call


class TestExtractUsageData:
    """Test the main usage data extraction function."""

    def test_openai_format(self):
        """Test OpenAI token_usage format extraction."""
        call = Mock(spec=Call)
        call.summary = None

        output = {
            "outputs": [
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "token_usage": {
                                            "prompt_tokens": 10,
                                            "completion_tokens": 5,
                                            "total_tokens": 15,
                                        }
                                    }
                                },
                                "generation_info": {"model_name": "gpt-4o-mini"},
                            }
                        ]
                    ]
                }
            ]
        }

        _extract_usage_data(call, output)

        assert call.summary is not None
        assert "usage" in call.summary
        usage = call.summary["usage"]
        assert "gpt-4o-mini" in usage
        assert usage["gpt-4o-mini"]["prompt_tokens"] == 10
        assert usage["gpt-4o-mini"]["completion_tokens"] == 5
        assert usage["gpt-4o-mini"]["total_tokens"] == 15

    def test_google_genai_format(self):
        """Test Google GenAI usage_metadata format extraction."""
        call = Mock(spec=Call)
        call.summary = None

        output = {
            "outputs": [
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 20,
                                            "output_tokens": 7,
                                            "total_tokens": 27,
                                        }
                                    }
                                },
                                "generation_info": {"model_name": "gemini-1.5-pro"},
                            }
                        ]
                    ]
                }
            ]
        }

        _extract_usage_data(call, output)

        assert call.summary is not None
        assert "usage" in call.summary
        usage = call.summary["usage"]
        assert "gemini-1.5-pro" in usage
        assert usage["gemini-1.5-pro"]["prompt_tokens"] == 20
        assert usage["gemini-1.5-pro"]["completion_tokens"] == 7
        assert usage["gemini-1.5-pro"]["total_tokens"] == 27

    def test_google_vertex_ai_format(self):
        """Test Google Vertex AI usage_metadata format extraction."""
        call = Mock(spec=Call)
        call.summary = None

        output = {
            "outputs": [
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "prompt_token_count": 15,
                                            "candidates_token_count": 8,
                                            "total_token_count": 23,
                                        }
                                    }
                                },
                                "generation_info": {
                                    "model_name": "gemini-2.5-pro-preview"
                                },
                            }
                        ]
                    ]
                }
            ]
        }

        _extract_usage_data(call, output)

        assert call.summary is not None
        assert "usage" in call.summary
        usage = call.summary["usage"]
        assert "gemini-2.5-pro-preview" in usage
        assert usage["gemini-2.5-pro-preview"]["prompt_tokens"] == 15
        assert usage["gemini-2.5-pro-preview"]["completion_tokens"] == 8
        assert usage["gemini-2.5-pro-preview"]["total_tokens"] == 23

    def test_anthropic_format(self):
        """Test Anthropic usage format (uses input_tokens/output_tokens pattern)."""
        call = Mock(spec=Call)
        call.summary = None

        output = {
            "outputs": [
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 25,
                                            "output_tokens": 11,
                                            "total_tokens": 36,
                                        }
                                    }
                                },
                                "generation_info": {
                                    "model_name": "claude-opus-4-20250514"
                                },
                            }
                        ]
                    ]
                }
            ]
        }

        _extract_usage_data(call, output)

        assert call.summary is not None
        assert "usage" in call.summary
        usage = call.summary["usage"]
        assert "claude-opus-4-20250514" in usage
        assert usage["claude-opus-4-20250514"]["prompt_tokens"] == 25
        assert usage["claude-opus-4-20250514"]["completion_tokens"] == 11
        assert usage["claude-opus-4-20250514"]["total_tokens"] == 36

    def test_batch_operations_aggregation(self):
        """Test usage aggregation for batch operations with multiple outputs."""
        call = Mock(spec=Call)
        call.summary = None

        output = {
            "outputs": [
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "token_usage": {
                                            "prompt_tokens": 10,
                                            "completion_tokens": 5,
                                            "total_tokens": 15,
                                        }
                                    }
                                },
                                "generation_info": {"model_name": "gpt-4o-mini"},
                            }
                        ]
                    ]
                },
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "token_usage": {
                                            "prompt_tokens": 12,
                                            "completion_tokens": 8,
                                            "total_tokens": 20,
                                        }
                                    }
                                },
                                "generation_info": {"model_name": "gpt-4o-mini"},
                            }
                        ]
                    ]
                },
            ]
        }

        _extract_usage_data(call, output)

        assert call.summary is not None
        assert "usage" in call.summary
        usage = call.summary["usage"]
        assert "gpt-4o-mini" in usage
        # Should aggregate both requests
        assert usage["gpt-4o-mini"]["prompt_tokens"] == 22  # 10 + 12
        assert usage["gpt-4o-mini"]["completion_tokens"] == 13  # 5 + 8
        assert usage["gpt-4o-mini"]["total_tokens"] == 35  # 15 + 20

    def test_tuple_outputs_normalized(self):
        """Test that tuple outputs are converted to lists for processing."""
        call = Mock(spec=Call)
        call.summary = None

        output = {
            "outputs": (  # Tuple instead of list
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "token_usage": {
                                            "prompt_tokens": 10,
                                            "completion_tokens": 5,
                                            "total_tokens": 15,
                                        }
                                    }
                                },
                                "generation_info": {"model_name": "gpt-4o-mini"},
                            }
                        ]
                    ]
                },
            )
        }

        _extract_usage_data(call, output)

        assert call.summary is not None
        assert "usage" in call.summary
        usage = call.summary["usage"]
        assert "gpt-4o-mini" in usage

    def test_no_outputs_no_usage(self):
        """Test that no usage is extracted when outputs are missing or empty."""
        call = Mock(spec=Call)
        call.summary = None

        # Test None output
        _extract_usage_data(call, None)
        assert call.summary is None

        # Test empty outputs
        _extract_usage_data(call, {"outputs": []})
        assert call.summary is None

        # Test missing outputs key
        _extract_usage_data(call, {"other_key": "value"})
        assert call.summary is None

    def test_preserves_existing_summary(self):
        """Test that existing call summary is preserved when adding usage."""
        call = Mock(spec=Call)
        call.summary = {"existing_key": "existing_value"}

        output = {
            "outputs": [
                {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "token_usage": {
                                            "prompt_tokens": 10,
                                            "completion_tokens": 5,
                                            "total_tokens": 15,
                                        }
                                    }
                                },
                                "generation_info": {"model_name": "gpt-4o-mini"},
                            }
                        ]
                    ]
                }
            ]
        }

        _extract_usage_data(call, output)

        assert call.summary["existing_key"] == "existing_value"
        assert "usage" in call.summary


class TestReconstructUsageDataFromFlattened:
    """Test usage data reconstruction from flattened key-value pairs."""

    def test_reconstruct_openai_usage(self):
        """Test reconstructing OpenAI token_usage data."""
        flattened = {
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            "outputs.0.generations.0.0.message.kwargs.token_usage.completion_tokens": 5,
            "outputs.0.generations.0.0.message.kwargs.token_usage.total_tokens": 15,
            "other.unrelated.key": "value",
        }
        base_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _reconstruct_usage_data_from_flattened(flattened, base_path)

        assert result == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    def test_reconstruct_google_usage(self):
        """Test reconstructing Google usage_metadata data."""
        flattened = {
            "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 20,
            "outputs.0.generations.0.0.message.kwargs.usage_metadata.output_tokens": 7,
            "outputs.0.generations.0.0.message.kwargs.usage_metadata.total_tokens": 27,
        }
        base_path = "outputs.0.generations.0.0.message.kwargs.usage_metadata"

        result = _reconstruct_usage_data_from_flattened(flattened, base_path)

        assert result == {"input_tokens": 20, "output_tokens": 7, "total_tokens": 27}

    def test_ignores_nested_fields(self):
        """Test that nested fields within usage data are ignored."""
        flattened = {
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            "outputs.0.generations.0.0.message.kwargs.token_usage.nested.field": "ignored",
            "outputs.0.generations.0.0.message.kwargs.token_usage.completion_tokens": 5,
        }
        base_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _reconstruct_usage_data_from_flattened(flattened, base_path)

        assert result == {"prompt_tokens": 10, "completion_tokens": 5}

    def test_converts_float_to_int(self):
        """Test that float values are converted to integers."""
        flattened = {
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10.0,
            "outputs.0.generations.0.0.message.kwargs.token_usage.completion_tokens": 5.5,
        }
        base_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _reconstruct_usage_data_from_flattened(flattened, base_path)

        assert result == {"prompt_tokens": 10, "completion_tokens": 5}

    def test_ignores_non_numeric_values(self):
        """Test that non-numeric values are ignored."""
        flattened = {
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            "outputs.0.generations.0.0.message.kwargs.token_usage.model_name": "gpt-4",  # string ignored
            "outputs.0.generations.0.0.message.kwargs.token_usage.completion_tokens": 5,
        }
        base_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _reconstruct_usage_data_from_flattened(flattened, base_path)

        assert result == {"prompt_tokens": 10, "completion_tokens": 5}


class TestValidateUsageShape:
    """Test usage data validation for known provider formats."""

    def test_valid_openai_format(self):
        """Test OpenAI format validation."""
        usage_data = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        assert _is_valid_usage_shape(usage_data) is True

    def test_valid_google_genai_format(self):
        """Test Google GenAI format validation."""
        usage_data = {"input_tokens": 20, "output_tokens": 7, "total_tokens": 27}
        assert _is_valid_usage_shape(usage_data) is True

    def test_valid_google_vertex_format(self):
        """Test Google Vertex AI format validation."""
        usage_data = {
            "prompt_token_count": 15,
            "candidates_token_count": 8,
            "total_token_count": 23,
        }
        assert _is_valid_usage_shape(usage_data) is True

    def test_openai_format_without_total(self):
        """Test OpenAI format without total_tokens is still valid."""
        usage_data = {"prompt_tokens": 10, "completion_tokens": 5}
        assert _is_valid_usage_shape(usage_data) is True

    def test_invalid_partial_openai_format(self):
        """Test incomplete OpenAI format is invalid."""
        usage_data = {
            "prompt_tokens": 10
            # Missing completion_tokens
        }
        assert _is_valid_usage_shape(usage_data) is False

    def test_invalid_partial_google_format(self):
        """Test incomplete Google format is invalid."""
        usage_data = {
            "input_tokens": 20
            # Missing output_tokens
        }
        assert _is_valid_usage_shape(usage_data) is False

    def test_invalid_unknown_format(self):
        """Test unknown format is invalid."""
        usage_data = {"unknown_tokens": 10, "other_tokens": 5}
        assert _is_valid_usage_shape(usage_data) is False

    def test_invalid_non_dict(self):
        """Test non-dictionary input is invalid."""
        assert _is_valid_usage_shape("not a dict") is False
        assert _is_valid_usage_shape(None) is False
        assert _is_valid_usage_shape(123) is False


class TestNormalizeTokenCounts:
    """Test token count normalization from provider-specific fields."""

    def test_normalize_openai_format(self):
        """Test OpenAI format normalization."""
        usage_data = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        token_counts = _normalize_token_counts(usage_data)

        assert token_counts.prompt_tokens == 10
        assert token_counts.completion_tokens == 5
        assert token_counts.total_tokens == 15

    def test_normalize_google_genai_format(self):
        """Test Google GenAI format normalization."""
        usage_data = {"input_tokens": 20, "output_tokens": 7, "total_tokens": 27}

        token_counts = _normalize_token_counts(usage_data)

        assert token_counts.prompt_tokens == 20
        assert token_counts.completion_tokens == 7
        assert token_counts.total_tokens == 27

    def test_normalize_google_vertex_format(self):
        """Test Google Vertex AI format normalization."""
        usage_data = {
            "prompt_token_count": 15,
            "candidates_token_count": 8,
            "total_token_count": 23,
        }

        token_counts = _normalize_token_counts(usage_data)

        assert token_counts.prompt_tokens == 15
        assert token_counts.completion_tokens == 8
        assert token_counts.total_tokens == 23

    def test_normalize_missing_total_tokens(self):
        """Test normalization when total_tokens is missing."""
        usage_data = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            # Missing total_tokens
        }

        token_counts = _normalize_token_counts(usage_data)

        assert token_counts.prompt_tokens == 10
        assert token_counts.completion_tokens == 5
        assert token_counts.total_tokens == 0  # Default when missing

    def test_normalize_empty_data(self):
        """Test normalization with empty data."""
        usage_data = {}

        token_counts = _normalize_token_counts(usage_data)

        assert token_counts.prompt_tokens == 0
        assert token_counts.completion_tokens == 0
        assert token_counts.total_tokens == 0

    def test_normalize_handles_none_values(self):
        """Test normalization handles None values gracefully."""
        usage_data = {"prompt_tokens": None, "completion_tokens": 5, "total_tokens": 15}

        token_counts = _normalize_token_counts(usage_data)

        assert token_counts.prompt_tokens == 0  # None defaults to 0
        assert token_counts.completion_tokens == 5
        assert token_counts.total_tokens == 15


class TestExtractModelFromFlattened:
    """Test model name extraction from flattened response structure."""

    def test_extract_model_generation_info_pattern(self):
        """Test model extraction from generation_info.model_name pattern."""
        flattened = {
            "outputs.0.generations.0.0.generation_info.model_name": "gpt-4o-mini",
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
        }
        usage_key_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _extract_model_from_flattened_path(flattened, usage_key_path)

        assert result == "gpt-4o-mini"

    def test_extract_model_response_metadata_pattern(self):
        """Test model extraction from response_metadata.model_name pattern."""
        flattened = {
            "outputs.0.generations.0.response_metadata.model_name": "gemini-1.5-pro",
            "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 20,
        }
        usage_key_path = "outputs.0.generations.0.0.message.kwargs.usage_metadata"

        result = _extract_model_from_flattened_path(flattened, usage_key_path)

        assert result == "gemini-1.5-pro"

    def test_extract_model_broader_search(self):
        """Test model extraction falls back to broader search when patterns fail."""
        flattened = {
            "outputs.0.some.custom.path.model_name": "claude-opus-4",
            "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 25,
        }
        usage_key_path = "outputs.0.generations.0.0.message.kwargs.usage_metadata"

        result = _extract_model_from_flattened_path(flattened, usage_key_path)

        assert result == "claude-opus-4"

    def test_extract_model_ignores_empty_values(self):
        """Test that empty model names are ignored."""
        flattened = {
            "outputs.0.generations.0.0.generation_info.model_name": "",  # Empty string ignored
            "outputs.0.generations.0.response_metadata.model_name": "gpt-4o-mini",
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
        }
        usage_key_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _extract_model_from_flattened_path(flattened, usage_key_path)

        assert result == "gpt-4o-mini"

    def test_extract_model_ignores_non_string_values(self):
        """Test that non-string model names are ignored."""
        flattened = {
            "outputs.0.generations.0.0.generation_info.model_name": 123,  # Number ignored
            "outputs.0.generations.0.response_metadata.model_name": "gpt-4o-mini",
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
        }
        usage_key_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _extract_model_from_flattened_path(flattened, usage_key_path)

        assert result == "gpt-4o-mini"

    def test_extract_model_fallback_to_unknown(self):
        """Test fallback to 'unknown' when no model name is found."""
        flattened = {
            "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            "other.unrelated.key": "value",
        }
        usage_key_path = "outputs.0.generations.0.0.message.kwargs.token_usage"

        result = _extract_model_from_flattened_path(flattened, usage_key_path)

        assert result == "unknown"
