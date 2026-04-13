import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from litellm.types.utils import ModelResponse

from tests.trace.util import client_is_sqlite
from weave.trace.settings import _context_vars
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import NotFoundError
from weave.trace_server.interface.builtin_object_classes.provider import (
    Provider,
    ProviderModel,
    ProviderReturnType,
)
from weave.trace_server.llm_completion import get_custom_provider_info
from weave.trace_server.secret_fetcher_context import (
    _secret_fetcher_context,
)


@contextmanager
def with_tracing_disabled():
    token = _context_vars["disabled"].set(True)
    try:
        yield
    finally:
        _context_vars["disabled"].reset(token)


class DummySecretFetcher:
    def fetch(self, secret_name: str) -> dict:
        return {
            "secrets": {secret_name: os.environ.get(secret_name, "DUMMY_SECRET_VALUE")}
        }


def create_provider_obj(
    project_id: str,
    provider_id: str,
    base_url: str = "https://api.example.com",
    api_key_name: str = "EXAMPLE_API_KEY",
    extra_headers: dict | None = None,
    return_type: str = "openai",
) -> tsi.ObjSchema:
    provider = Provider(
        base_url=base_url,
        api_key_name=api_key_name,
        extra_headers=extra_headers or {},
        return_type=ProviderReturnType(return_type),
    )

    return tsi.ObjSchema(
        project_id=project_id,
        object_id=provider_id,
        base_object_class="Provider",
        leaf_object_class="Provider",
        val=provider.model_dump(),
        created_at=datetime.now(),
        version_index=1,
        is_latest=1,
        kind="object",
        deleted_at=None,
        digest="test-digest-1",
    )


def create_provider_model_obj(
    project_id: str,
    provider_id: str,
    model_id: str,
    model_name: str | None = None,
    max_tokens: int = 4096,
) -> tsi.ObjSchema:
    provider_model = ProviderModel(
        name=model_name or model_id,
        provider=provider_id,
        max_tokens=max_tokens,
    )

    return tsi.ObjSchema(
        project_id=project_id,
        object_id=f"{provider_id}-{model_id}",
        base_object_class="ProviderModel",
        leaf_object_class="ProviderModel",
        val=provider_model.model_dump(),
        created_at=datetime.now(),
        version_index=1,
        is_latest=1,
        kind="object",
        deleted_at=None,
        digest="test-digest-2",
    )


def create_mock_completion_response(
    model_name: str = "example-model",
    content: str = "Hello from custom provider!",
    completion_tokens: int = 5,
    prompt_tokens: int = 11,
) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "created": 1730235604,
        "model": model_name,
        "object": "chat.completion",
        "system_fingerprint": None,
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "content": content,
                    "role": "assistant",
                    "tool_calls": None,
                    "function_call": None,
                    "provider_specific_fields": None,
                },
            }
        ],
        "usage": {
            "completion_tokens": completion_tokens,
            "prompt_tokens": prompt_tokens,
            "total_tokens": completion_tokens + prompt_tokens,
            "completion_tokens_details": None,
            "prompt_tokens_details": None,
        },
        "completion_tokens_details": None,
        "prompt_tokens_details": None,
    }


def setup_test_environment(mock_secret_fetcher=None):
    mock_secret_fetcher = mock_secret_fetcher or DummySecretFetcher()
    token = _secret_fetcher_context.set(mock_secret_fetcher)
    return mock_secret_fetcher, token


def create_mock_obj_read(
    provider_obj: tsi.ObjSchema, provider_model_obj: tsi.ObjSchema
):
    def mock_obj_read(req):
        if req.object_id == provider_obj.object_id:
            return tsi.ObjReadRes(obj=provider_obj)
        elif req.object_id == provider_model_obj.object_id:
            return tsi.ObjReadRes(obj=provider_model_obj)
        raise NotFoundError(f"Unknown object_id: {req.object_id}")

    return mock_obj_read


