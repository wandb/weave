"""Unit tests for langchain integration helpers.

Tests the usage metadata extraction and processing functions that handle
different provider formats (OpenAI, Google GenAI, Google Vertex AI).
"""

from unittest.mock import Mock

import pytest

from weave.integrations.langchain.helpers import (
    TokenUsage,
    _extract_usage_data,
    _find_full_model_name,
    _normalize_usage_metadata,
)
from weave.trace.call import Call


@pytest.mark.parametrize(
    ("usage_metadata", "expected"),
    [
        # OpenAI format (real data structure)
        (
            {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
            TokenUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14),
        ),
        # Legacy OpenAI format
        (
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ),
        # Google GenAI format (real data structure)
        (
            {"input_tokens": 2, "output_tokens": 6, "total_tokens": 8},
            TokenUsage(prompt_tokens=2, completion_tokens=6, total_tokens=8),
        ),
        # Google Vertex AI format (legacy)
        (
            {
                "prompt_token_count": 15,
                "candidates_token_count": 8,
                "total_token_count": 23,
            },
            TokenUsage(prompt_tokens=15, completion_tokens=8, total_tokens=23),
        ),
        # Cohere format (real data shows input_tokens/output_tokens)
        (
            {"input_tokens": 497, "output_tokens": 6, "total_tokens": 503},
            TokenUsage(prompt_tokens=497, completion_tokens=6, total_tokens=503),
        ),
        # Empty metadata
        (
            {},
            TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        ),
        # None metadata
        (
            None,
            TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        ),
        # Partial data (missing total_tokens)
        (
            {"input_tokens": 10, "output_tokens": 3},
            TokenUsage(prompt_tokens=10, completion_tokens=3, total_tokens=0),
        ),
        # None values in metadata
        (
            {"input_tokens": None, "output_tokens": 5, "total_tokens": None},
            TokenUsage(prompt_tokens=0, completion_tokens=5, total_tokens=0),
        ),
    ],
)
def test_normalize_usage_metadata(usage_metadata, expected):
    """Test normalization of usage metadata from different provider formats."""
    result = _normalize_usage_metadata(usage_metadata)
    assert result.prompt_tokens == expected.prompt_tokens
    assert result.completion_tokens == expected.completion_tokens
    assert result.total_tokens == expected.total_tokens


@pytest.mark.parametrize(
    ("output", "partial_model", "expected"),
    [
        # Find longer model name
        (
            {"some_key": "gemini-1.5-pro-002", "other": "value"},
            "gemini-1.5-pro",
            "gemini-1.5-pro-002",
        ),
        # No better match found
        (
            {"some_key": "other-model", "other": "value"},
            "gemini-1.5-pro",
            "gemini-1.5-pro",
        ),
        # Empty/None inputs
        (
            None,
            "gemini-1.5-pro",
            "gemini-1.5-pro",
        ),
        (
            {},
            "",
            "",
        ),
        (
            {"key": "value"},
            "unknown",
            "unknown",
        ),
        # Non-string values ignored
        (
            {"model": 123, "other_model": "gemini-1.5-pro-002"},
            "gemini-1.5-pro",
            "gemini-1.5-pro-002",
        ),
    ],
)
def test_find_full_model_name(output, partial_model, expected):
    """Test finding full model names from flattened output."""
    result = _find_full_model_name(output, partial_model)
    assert result == expected


