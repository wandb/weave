"""
Unit tests for langchain integration helpers.

Tests the usage metadata extraction and processing functions that handle
different provider formats (OpenAI, Google GenAI, Google Vertex AI, Anthropic).
"""

from unittest.mock import Mock

import pytest

from weave.integrations.langchain.helpers import (
    ModelTokenCounts,
    TokenCounts,
    _extract_model_from_flattened_path,
    _extract_usage_data,
    _extract_usage_from_generation,
    _find_generation_paths,
    _is_valid_usage_shape,
    _normalize_token_counts,
    _reconstruct_usage_data_from_flattened,
)
from weave.trace.weave_client import Call


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        # OpenAI format
        (
            {
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
            },
            {
                "gpt-4o-mini": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                }
            },
        ),
        # Google GenAI format
        (
            {
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
            },
            {
                "gemini-1.5-pro": {
                    "prompt_tokens": 20,
                    "completion_tokens": 7,
                    "total_tokens": 27,
                }
            },
        ),
        # Google Vertex AI format
        (
            {
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
            },
            {
                "gemini-2.5-pro-preview": {
                    "prompt_tokens": 15,
                    "completion_tokens": 8,
                    "total_tokens": 23,
                }
            },
        ),
        # Batch aggregation - multiple outputs with same model
        (
            {
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
            },
            {
                "gpt-4o-mini": {
                    "prompt_tokens": 22,
                    "completion_tokens": 13,
                    "total_tokens": 35,
                }
            },
        ),
        # Multiple generations within single output
        (
            {
                "outputs": [
                    {
                        "generations": [
                            [
                                {
                                    "message": {
                                        "kwargs": {
                                            "usage_metadata": {
                                                "input_tokens": 25,
                                                "output_tokens": 10,
                                                "total_tokens": 35,
                                            }
                                        }
                                    },
                                    "generation_info": {"model_name": "gemini-1.5-pro"},
                                },
                                {
                                    "message": {
                                        "kwargs": {
                                            "usage_metadata": {
                                                "input_tokens": 15,
                                                "output_tokens": 8,
                                                "total_tokens": 23,
                                            }
                                        }
                                    },
                                    "generation_info": {"model_name": "gemini-1.5-pro"},
                                },
                            ]
                        ]
                    }
                ]
            },
            {
                "gemini-1.5-pro": {
                    "prompt_tokens": 40,
                    "completion_tokens": 18,
                    "total_tokens": 58,
                }
            },
        ),
    ],
)
def test_extract_usage_data(output, expected):
    """Test main usage extraction function with various provider formats."""
    call = Mock(spec=Call)
    call.summary = None
    _extract_usage_data(call, output)
    assert call.summary is not None
    assert "usage" in call.summary
    assert call.summary["usage"] == expected


def test_extract_usage_data_no_outputs():
    """Test that no usage data is extracted when outputs are missing or empty."""
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


def test_extract_usage_data_preserves_existing_summary():
    """Test that existing call summary data is preserved when adding usage data."""
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


@pytest.mark.parametrize(
    ("flattened", "base_path", "expected"),
    [
        # OpenAI format
        (
            {
                "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
                "outputs.0.generations.0.0.message.kwargs.token_usage.completion_tokens": 5,
                "outputs.0.generations.0.0.message.kwargs.token_usage.total_tokens": 15,
                "other.unrelated.key": "value",
            },
            "outputs.0.generations.0.0.message.kwargs.token_usage",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        ),
        # Google GenAI format
        (
            {
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 20,
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.output_tokens": 7,
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.total_tokens": 27,
            },
            "outputs.0.generations.0.0.message.kwargs.usage_metadata",
            {"input_tokens": 20, "output_tokens": 7, "total_tokens": 27},
        ),
        # Google Vertex AI format
        (
            {
                "outputs.0.generation_info.usage_metadata.prompt_token_count": 15,
                "outputs.0.generation_info.usage_metadata.candidates_token_count": 8,
                "outputs.0.generation_info.usage_metadata.total_token_count": 23,
            },
            "outputs.0.generation_info.usage_metadata",
            {
                "prompt_token_count": 15,
                "candidates_token_count": 8,
                "total_token_count": 23,
            },
        ),
        # Ignores nested structures
        (
            {
                "outputs.0.usage_metadata.input_tokens": 20,
                "outputs.0.usage_metadata.nested.deep.value": "ignored",
                "outputs.0.usage_metadata.output_tokens": 7,
            },
            "outputs.0.usage_metadata",
            {"input_tokens": 20, "output_tokens": 7},
        ),
        # Handles float values
        (
            {
                "outputs.0.usage_metadata.input_tokens": 20.5,
                "outputs.0.usage_metadata.output_tokens": 7.2,
            },
            "outputs.0.usage_metadata",
            {"input_tokens": 20, "output_tokens": 7},
        ),
    ],
)
def test_reconstruct_usage_data_from_flattened(flattened, base_path, expected):
    """Test reconstruction of usage data from flattened key-value pairs."""
    result = _reconstruct_usage_data_from_flattened(flattened, base_path)
    assert result == expected