def test_custom_provider_model_classes():
    """Test the model classes for Provider and ProviderModel."""
    provider = Provider(
        base_url="https://api.example.com",
        api_key_name="EXAMPLE_API_KEY",
        extra_headers={"X-Custom-Header": "value"},
        return_type=ProviderReturnType.OPENAI,
    )

    assert provider.base_url == "https://api.example.com"
    assert provider.api_key_name == "EXAMPLE_API_KEY"
    assert provider.extra_headers == {"X-Custom-Header": "value"}
    assert provider.return_type == ProviderReturnType.OPENAI

    provider_model = ProviderModel(
        provider="provider_id",
        max_tokens=4096,
    )

    assert provider_model.provider == "provider_id"
    assert provider_model.max_tokens == 4096


def test_get_custom_provider_info():
    """Test the get_custom_provider_info function directly."""
    project_id = "test-project"
    model_name = "test-provider-test-model"

    provider_obj = create_provider_obj(
        project_id=project_id,
        provider_id="test-provider",
        extra_headers={"X-Custom-Header": "value"},
    )

    provider_model_obj = create_provider_model_obj(
        project_id=project_id, provider_id="test-provider", model_id="test-model"
    )

    mock_obj_read = create_mock_obj_read(provider_obj, provider_model_obj)

    mock_secret_fetcher, token = setup_test_environment()
    try:
        provider_info = get_custom_provider_info(
            project_id=project_id,
            provider_name="test-provider",
            model_name=model_name,
            obj_read_func=mock_obj_read,
        )

        assert provider_info.base_url == "https://api.example.com"
        assert provider_info.api_key == "DUMMY_SECRET_VALUE"
        assert provider_info.extra_headers == {"X-Custom-Header": "value"}
        assert provider_info.return_type == "openai"
        assert provider_info.actual_model_name == "test-model"
    finally:
        _secret_fetcher_context.reset(token)


