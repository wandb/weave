import os
from unittest.mock import patch

from litellm.types.utils import ModelResponse

from weave.trace.settings import override_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.types import AgentSpansQueryReq
from weave.trace_server.secret_fetcher_context import secret_fetcher_context


def test_completions_create(client):
    """This test is testing the backend implementation of completions_create. It relies on LiteLLM
    and we don't want to jump through the hoops to add it to the integration sharding. So we are putting
    it here for now. Should be moved to a dedicated client tester that pins to a single python version.
    """
    model_name = "gpt-4o"
    inputs = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, world!"}],
    }
    mock_response = {
        "id": "chatcmpl-ANnboqjHwrm6uWcubQma9pzxye0Cm",
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "content": "Hello! How can I assist you today?",
                    "role": "assistant",
                    "tool_calls": None,
                    "function_call": None,
                    "provider_specific_fields": None,
                },
            }
        ],
        "created": 1730235604,
        "model": "gpt-4o-2024-08-06",
        "object": "chat.completion",
        "system_fingerprint": "fp_90354628f2",
        "usage": {
            "completion_tokens": 9,
            "prompt_tokens": 11,
            "total_tokens": 20,
            "completion_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": None,
                "reasoning_tokens": 0,
                "rejected_prediction_tokens": None,
                "text_tokens": None,
            },
            "prompt_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": None,
                "cached_tokens": 0,
                "image_tokens": None,
                "rejected_prediction_tokens": None,
                "text_tokens": None,
            },
        },
        "service_tier": None,
    }

    class DummySecretFetcher:
        def fetch(self, secret_name: str) -> dict:
            return {
                "secrets": {
                    secret_name: os.environ.get(secret_name, "DUMMY_SECRET_VALUE")
                }
            }

    # Have to do this since we run the tests in the same process as the server
    # and the inner litellm gets patched!
    with (
        override_settings(disabled=True),
        secret_fetcher_context(DummySecretFetcher()),
        patch("litellm.completion") as mock_completion,
    ):
        mock_completion.return_value = ModelResponse.model_validate(mock_response)
        res = client.server.completions_create(
            tsi.CompletionsCreateReq.model_validate(
                {
                    "project_id": client.project_id,
                    "inputs": inputs,
                }
            )
        )

    assert res.response == mock_response
    assert res.span_id is not None
    assert res.trace_id is not None
    assert res.conversation_id is not None

    spans_res = client.server.agent_spans_query(
        AgentSpansQueryReq(
            project_id=client.project_id,
            include_details=True,
        )
    )
    assert len(spans_res.spans) == 1
    span = spans_res.spans[0]
    assert span.span_id == res.span_id
    assert span.trace_id == res.trace_id
    assert span.conversation_id == res.conversation_id
    assert span.request_model == model_name
    assert span.response_model == "gpt-4o-2024-08-06"
    assert span.input_tokens == 11
    assert span.output_tokens == 9
    assert span.agent_name == "Weave Chat Playground"
    assert span.status_code == "OK"
