import os
from contextlib import contextmanager
from unittest.mock import patch

from litellm.types.utils import ModelResponse

from tests.trace.util import client_is_sqlite
from weave.trace.settings import _context_vars
from weave.trace_server.secret_fetcher_context import secret_fetcher_context
from weave.tsi import trace_server_interface as tsi


@contextmanager
def with_tracing_disabled():
    token = _context_vars["disabled"].set(True)
    try:
        yield
    finally:
        _context_vars["disabled"].reset(token)


def test_completions_create(client):
    """
    This test is testing the backend implementation of completions_create. It relies on LiteLLM
    and we don't want to jump through the hoops to add it to the integration sharding. So we are putting
    it here for now. Should be moved to a dedicated client tester that pins to a single python version.
    """
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # no need to test in sqlite
        return

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
            },
            "prompt_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": None,
                "cached_tokens": 0,
                "rejected_prediction_tokens": None,
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
    with with_tracing_disabled():
        with secret_fetcher_context(DummySecretFetcher()):
            with patch("litellm.completion") as mock_completion:
                mock_completion.return_value = ModelResponse.model_validate(
                    mock_response
                )
                res = client.server.completions_create(
                    tsi.CompletionsCreateReq.model_validate(
                        {
                            "project_id": client._project_id(),
                            "inputs": inputs,
                        }
                    )
                )

    assert res.response == mock_response
    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].output == res.response
    assert calls[0].summary["usage"][model_name] == res.response["usage"]
    assert calls[0].inputs == inputs
    assert calls[0].op_name == "weave.completions_create"