def test_custom_provider_completions_create(client):
    """Test completions_create with custom provider: standard, ollama, and trailing slash."""
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        return

    # --- Standard custom provider completion ---
    provider_id = f"test-provider-{uuid.uuid4()}"
    model_id = "test-model"
    model_name = f"custom::{provider_id}::{model_id}"

    provider_obj = create_provider_obj(
        project_id=client.project_id,
        provider_id=provider_id,
        extra_headers={"X-Custom-Header": "value"},
    )
    provider_model_obj = create_provider_model_obj(
        project_id=client.project_id,
        provider_id=provider_id,
        model_id=model_id,
        model_name=model_id,
    )
    mock_obj_read = create_mock_obj_read(provider_obj, provider_model_obj)

    inputs = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, world!"}],
    }
    mock_response = create_mock_completion_response(model_name=model_name)

    with with_tracing_disabled():
        mock_secret_fetcher, token = setup_test_environment()
        try:
            with patch(
                "weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer.obj_read"
            ) as mock_read:
                mock_read.side_effect = mock_obj_read
                with patch("litellm.completion") as mock_completion:
                    mock_completion.return_value = ModelResponse.model_validate(
                        mock_response
                    )
                    res = client.server.completions_create(
                        tsi.CompletionsCreateReq.model_validate(
                            {
                                "project_id": client.project_id,
                                "inputs": inputs,
                            }
                        )
                    )

            assert res.response == mock_response
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args[1]
            assert call_args["model"] == f"openai/{model_id}"
            assert call_args["messages"] == inputs["messages"]
            assert call_args["api_key"] == "DUMMY_SECRET_VALUE"
            assert call_args["api_base"] == "https://api.example.com"
            assert call_args["extra_headers"] == {"X-Custom-Header": "value"}

            calls = list(client.get_calls())
            assert len(calls) == 1
            assert calls[0].output == res.response
            expected_usage_key = f"{provider_id}/{model_id}"
            assert (
                calls[0].summary["usage"][expected_usage_key] == res.response["usage"]
            )
            assert calls[0].op_name == "weave.completions_create"

            # --- Ollama model (special prefix) ---
            ollama_provider_id = f"test-ollama-{uuid.uuid4()}"
            ollama_model_name = f"custom::{ollama_provider_id}::llama2"

            ollama_provider_obj = create_provider_obj(
                project_id=client.project_id,
                provider_id=ollama_provider_id,
                base_url="http://localhost:11434",
                api_key_name="OLLAMA_API_KEY",
                extra_headers={},
            )
            ollama_model_obj = create_provider_model_obj(
                project_id=client.project_id,
                provider_id=ollama_provider_id,
                model_id="llama2",
                model_name="llama2",
            )
            ollama_mock_read = create_mock_obj_read(
                ollama_provider_obj, ollama_model_obj
            )

            ollama_inputs = {
                "model": ollama_model_name,
                "messages": [{"role": "user", "content": "Hello, world!"}],
            }
            ollama_response = create_mock_completion_response(
                model_name="ollama/llama2",
                content="Hello from Ollama!",
                completion_tokens=4,
                prompt_tokens=11,
            )

            with patch(
                "weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer.obj_read"
            ) as mock_read:
                mock_read.side_effect = ollama_mock_read
                with patch("litellm.completion") as mock_completion:
                    mock_completion.return_value = ModelResponse.model_validate(
                        ollama_response
                    )
                    res = client.server.completions_create(
                        tsi.CompletionsCreateReq.model_validate(
                            {
                                "project_id": client.project_id,
                                "inputs": ollama_inputs,
                            }
                        )
                    )

            assert res.response == ollama_response
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args[1]
            assert call_args["model"] == "ollama/llama2"
            assert call_args["api_base"] == "http://localhost:11434"

            # --- Trailing slash normalization ---
            slash_provider_id = f"test-trailing-slash-{uuid.uuid4()}"
            slash_model_name = f"custom::{slash_provider_id}::test-model"

            slash_provider_obj = create_provider_obj(
                project_id=client.project_id,
                provider_id=slash_provider_id,
                base_url="http://localhost:11434/",
                api_key_name="TEST_API_KEY",
                extra_headers={},
            )
            slash_model_obj = create_provider_model_obj(
                project_id=client.project_id,
                provider_id=slash_provider_id,
                model_id="test-model",
                model_name="test-model",
            )
            slash_mock_read = create_mock_obj_read(
                slash_provider_obj, slash_model_obj
            )

            slash_inputs = {
                "model": slash_model_name,
                "messages": [{"role": "user", "content": "Hello, world!"}],
            }
            slash_response = create_mock_completion_response(
                model_name="test-model", content="Hello!"
            )

            with patch(
                "weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer.obj_read"
            ) as mock_read:
                mock_read.side_effect = slash_mock_read
                with patch("litellm.completion") as mock_completion:
                    mock_completion.return_value = ModelResponse.model_validate(
                        slash_response
                    )
                    client.server.completions_create(
                        tsi.CompletionsCreateReq.model_validate(
                            {
                                "project_id": client.project_id,
                                "inputs": slash_inputs,
                            }
                        )
                    )

            mock_completion.assert_called_once()
            call_args = mock_completion.call_args[1]
            assert call_args["api_base"] == "http://localhost:11434"
        finally:
            _secret_fetcher_context.reset(token)


def test_custom_provider_error_handling(client):
    """Test error handling for custom provider: missing provider and invalid format."""
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        return

    with with_tracing_disabled():
        mock_secret_fetcher, token = setup_test_environment()
        try:
            # Provider not found
            provider_id = f"test-error-{uuid.uuid4()}"
            model_name = f"custom::{provider_id}::test-model"

            def mock_obj_read_error(req):
                raise NotFoundError("Test error fetching provider")

            with patch(
                "weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer.obj_read"
            ) as mock_read:
                mock_read.side_effect = mock_obj_read_error
                res = client.server.completions_create(
                    tsi.CompletionsCreateReq.model_validate(
                        {
                            "project_id": client.project_id,
                            "inputs": {
                                "model": model_name,
                                "messages": [
                                    {"role": "user", "content": "Hello, world!"}
                                ],
                            },
                        }
                    )
                )

            assert "error" in res.response
            assert (
                "Failed to fetch provider model information: Test error fetching provider"
                in res.response["error"]
            )

            # Invalid model format (no custom:: prefix)
            res = client.server.completions_create(
                tsi.CompletionsCreateReq.model_validate(
                    {
                        "project_id": client.project_id,
                        "inputs": {
                            "model": "invalid-model-format",
                            "messages": [
                                {"role": "user", "content": "Hello, world!"}
                            ],
                        },
                    }
                )
            )

            assert "error" in res.response
            assert "LLM Provider NOT provided" in res.response["error"]
        finally:
            _secret_fetcher_context.reset(token)
