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
    ProviderModelMode,
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
    extra_headers: dict = None,
    return_type: str = "openai",
) -> tsi.ObjSchema:
    """Create a Provider object for testing.

    Args:
        project_id: The project ID
        provider_id: The provider ID
        base_url: The base URL for the provider's API
        api_key_name: The name of the API key secret
        extra_headers: Additional headers to include in requests
        return_type: The return type for the provider

    Returns:
        tsi.ObjSchema: A provider object
    """
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
    model_name: str = None,
    max_tokens: int = 4096,
    mode: str = "chat",
) -> tsi.ObjSchema:
    """Create a ProviderModel object for testing.

    Args:
        project_id: The project ID
        provider_id: The provider ID
        model_id: The model ID
        model_name: The actual model name to use (defaults to model_id)
        max_tokens: Maximum tokens for the model
        mode: The model mode (chat/completion)

    Returns:
        tsi.ObjSchema: A provider model object
    """
    provider_model = ProviderModel(
        name=model_name or model_id,
        provider=provider_id,
        max_tokens=max_tokens,
        mode=ProviderModelMode(mode),
    )

    return tsi.ObjSchema(
        project_id=project_id,
        object_id=f"{provider_id}-{model_id}",
        base_object_class="ProviderModel",
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
    """Create a mock completion response for testing.

    Args:
        model_name: The name of the model
        content: The response content
        completion_tokens: Number of completion tokens
        prompt_tokens: Number of prompt tokens

    Returns:
        dict: A mock completion response
    """
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
    """Set up the test environment with a secret fetcher.

    Args:
        mock_secret_fetcher: Optional custom secret fetcher to use

    Returns:
        tuple: (secret_fetcher, context_token)
    """
    mock_secret_fetcher = mock_secret_fetcher or DummySecretFetcher()
    token = _secret_fetcher_context.set(mock_secret_fetcher)
    return mock_secret_fetcher, token


def create_mock_obj_read(
    provider_obj: tsi.ObjSchema, provider_model_obj: tsi.ObjSchema
):
    """Create a mock obj_read function for testing.

    Args:
        provider_obj: The provider object configuration
        provider_model_obj: The provider model object configuration

    Returns:
        function: A mock obj_read function
    """

    def mock_obj_read(req):
        if req.object_id == provider_obj.object_id:
            return tsi.ObjReadRes(obj=provider_obj)
        elif req.object_id == provider_model_obj.object_id:
            return tsi.ObjReadRes(obj=provider_model_obj)
        raise NotFoundError(f"Unknown object_id: {req.object_id}")

    return mock_obj_read


def test_custom_provider_model_classes():
    """Test the model classes for Provider and ProviderModel.

    This test verifies that:
    1. Provider class can be instantiated with correct configuration
    2. Provider attributes are properly set and accessible
    3. ProviderModel class can be instantiated with correct configuration
    4. ProviderModel attributes are properly set and accessible

    The test checks both required and optional fields, ensuring they are
    properly typed and accessible through the model instances.
    """
    # Test Provider class initialization and attribute access
    provider = Provider(
        base_url="https://api.example.com",
        api_key_name="EXAMPLE_API_KEY",
        extra_headers={"X-Custom-Header": "value"},
        return_type=ProviderReturnType.OPENAI,
    )

    # Verify Provider attributes
    assert provider.base_url == "https://api.example.com", (
        f"Provider base_url mismatch. Expected 'https://api.example.com', "
        f"got '{provider.base_url}'"
    )
    assert provider.api_key_name == "EXAMPLE_API_KEY", (
        f"Provider api_key_name mismatch. Expected 'EXAMPLE_API_KEY', "
        f"got '{provider.api_key_name}'"
    )
    assert provider.extra_headers == {"X-Custom-Header": "value"}, (
        f"Provider extra_headers mismatch. Expected {{'X-Custom-Header': 'value'}}, "
        f"got {provider.extra_headers}"
    )
    assert provider.return_type == ProviderReturnType.OPENAI, (
        f"Provider return_type mismatch. Expected {ProviderReturnType.OPENAI}, "
        f"got {provider.return_type}"
    )

    # Test ProviderModel class initialization and attribute access
    provider_model = ProviderModel(
        provider="provider_id",
        max_tokens=4096,
        mode=ProviderModelMode.CHAT,
    )

    # Verify ProviderModel attributes
    assert provider_model.provider == "provider_id", (
        f"ProviderModel provider mismatch. Expected 'provider_id', "
        f"got '{provider_model.provider}'"
    )
    assert provider_model.max_tokens == 4096, (
        f"ProviderModel max_tokens mismatch. Expected 4096, "
        f"got {provider_model.max_tokens}"
    )
    assert provider_model.mode == ProviderModelMode.CHAT, (
        f"ProviderModel mode mismatch. Expected {ProviderModelMode.CHAT}, "
        f"got {provider_model.mode}"
    )


def test_custom_provider_completions_create(client):
    """Test the completions_create endpoint with a custom provider.

    This test verifies the complete flow of creating a completion using a custom provider:
    1. Provider and model object creation with correct configuration
    2. Proper request handling and parameter passing to LiteLLM
    3. Response transformation and validation
    4. Usage tracking and logging of the completion call

    The test mocks:
    - Object read operations to simulate provider/model configuration
    - LiteLLM completion call to simulate API response
    - Secret fetching for API keys

    Args:
        client: The test client fixture providing access to the completion endpoint
    """
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # no need to test in sqlite
        return

    # Create unique provider ID and model ID for test isolation
    provider_id = f"test-provider-{uuid.uuid4()}"
    model_id = "test-model"
    model_name = f"{provider_id}/{model_id}"

    # Create a Provider object with test configuration
    provider_obj = create_provider_obj(
        project_id=client._project_id(),
        provider_id=provider_id,
        extra_headers={"X-Custom-Header": "value"},
    )

    # Create a ProviderModel object with test configuration
    provider_model_obj = create_provider_model_obj(
        project_id=client._project_id(),
        provider_id=provider_id,
        model_id=model_id,
        model_name=model_name,  # Use the full model name
    )

    # Mock responses for obj_read calls to return our test configurations
    mock_obj_read = create_mock_obj_read(provider_obj, provider_model_obj)

    # Create test input with a simple chat message
    inputs = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, world!"}],
    }

    # Mock response from LiteLLM to simulate successful API call
    mock_response = create_mock_completion_response(model_name=model_name)

    # Run test with tracing disabled to avoid interference
    with with_tracing_disabled():
        # Set up the secret fetcher
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
                                "project_id": client._project_id(),
                                "inputs": inputs,
                            }
                        )
                    )

            # Verify the response matches our mock
            assert (
                res.response == mock_response
            ), f"Response mismatch. Expected {mock_response}, got {res.response}"

            # Verify LiteLLM was called with correct parameters
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args[1]
            assert (
                call_args["model"] == model_name
            ), f"Model name mismatch. Expected '{model_name}', got '{call_args['model']}'"
            assert call_args["messages"] == inputs["messages"], (
                f"Messages mismatch. Expected {inputs['messages']}, "
                f"got {call_args['messages']}"
            )
            assert call_args["api_key"] == "DUMMY_SECRET_VALUE", (
                f"API key mismatch. Expected 'DUMMY_SECRET_VALUE', "
                f"got '{call_args['api_key']}'"
            )
            assert call_args["api_base"] == "https://api.example.com", (
                f"API base URL mismatch. Expected 'https://api.example.com', "
                f"got '{call_args['api_base']}'"
            )
            assert call_args["extra_headers"] == {"X-Custom-Header": "value"}, (
                f"Extra headers mismatch. Expected {{'X-Custom-Header': 'value'}}, "
                f"got {call_args['extra_headers']}"
            )

            # Verify the call was properly logged
            calls = list(client.get_calls())
            assert len(calls) == 1, f"Expected 1 logged call, got {len(calls)}"
            assert calls[0].output == res.response, (
                f"Logged output mismatch. Expected {res.response}, "
                f"got {calls[0].output}"
            )
            assert calls[0].summary["usage"][model_name] == res.response["usage"], (
                f"Usage summary mismatch. Expected {res.response['usage']}, "
                f"got {calls[0].summary['usage'][model_name]}"
            )
            assert (
                calls[0].inputs == inputs
            ), f"Logged inputs mismatch. Expected {inputs}, got {calls[0].inputs}"
            assert calls[0].op_name == "weave.completions_create", (
                f"Operation name mismatch. Expected 'weave.completions_create', "
                f"got {calls[0].op_name}"
            )
        finally:
            _secret_fetcher_context.reset(token)