@pytest.mark.parametrize(
    ("usage_data", "expected"),
    [
        # Valid OpenAI format
        ({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, True),
        # Valid Google GenAI format
        ({"input_tokens": 20, "output_tokens": 7, "total_tokens": 27}, True),
        # Valid Google Vertex AI format
        (
            {
                "prompt_token_count": 15,
                "candidates_token_count": 8,
                "total_token_count": 23,
            },
            True,
        ),
        # OpenAI without total (still valid)
        ({"prompt_tokens": 10, "completion_tokens": 5}, True),
        # Google GenAI without total (still valid)
        ({"input_tokens": 20, "output_tokens": 7}, True),
        # Incomplete OpenAI (missing completion_tokens)
        ({"prompt_tokens": 10}, False),
        # Incomplete Google GenAI (missing output_tokens)
        ({"input_tokens": 20}, False),
        # Incomplete Vertex AI (missing candidates_token_count)
        ({"prompt_token_count": 15}, False),
        # Unknown format
        ({"unknown_tokens": 10, "other_tokens": 5}, False),
        # Non-dict inputs
        ("not a dict", False),
        (None, False),
        (123, False),
        ([], False),
        # Empty dict
        ({}, False),
    ],
)
def test_is_valid_usage_shape(usage_data, expected):
    """Test validation of usage data shapes for different providers."""
    result = _is_valid_usage_shape(usage_data)
    assert result == expected


@pytest.mark.parametrize(
    ("usage_data", "expected_prompt", "expected_completion", "expected_total"),
    [
        # OpenAI format
        ({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, 10, 5, 15),
        # Google GenAI format
        ({"input_tokens": 20, "output_tokens": 7, "total_tokens": 27}, 20, 7, 27),
        # Google Vertex AI format
        (
            {
                "prompt_token_count": 15,
                "candidates_token_count": 8,
                "total_token_count": 23,
            },
            15,
            8,
            23,
        ),
        # OpenAI without total_tokens
        ({"prompt_tokens": 10, "completion_tokens": 5}, 10, 5, 0),
        # Google GenAI without total_tokens
        ({"input_tokens": 20, "output_tokens": 7}, 20, 7, 0),
        # Empty dict
        ({}, 0, 0, 0),
        # None values should be treated as 0
        ({"prompt_tokens": None, "completion_tokens": 5, "total_tokens": 15}, 0, 5, 15),
        ({"input_tokens": 20, "output_tokens": None, "total_tokens": 20}, 20, 0, 20),
        # Zero values
        ({"prompt_tokens": 0, "completion_tokens": 5, "total_tokens": 5}, 0, 5, 5),
    ],
)
def test_normalize_token_counts(
    usage_data, expected_prompt, expected_completion, expected_total
):
    """Test normalization of token counts from different provider formats."""
    token_counts = _normalize_token_counts(usage_data)
    assert token_counts.prompt_tokens == expected_prompt
    assert token_counts.completion_tokens == expected_completion
    assert token_counts.total_tokens == expected_total


@pytest.mark.parametrize(
    ("flattened", "usage_key_path", "expected"),
    [
        # generation_info.model_name (preferred location)
        (
            {
                "outputs.0.generations.0.0.generation_info.model_name": "gpt-4o-mini",
                "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            },
            "outputs.0.generations.0.0.message.kwargs.token_usage",
            "gpt-4o-mini",
        ),
        # response_metadata.model_name
        (
            {
                "outputs.0.generations.0.response_metadata.model_name": "gemini-1.5-pro",
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 20,
            },
            "outputs.0.generations.0.0.message.kwargs.usage_metadata",
            "gemini-1.5-pro",
        ),
        # broader search pattern
        (
            {
                "outputs.0.some.custom.path.model_name": "claude-opus-4",
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 25,
            },
            "outputs.0.generations.0.0.message.kwargs.usage_metadata",
            "claude-opus-4",
        ),
        # ignores empty string values
        (
            {
                "outputs.0.generations.0.0.generation_info.model_name": "",
                "outputs.0.generations.0.response_metadata.model_name": "gpt-4o-mini",
                "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            },
            "outputs.0.generations.0.0.message.kwargs.token_usage",
            "gpt-4o-mini",
        ),
        # ignores non-string values
        (
            {
                "outputs.0.generations.0.0.generation_info.model_name": 123,
                "outputs.0.generations.0.response_metadata.model_name": "gpt-4o-mini",
                "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            },
            "outputs.0.generations.0.0.message.kwargs.token_usage",
            "gpt-4o-mini",
        ),
        # fallback to unknown when no model found
        (
            {
                "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
                "other.unrelated.key": "value",
            },
            "outputs.0.generations.0.0.message.kwargs.token_usage",
            "unknown",
        ),
        # prioritizes generation_info over response_metadata
        (
            {
                "outputs.0.generations.0.0.generation_info.model_name": "preferred-model",
                "outputs.0.generations.0.response_metadata.model_name": "fallback-model",
                "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
            },
            "outputs.0.generations.0.0.message.kwargs.token_usage",
            "preferred-model",
        ),
    ],
)
def test_extract_model_from_flattened_path(flattened, usage_key_path, expected):
    """Test extraction of model names from flattened response structures."""
    result = _extract_model_from_flattened_path(flattened, usage_key_path)
    assert result == expected


@pytest.mark.parametrize(
    ("flattened", "expected"),
    [
        # Simple single generation
        (
            {
                "outputs.0.generations.0.0.message.content": "Hello",
                "outputs.0.generations.0.0.generation_info.model_name": "gpt-4",
            },
            ["outputs.0.generations.0.0"],
        ),
        # Multiple generations in same output
        (
            {
                "outputs.0.generations.0.0.message.content": "Hello",
                "outputs.0.generations.0.1.message.content": "World",
                "outputs.0.generations.0.0.generation_info.model_name": "gpt-4",
            },
            ["outputs.0.generations.0.0", "outputs.0.generations.0.1"],
        ),
        # Multiple outputs with generations
        (
            {
                "outputs.0.generations.0.0.message.content": "Hello",
                "outputs.1.generations.0.0.message.content": "World",
                "outputs.0.generations.0.0.generation_info.model_name": "gpt-4",
            },
            ["outputs.0.generations.0.0", "outputs.1.generations.0.0"],
        ),
        # No generations pattern
        (
            {
                "outputs.0.message.content": "Hello",
                "outputs.0.model_name": "gpt-4",
            },
            [],
        ),
        # Incomplete generation path (should be ignored)
        (
            {
                "outputs.0.generations.0.incomplete": "data",
                "outputs.0.generations.0.0.message.content": "Hello",
            },
            ["outputs.0.generations.0.0"],
        ),
        # Empty input
        ({}, []),
    ],
)
def test_find_generation_paths(flattened, expected):
    """Test finding generation paths in flattened LangChain results."""
    result = _find_generation_paths(flattened)
    assert result == expected


@pytest.mark.parametrize(
    ("flattened", "generation_path", "expected_tokens", "expected_model"),
    [
        # OpenAI format in generation
        (
            {
                "outputs.0.generations.0.0.message.kwargs.token_usage.prompt_tokens": 10,
                "outputs.0.generations.0.0.message.kwargs.token_usage.completion_tokens": 5,
                "outputs.0.generations.0.0.message.kwargs.token_usage.total_tokens": 15,
                "outputs.0.generations.0.0.generation_info.model_name": "gpt-4o-mini",
            },
            "outputs.0.generations.0.0",
            TokenCounts(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            "gpt-4o-mini",
        ),
        # Google GenAI format in generation
        (
            {
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 20,
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.output_tokens": 7,
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.total_tokens": 27,
                "outputs.0.generations.0.0.generation_info.model_name": "gemini-1.5-pro",
            },
            "outputs.0.generations.0.0",
            TokenCounts(prompt_tokens=20, completion_tokens=7, total_tokens=27),
            "gemini-1.5-pro",
        ),
        # Vertex AI format with generation_info priority
        (
            {
                "outputs.0.generations.0.0.generation_info.usage_metadata.prompt_token_count": 15,
                "outputs.0.generations.0.0.generation_info.usage_metadata.candidates_token_count": 8,
                "outputs.0.generations.0.0.generation_info.usage_metadata.total_token_count": 23,
                "outputs.0.generations.0.0.message.kwargs.usage_metadata.prompt_token_count": 99,  # Should be ignored
                "outputs.0.generations.0.0.generation_info.model_name": "gemini-pro",
            },
            "outputs.0.generations.0.0",
            TokenCounts(prompt_tokens=15, completion_tokens=8, total_tokens=23),
            "gemini-pro",
        ),
        # No usage data in generation
        (
            {
                "outputs.0.generations.0.0.message.content": "Hello",
                "outputs.0.generations.0.0.generation_info.model_name": "gpt-4",
            },
            "outputs.0.generations.0.0",
            TokenCounts(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            "gpt-4",
        ),
    ],
)
def test_extract_usage_from_generation(
    flattened, generation_path, expected_tokens, expected_model
):
    """Test extraction of usage data from a specific generation path."""
    result = _extract_usage_from_generation(flattened, generation_path)

    assert result.prompt_tokens == expected_tokens.prompt_tokens
    assert result.completion_tokens == expected_tokens.completion_tokens
    assert result.total_tokens == expected_tokens.total_tokens
    assert result.model_name == expected_model


def test_extract_usage_from_generation_empty():
    """Test that empty ModelTokenCounts is returned when no usage data found."""
    flattened = {
        "outputs.0.generations.0.0.message.content": "Hello",
        "other.unrelated.key": "value",
    }
    result = _extract_usage_from_generation(flattened, "outputs.0.generations.0.0")

    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    assert result.total_tokens == 0
    assert result.model_name == "unknown"


def test_model_token_counts_validation():
    """Test ModelTokenCounts validation logic."""
    # Valid cases
    valid_cases = [
        ModelTokenCounts(
            prompt_tokens=10, completion_tokens=5, total_tokens=15, model_name="gpt-4"
        ),
        ModelTokenCounts(
            prompt_tokens=0, completion_tokens=5, total_tokens=5, model_name="gpt-4"
        ),
        ModelTokenCounts(
            prompt_tokens=10, completion_tokens=0, total_tokens=10, model_name="gpt-4"
        ),
    ]

    for case in valid_cases:
        # Check that we have meaningful token counts (prompt or completion tokens > 0)
        has_meaningful_tokens = case.prompt_tokens > 0 or case.completion_tokens > 0
        assert has_meaningful_tokens, f"Expected {case} to have meaningful token counts"

    # Cases without meaningful token counts (both prompt and completion tokens are 0)
    no_meaningful_tokens_cases = [
        ModelTokenCounts(
            prompt_tokens=0, completion_tokens=0, total_tokens=0, model_name="gpt-4"
        ),
        ModelTokenCounts(
            prompt_tokens=0, completion_tokens=0, total_tokens=1, model_name="gpt-4"
        ),
    ]

    for case in no_meaningful_tokens_cases:
        # Check that we don't have meaningful token counts (no prompt or completion tokens > 0)
        has_meaningful_tokens = case.prompt_tokens > 0 or case.completion_tokens > 0
        assert (
            not has_meaningful_tokens
        ), f"Expected {case} to not have meaningful token counts"


def test_model_token_counts_from_usage_data():
    """Test ModelTokenCounts creation from usage data."""
    # OpenAI format
    openai_data = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    result = ModelTokenCounts.from_usage_data(openai_data, "gpt-4")
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens == 15
    assert result.model_name == "gpt-4"
    # Check that we have meaningful token counts (prompt or completion tokens > 0)
    assert result.prompt_tokens > 0 or result.completion_tokens > 0

    # Google GenAI format
    genai_data = {"input_tokens": 20, "output_tokens": 7, "total_tokens": 27}
    result = ModelTokenCounts.from_usage_data(genai_data, "gemini-1.5-pro")
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 7
    assert result.total_tokens == 27
    assert result.model_name == "gemini-1.5-pro"
    # Check that we have meaningful token counts (prompt or completion tokens > 0)
    assert result.prompt_tokens > 0 or result.completion_tokens > 0

    # Empty data
    empty_result = ModelTokenCounts.from_usage_data({}, "unknown")
    # Check that we don't have meaningful token counts (no prompt or completion tokens > 0)
    assert not (empty_result.prompt_tokens > 0 or empty_result.completion_tokens > 0)


def test_model_token_counts_empty():
    """Test ModelTokenCounts.empty() factory method."""
    empty = ModelTokenCounts.empty("test-model")
    assert empty.prompt_tokens == 0
    assert empty.completion_tokens == 0
    assert empty.total_tokens == 0
    assert empty.model_name == "test-model"
    # Check that we don't have meaningful token counts (no prompt or completion tokens > 0)
    assert not (empty.prompt_tokens > 0 or empty.completion_tokens > 0)


def test_extract_usage_data_with_deduplication():
    """Test that usage data deduplication works correctly in complex scenarios."""
    # Vertex AI often duplicates usage data in generation_info and message.kwargs
    # The new implementation should prefer generation_info and avoid double-counting
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
                                "model_name": "gemini-pro",
                                "usage_metadata": {
                                    "prompt_token_count": 15,  # Same data - should not double count
                                    "candidates_token_count": 8,
                                    "total_token_count": 23,
                                },
                            },
                        }
                    ]
                ]
            }
        ]
    }

    call = Mock(spec=Call)
    call.summary = None
    _extract_usage_data(call, output)

    expected = {
        "gemini-pro": {
            "prompt_tokens": 15,
            "completion_tokens": 8,
            "total_tokens": 23,
        }
    }

    assert call.summary["usage"] == expected


