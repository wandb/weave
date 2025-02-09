"""
The only reason this test is here is to piggy back off the existing litellm test environment.
TODO: merge this back into `test_actions_lifecycle.py`
"""

import os
from unittest.mock import patch

import pytest
from litellm.assistants.main import ModelResponse

import weave
from tests.integrations.litellm.client_completions_create_test import (
    secret_fetcher_context,
)
from tests.trace.util import client_is_sqlite
from weave.trace.weave_client import WeaveClient
from weave.tsi.builtin_object_classes.actions import (
    ActionSpec,
)
from weave.tsi.trace_server_interface import (
    ActionsExecuteBatchReq,
)


class DummySecretFetcher:
    def fetch(self, secret_name: str) -> dict:
        return {"secrets": {secret_name: os.getenv(secret_name, "DUMMY_SECRET_VALUE")}}


primitive_mock_response = {
    "id": "chatcmpl-AQPvs3DE4NQqLxorvaTPixpqq9nTD",
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": '{"response":true}',
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


def test_action_lifecycle_llm_judge_primitive(client: WeaveClient):
    if client_is_sqlite(client):
        return pytest.skip("skipping for sqlite")

    action_name = "response_is_mindful"

    published_ref = weave.publish(
        ActionSpec(
            name=action_name,
            config={
                "action_type": "llm_judge",
                "model": "gpt-4o-mini",
                "prompt": "Is the response mindful?",
                "response_schema": {"type": "boolean"},
            },
        )
    )

    # Construct the URI
    action_ref_uri = published_ref.uri()

    @weave.op
    def example_op(input: str) -> str:
        return input + "."

    # Step 2: test that we can in-place execute one action at a time.
    _, call = example_op.call("i've been very meditative and mindful today")

    with secret_fetcher_context(DummySecretFetcher()):
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = ModelResponse.model_validate(
                primitive_mock_response
            )
            client.server.actions_execute_batch(
                ActionsExecuteBatchReq.model_validate(
                    {
                        "project_id": client._project_id(),
                        "action_ref": action_ref_uri,
                        "call_ids": [call.id],
                    }
                )
            )

    feedbacks = list(call.feedback)
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert feedback.feedback_type == "wandb.runnable." + action_name
    assert feedback.runnable_ref == action_ref_uri
    assert feedback.payload == {"output": True}


structured_mock_response = {
    "id": "chatcmpl-AQQKJWQDxSvU2Ya9ool2vgcJrFuON",
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": '{"is_mindful":true,"reason":"The response reflects a state of being that embodies mindfulness and meditation, acknowledging a positive mental and emotional state."}',
                "role": "assistant",
                "tool_calls": None,
                "function_call": None,
            },
        }
    ],
    "created": 1730861091,
    "model": "gpt-4o-mini-2024-07-18",
    "object": "chat.completion",
    "system_fingerprint": "fp_0ba0d124f1",
    "usage": {
        "completion_tokens": 32,
        "prompt_tokens": 84,
        "total_tokens": 116,
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


def test_action_lifecycle_llm_judge_structured(client: WeaveClient):
    if client_is_sqlite(client):
        return pytest.skip("skipping for sqlite")

    action_name = "response_is_mindful"

    published_ref = weave.publish(
        ActionSpec(
            name=action_name,
            config={
                "action_type": "llm_judge",
                "model": "gpt-4o-mini",
                "prompt": "Is the response mindful?",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "is_mindful": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                },
            },
        )
    )

    # Construct the URI
    action_ref_uri = published_ref.uri()

    @weave.op
    def example_op(input: str) -> str:
        return input + "."

    # Step 2: test that we can in-place execute one action at a time.
    _, call = example_op.call("i've been very meditative and mindful today")

    with secret_fetcher_context(DummySecretFetcher()):
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = ModelResponse.model_validate(
                structured_mock_response
            )
            client.server.actions_execute_batch(
                ActionsExecuteBatchReq.model_validate(
                    {
                        "project_id": client._project_id(),
                        "action_ref": action_ref_uri,
                        "call_ids": [call.id],
                    }
                )
            )

    feedbacks = list(call.feedback)
    assert len(feedbacks) == 1
    feedback = feedbacks[0]
    assert feedback.feedback_type == "wandb.runnable." + action_name
    assert feedback.runnable_ref == action_ref_uri
    assert feedback.payload == {
        "output": {
            "is_mindful": True,
            "reason": "The response reflects a state of being that embodies mindfulness and meditation, acknowledging a positive mental and emotional state.",
        }
    }
