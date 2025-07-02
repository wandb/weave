from contextlib import contextmanager
from unittest.mock import patch

from litellm.assistants.main import ModelResponse


@contextmanager
def with_mock_litellm_completion(response_dict: dict):
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value = ModelResponse.model_validate(response_dict)
        yield


@contextmanager
def with_simple_mock_litellm_completion(response_text: str):
    with with_mock_litellm_completion(
        {
            "id": "chatcmpl-AQPvs3DE4NQqLxorvaTPixpqq9nTD",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": response_text,
                        "role": "assistant",
                        "tool_calls": None,
                        "function_call": None,
                    },
                }
            ],
            "created": 1730859576,
            "model": "gpt-4o-mini-2024-07-18",
            "object": "chat.completion",
            "system_fingerprint": "fp_0ba0d124f1",
            "usage": {
                "completion_tokens": 5,
                "prompt_tokens": 74,
                "total_tokens": 79,
                "completion_tokens_details": {
                    "audio_tokens": 0,
                    "reasoning_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0,
                },
                "prompt_tokens_details": {"audio_tokens": 0, "cached_tokens": 0},
            },
            "service_tier": None,
        }
    ):
        yield