def test_extract_usage_data_fallback_mode():
    """Test fallback mode when no clear generation structure is found."""
    # This tests the fallback path in _extract_usage_data when generation_paths is empty
    output = {
        "outputs": [
            {
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
                "model_name": "gpt-4",
            }
        ]
    }

    call = Mock(spec=Call)
    call.summary = None
    _extract_usage_data(call, output)

    # Should still extract usage data via fallback mechanism
    assert call.summary is not None
    assert "usage" in call.summary
    # Model extraction might default to "unknown" in fallback mode
    assert "gpt-4" in call.summary["usage"] or "unknown" in call.summary["usage"]


def test_extract_usage_data_invalid_usage_shapes():
    """Test that invalid usage shapes are properly ignored."""
    output = {
        "outputs": [
            {
                "generations": [
                    [
                        {
                            "message": {
                                "kwargs": {
                                    "usage_metadata": {
                                        "invalid_field": 10,  # Invalid shape
                                        "another_invalid": 5,
                                    }
                                }
                            },
                            "generation_info": {"model_name": "gpt-4"},
                        }
                    ]
                ]
            }
        ]
    }

    call = Mock(spec=Call)
    call.summary = None
    _extract_usage_data(call, output)

    # Should not create usage data for invalid shapes
    assert call.summary is None


def test_extract_usage_data_mixed_models():
    """Test extraction with different models in same batch."""
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
                            "generation_info": {"model_name": "gpt-4"},
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
            },
        ]
    }

    call = Mock(spec=Call)
    call.summary = None
    _extract_usage_data(call, output)

    expected = {
        "gpt-4": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
        "gemini-1.5-pro": {
            "prompt_tokens": 20,
            "completion_tokens": 7,
            "total_tokens": 27,
        },
    }

    assert call.summary["usage"] == expected