def test_custom_provider_ollama_model(client):
    """Test handling of ollama models that need special prefixing."""
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # no need to test in sqlite
        return

    # Create provider ID and model ID for testing
    provider_id = f"test-ollama-{uuid.uuid4()}"
    model_id = "llama2"
    model_name = f"{provider_id}/{model_id}"

    # Create a Provider object with Ollama-specific configuration
    provider_obj = create_provider_obj(
        project_id=client._project_id(),
        provider_id=provider_id,
        base_url="http://localhost:11434",
        api_key_name="OLLAMA_API_KEY",
        extra_headers={},
    )

    # Create a ProviderModel object with Ollama-specific configuration
    provider_model_obj = create_provider_model_obj(
        project_id=client._project_id(),
        provider_id=provider_id,
        model_id=model_id,
        model_name="llama2",  # Note: this will be prefixed with ollama/
    )

    # Mock responses for obj_read calls
    mock_obj_read = create_mock_obj_read(provider_obj, provider_model_obj)

    # Create test input
    inputs = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, world!"}],
    }

    # Mock response from LiteLLM with Ollama-specific details
    mock_response = create_mock_completion_response(
        model_name="ollama/llama2",
        content="Hello from Ollama!",
        completion_tokens=4,
        prompt_tokens=11,
    )

    with with_tracing_disabled():
        # Set up the secret fetcher
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
                                "project_id": client._project_id(),
                                "inputs": inputs,
                            }
                        )
                    )

            # Verify the correct response is returned
            assert res.response == mock_response

            # Verify the litellm.completion was called with the right parameters
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args[1]
            assert call_args["model"] == "ollama/llama2"  # Should add ollama/ prefix
            assert call_args["api_key"] == "DUMMY_SECRET_VALUE"
            assert call_args["api_base"] == "http://localhost:11434"
        finally:
            _secret_fetcher_context.reset(token)