@pytest.mark.parametrize(
    ("output", "expected_usage"),
    [
        # OpenAI chat model format
        (
            {
                "extra": {
                    "metadata": {
                        "ls_provider": "openai",
                        "ls_model_name": "gpt-3.5-turbo",
                        "ls_model_type": "chat",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 10,
                                            "output_tokens": 4,
                                            "total_tokens": 14,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            {
                "gpt-3.5-turbo": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                }
            },
        ),
        # Cohere chat model format
        (
            {
                "extra": {
                    "metadata": {
                        "ls_provider": "cohere",
                        "ls_model_name": "command-a-03-2025",
                        "ls_model_type": "chat",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 497,
                                            "output_tokens": 6,
                                            "total_tokens": 503,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            {
                "command-a-03-2025": {
                    "prompt_tokens": 497,
                    "completion_tokens": 6,
                    "total_tokens": 503,
                }
            },
        ),
        # Anthropic chat model format
        (
            {
                "extra": {
                    "metadata": {
                        "ls_provider": "anthropic",
                        "ls_model_name": "claude-3-5-sonnet-20240620",
                        "ls_model_type": "chat",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 9,
                                            "output_tokens": 7,
                                            "total_tokens": 16,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            {
                "claude-3-5-sonnet-20240620": {
                    "prompt_tokens": 9,
                    "completion_tokens": 7,
                    "total_tokens": 16,
                }
            },
        ),
        # Google GenAI chat model format
        (
            {
                "extra": {
                    "metadata": {
                        "ls_provider": "google_genai",
                        "ls_model_name": "gemini-1.5-flash",
                        "ls_model_type": "chat",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 2,
                                            "output_tokens": 6,
                                            "total_tokens": 8,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            {
                "gemini-1.5-flash": {
                    "prompt_tokens": 2,
                    "completion_tokens": 6,
                    "total_tokens": 8,
                }
            },
        ),
        # Google GenAI LLM model format
        (
            {
                "extra": {
                    "metadata": {
                        "ls_provider": "google_genai",
                        "ls_model_name": "gemini-1.5-flash",
                        "ls_model_type": "llm",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "generation_info": {
                                    "usage_metadata": {
                                        "input_tokens": 4,
                                        "output_tokens": 6,
                                        "total_tokens": 10,
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            {
                "gemini-1.5-flash": {
                    "prompt_tokens": 4,
                    "completion_tokens": 6,
                    "total_tokens": 10,
                }
            },
        ),
        # LiteLLM chat model format
        (
            {
                "extra": {
                    "metadata": {
                        "ls_provider": "litellm",
                        "ls_model_name": "gpt-4.1-nano",
                        "ls_model_type": "chat",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 10,
                                            "output_tokens": 3,
                                            "total_tokens": 13,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            {
                "gpt-4.1-nano": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "total_tokens": 13,
                }
            },
        ),
        # Multiple generations aggregated (OpenAI example)
        (
            {
                "extra": {
                    "metadata": {
                        "ls_provider": "openai",
                        "ls_model_name": "gpt-4",
                        "ls_model_type": "chat",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 10,
                                            "output_tokens": 5,
                                            "total_tokens": 15,
                                        }
                                    }
                                }
                            },
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "input_tokens": 12,
                                            "output_tokens": 8,
                                            "total_tokens": 20,
                                        }
                                    }
                                }
                            },
                        ]
                    ]
                },
            },
            {
                "gpt-4": {
                    "prompt_tokens": 22,
                    "completion_tokens": 13,
                    "total_tokens": 35,
                }
            },
        ),
    ],
)
def test_extract_usage_data_success(output, expected_usage):
    """Test successful usage data extraction from various formats."""
    call = Mock(spec=Call)
    call.summary = None
    _extract_usage_data(call, output)
    assert call.summary is not None
    assert "usage" in call.summary
    assert call.summary["usage"] == expected_usage


@pytest.mark.parametrize(
    ("output", "initial_summary", "expected_summary"),
    [
        # None output
        (None, None, None),
        # Missing outputs key
        ({"other_key": "value"}, None, None),
        # Unknown model type - should not create usage data
        (
            {
                "extra": {
                    "metadata": {
                        "ls_model_name": "some-model",
                        "ls_model_type": "unknown",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "prompt_tokens": 10,
                                            "completion_tokens": 5,
                                            "total_tokens": 15,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            None,
            None,
        ),
        # Zero token counts - should not create usage data
        (
            {
                "extra": {
                    "metadata": {"ls_model_name": "gpt-4", "ls_model_type": "chat"}
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "prompt_tokens": 0,
                                            "completion_tokens": 0,
                                            "total_tokens": 0,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            None,
            None,
        ),
        # Preserves existing summary data
        (
            {
                "extra": {
                    "metadata": {
                        "ls_model_name": "gpt-4o-mini",
                        "ls_model_type": "chat",
                    }
                },
                "outputs": {
                    "generations": [
                        [
                            {
                                "message": {
                                    "kwargs": {
                                        "usage_metadata": {
                                            "prompt_tokens": 10,
                                            "completion_tokens": 5,
                                            "total_tokens": 15,
                                        }
                                    }
                                }
                            }
                        ]
                    ]
                },
            },
            {"existing_key": "existing_value"},
            {
                "existing_key": "existing_value",
                "usage": {
                    "gpt-4o-mini": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    }
                },
            },
        ),
    ],
)
def test_extract_usage_data_edge_cases(output, initial_summary, expected_summary):
    """Test edge cases for usage data extraction."""
    call = Mock(spec=Call)
    call.summary = initial_summary

    _extract_usage_data(call, output)

    if expected_summary is None:
        assert call.summary == initial_summary
    else:
        assert call.summary == expected_summary