def test_get_custom_provider_info():
    """Test the get_custom_provider_info function directly."""
    # Set up test data
    project_id = "test-project"
    model_name = "test-provider/test-model"

    # Create a Provider object with explicit extra headers
    provider_obj = create_provider_obj(
        project_id=project_id,
        provider_id="test-provider",
        extra_headers={"X-Custom-Header": "value"},
    )

    # Create a ProviderModel object
    provider_model_obj = create_provider_model_obj(
        project_id=project_id, provider_id="test-provider", model_id="test-model"
    )

    # Mock the obj_read_func
    mock_obj_read = create_mock_obj_read(provider_obj, provider_model_obj)

    # Set up the secret fetcher
    mock_secret_fetcher, token = setup_test_environment()
    try:
        # Call the function
        base_url, api_key, extra_headers, return_type, actual_model_name = (
            get_custom_provider_info(
                project_id=project_id,
                model_name=model_name,
                obj_read_func=mock_obj_read,
            )
        )

        # Verify the results
        assert base_url == "https://api.example.com"
        assert api_key == "DUMMY_SECRET_VALUE"
        assert extra_headers == {"X-Custom-Header": "value"}
        assert return_type == "openai"
        assert actual_model_name == "test-model"
    finally:
        _secret_fetcher_context.reset(token)


def test_error_handling_custom_provider(client):
    """Test error handling for custom provider."""
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # no need to test in sqlite
        return

    # Create provider ID and model ID for testing
    provider_id = f"test-error-{uuid.uuid4()}"
    model_id = "test-model"
    model_name = f"{provider_id}/{model_id}"

    # Create test input
    inputs = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, world!"}],
    }

    # Mock obj_read to raise an exception
    def mock_obj_read(req):
        raise NotFoundError("Test error fetching provider")

    with with_tracing_disabled():
        # Set up the secret fetcher
        mock_secret_fetcher, token = setup_test_environment()
        try:
            with patch(
                "weave.trace_server.clickhouse_trace_server_batched.ClickHouseTraceServer.obj_read"
            ) as mock_read:
                mock_read.side_effect = mock_obj_read
                res = client.server.completions_create(
                    tsi.CompletionsCreateReq.model_validate(
                        {
                            "project_id": client._project_id(),
                            "inputs": inputs,
                        }
                    )
                )

            # Verify error is returned in the response
            assert "error" in res.response
            assert "Test error fetching provider" in res.response["error"]
        finally:
            _secret_fetcher_context.reset(token)


def test_custom_provider_invalid_model_format(client):
    """Test error handling for invalid model format."""
    is_sqlite = client_is_sqlite(client)
    if is_sqlite:
        # no need to test in sqlite
        return

    # Use an invalid model format (no slash)
    model_name = "invalid-model-format"

    # Create test input
    inputs = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, world!"}],
    }

    with with_tracing_disabled():
        # Set up the secret fetcher
        mock_secret_fetcher, token = setup_test_environment()
        try:
            res = client.server.completions_create(
                tsi.CompletionsCreateReq.model_validate(
                    {
                        "project_id": client._project_id(),
                        "inputs": inputs,
                    }
                )
            )

            # Verify error is returned in the response
            assert "error" in res.response
            assert "Invalid custom provider model format" in res.response["error"]
        finally:
            _secret_fetcher_context.reset(token)
