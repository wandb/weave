import datetime
import unittest
from unittest.mock import MagicMock, patch

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
    MissingLLMApiKeyError,
    NotFoundError,
)
from weave.trace_server.llm_completion import get_custom_provider_info
from weave.trace_server.secret_fetcher_context import (
    _secret_fetcher_context,
)


class MockObjectReadError(Exception):
    """Custom exception for mock object read failures."""

    pass


class TestGetCustomProviderInfo(unittest.TestCase):
    """Tests for the get_custom_provider_info function in llm_completion.py.

    This test suite verifies the functionality of retrieving and validating custom provider
    information for LLM completions. It tests:
    1. Successful retrieval of provider and model information
    2. Error handling for missing or invalid configurations
    3. Secret fetching and validation
    4. Type checking for provider and model objects

    The suite uses mock objects to simulate database interactions and secret fetching,
    allowing for controlled testing of various scenarios and edge cases.
    """

    def setUp(self):
        """Set up test fixtures before each test.

        Creates mock objects and test data including:
        - Project and provider IDs
        - Provider configuration with API endpoints and headers
        - Provider model configuration with model parameters
        - Mock secret fetcher for API key management
        """
        self.project_id = "test-project"

        # Provider data with complete configuration
        self.provider_id = "test-provider"
        self.provider_obj = tsi.ObjSchema(
            project_id=self.project_id,
            object_id=self.provider_id,
            digest="digest-1",
            base_object_class="Provider",
            val={
                "base_url": "https://api.example.com",
                "api_key_name": "TEST_API_KEY",
                "extra_headers": {"X-Header": "value"},
                "return_type": "openai",
            },
            created_at=datetime.datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        # Provider model data with model-specific settings
        self.model_id = "test-model"
        self.provider_model_obj = tsi.ObjSchema(
            project_id=self.project_id,
            object_id=f"{self.provider_id}-{self.model_id}",
            digest="digest-2",
            base_object_class="ProviderModel",
            val={
                "name": "actual-model-name",
                "provider": self.provider_id,
                "max_tokens": 4096,
                "mode": "chat",
            },
            created_at=datetime.datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        # Model name in format provider_id/model_id for API calls
        self.model_name = f"{self.provider_id}/{self.model_id}"

        # Mock secret fetcher for API key management
        self.mock_secret_fetcher = MagicMock()
        self.mock_secret_fetcher.fetch.return_value = {
            "secrets": {"TEST_API_KEY": "test-api-key-value"}
        }

        # Mock object read function for database interactions
        self.mock_obj_read_func = MagicMock()

    def test_successful_provider_info_fetch(self):
        """Test successful retrieval of provider information.

        Verifies that:
        1. Provider and model information are correctly retrieved
        2. API credentials are properly fetched
        3. All configuration parameters are returned as expected
        4. Object read and secret fetch calls are made correctly
        """

        def mock_obj_read(req):
            if req.object_id == self.provider_id:
                return tsi.ObjReadRes(obj=self.provider_obj)
            elif req.object_id == f"{self.provider_id}-{self.model_id}":
                return tsi.ObjReadRes(obj=self.provider_model_obj)
            raise NotFoundError(f"Unknown object_id: {req.object_id}")

        self.mock_obj_read_func.side_effect = mock_obj_read

        # Set up the secret fetcher context
        token = _secret_fetcher_context.set(self.mock_secret_fetcher)
        try:
            # Call the function under test
            provider_info = get_custom_provider_info(
                project_id=self.project_id,
                model_name=self.model_name,
                obj_read_func=self.mock_obj_read_func,
            )

            # Verify the results
            assert provider_info.base_url == "https://api.example.com", (
                f"Base URL mismatch. Expected 'https://api.example.com', "
                f"got '{provider_info.base_url}'"
            )
            assert provider_info.api_key == "test-api-key-value", (
                f"API key mismatch. Expected 'test-api-key-value', "
                f"got '{provider_info.api_key}'"
            )
            assert provider_info.extra_headers == {"X-Header": "value"}, (
                f"Extra headers mismatch. Expected {{'X-Header': 'value'}}, "
                f"got {provider_info.extra_headers}"
            )
            assert provider_info.return_type == "openai", (
                f"Return type mismatch. Expected 'openai', "
                f"got '{provider_info.return_type}'"
            )
            assert provider_info.actual_model_name == "actual-model-name", (
                f"Actual model name mismatch. Expected 'actual-model-name', "
                f"got '{provider_info.actual_model_name}'"
            )

            # Verify the mock calls
            self.mock_obj_read_func.assert_called()
            self.mock_secret_fetcher.fetch.assert_called_with("TEST_API_KEY")
        finally:
            _secret_fetcher_context.reset(token)

    def test_missing_secret_fetcher(self):
        """Test error handling when secret fetcher is not configured.

        Verifies that appropriate error is raised when attempting to
        fetch provider information without a configured secret fetcher.
        """
        # Set the context to None to simulate missing secret fetcher
        token = _secret_fetcher_context.set(None)
        try:
            with self.assertRaises(InvalidRequest) as context:
                get_custom_provider_info(
                    project_id=self.project_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )

            self.assertIn(
                "No secret fetcher found",
                str(context.exception),
                "Expected error message about missing secret fetcher not found",
            )
        finally:
            _secret_fetcher_context.reset(token)

    def test_provider_not_found(self):
        """Test error handling when provider object cannot be found.

        Verifies that appropriate error is raised when the provider
        object cannot be retrieved from the database.
        """
        # Make obj_read_func raise an exception to simulate missing provider
        self.mock_obj_read_func.side_effect = NotFoundError("Provider not found")

        token = _secret_fetcher_context.set(self.mock_secret_fetcher)
        try:
            with self.assertRaises(InvalidRequest) as context:
                get_custom_provider_info(
                    project_id=self.project_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )

            self.assertIn(
                "Failed to fetch provider information",
                str(context.exception),
                "Expected error message about failed provider fetch not found",
            )
        finally:
            _secret_fetcher_context.reset(token)

    def test_wrong_provider_type(self):
        """Test error handling when provider object has incorrect type.

        Verifies that appropriate error is raised when the retrieved
        provider object is not of the expected Provider type.
        """
        # Create provider object with incorrect type
        wrong_type_provider = self.provider_obj.model_copy()
        wrong_type_provider.base_object_class = "NotAProvider"

        def mock_obj_read(req):
            if req.object_id == self.provider_id:
                return tsi.ObjReadRes(obj=wrong_type_provider)
            else:
                return tsi.ObjReadRes(obj=self.provider_model_obj)

        self.mock_obj_read_func.side_effect = mock_obj_read

        token = _secret_fetcher_context.set(self.mock_secret_fetcher)
        try:
            with self.assertRaises(InvalidRequest) as context:
                get_custom_provider_info(
                    project_id=self.project_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )

            self.assertIn(
                "is not a Provider",
                str(context.exception),
                "Expected error message about incorrect provider type not found",
            )
        finally:
            _secret_fetcher_context.reset(token)

    def test_wrong_provider_model_type(self):
        """Test error handling when provider model object has incorrect type.

        Verifies that appropriate error is raised when the retrieved
        provider model object is not of the expected ProviderModel type.
        """
        # Create provider model object with incorrect type
        wrong_type_model = self.provider_model_obj.model_copy()
        wrong_type_model.base_object_class = "NotAProviderModel"

        def mock_obj_read(req):
            if req.object_id == self.provider_id:
                return tsi.ObjReadRes(obj=self.provider_obj)
            else:
                return tsi.ObjReadRes(obj=wrong_type_model)

        self.mock_obj_read_func.side_effect = mock_obj_read

        token = _secret_fetcher_context.set(self.mock_secret_fetcher)
        try:
            with self.assertRaises(InvalidRequest) as context:
                get_custom_provider_info(
                    project_id=self.project_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )

            self.assertIn(
                "is not a ProviderModel",
                str(context.exception),
                "Expected error message about incorrect provider model type not found",
            )
        finally:
            _secret_fetcher_context.reset(token)


class TestLLMCompletionStreaming(unittest.TestCase):
    """Tests for LLM completion streaming functionality."""

    def setUp(self):
        """Set up test fixtures before each test."""
        self.server = chts.ClickHouseTraceServer(host="test_host")
        self.mock_secret_fetcher = MagicMock()
        self.mock_secret_fetcher.fetch.return_value = {
            "secrets": {
                "OPENAI_API_KEY": "test-api-key-value",
                "CUSTOM_API_KEY": "test-api-key-value",
                "TEST_API_KEY": "test-api-key-value",
            }
        }
        self.token = _secret_fetcher_context.set(self.mock_secret_fetcher)

    def tearDown(self):
        _secret_fetcher_context.reset(self.token)

    def test_basic_streaming_completion(self):
        """Test basic streaming completion functionality."""
        # Mock the litellm completion stream
        mock_chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": "Hello"},
                        "finish_reason": None,
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "test-model",
                "created": 1234567890,
            },
            {
                "choices": [
                    {
                        "delta": {"content": " world"},
                        "finish_reason": None,
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "test-model",
                "created": 1234567890,
            },
            {
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": "stop",
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "test-model",
                "created": 1234567890,
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            },
        ]

        with patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm:
            # Mock the litellm completion stream
            mock_stream = MagicMock()
            mock_stream.__iter__.return_value = mock_chunks
            mock_litellm.return_value = mock_stream

            # Create test request
            req = tsi.CompletionsCreateReq(
                project_id="test_project",
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say hello"}],
                ),
                track_llm_call=False,
            )

            # Get the stream
            stream = self.server.completions_create_stream(req)

            # Collect all chunks
            chunks = list(stream)

            # Verify the chunks
            self.assertEqual(len(chunks), 3)
            self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "Hello")
            self.assertEqual(chunks[1]["choices"][0]["delta"]["content"], " world")
            self.assertEqual(chunks[2]["choices"][0]["finish_reason"], "stop")
            self.assertIn("usage", chunks[2])

    def test_streaming_error_handling(self):
        """Test error handling in streaming completion."""
        with patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm:
            # Mock litellm to raise an exception
            mock_litellm.side_effect = Exception("Test error")

            # Create test request
            req = tsi.CompletionsCreateReq(
                project_id="test_project",
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say hello"}],
                ),
                track_llm_call=False,
            )

            # Get the stream and expect an exception
            with self.assertRaises(Exception):
                list(self.server.completions_create_stream(req))

    def test_streaming_with_call_tracking(self):
        """Test streaming completion with call tracking enabled."""
        # Mock the litellm completion stream
        mock_chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": "Hello"},
                        "finish_reason": None,
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "test-model",
                "created": 1234567890,
            },
            {
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": "stop",
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "test-model",
                "created": 1234567890,
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 1,
                    "total_tokens": 11,
                },
            },
        ]

        with (
            patch(
                "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
            ) as mock_litellm,
            patch.object(
                chts.ClickHouseTraceServer, "_insert_call"
            ) as mock_insert_call,
        ):
            # Mock the litellm completion stream
            mock_stream = MagicMock()
            mock_stream.__iter__.return_value = mock_chunks
            mock_litellm.return_value = mock_stream

            # Create test request
            req = tsi.CompletionsCreateReq(
                project_id="dGVzdF9wcm9qZWN0",
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say hello"}],
                ),
                track_llm_call=True,
            )

            # Get the stream
            stream = self.server.completions_create_stream(req)

            # Collect all chunks
            chunks = list(stream)

            # Verify the chunks
            self.assertEqual(len(chunks), 3)  # Meta chunk + 2 content chunks
            self.assertIn("_meta", chunks[0])
            self.assertIn("weave_call_id", chunks[0]["_meta"])
            self.assertEqual(chunks[1]["choices"][0]["delta"]["content"], "Hello")
            self.assertEqual(chunks[2]["choices"][0]["finish_reason"], "stop")

            # Verify call tracking
            self.assertEqual(mock_insert_call.call_count, 2)  # Start and end calls
            start_call = mock_insert_call.call_args_list[0][0][0]
            end_call = mock_insert_call.call_args_list[1][0][0]
            self.assertEqual(start_call.project_id, "dGVzdF9wcm9qZWN0")
            self.assertEqual(end_call.project_id, "dGVzdF9wcm9qZWN0")
            self.assertEqual(end_call.id, start_call.id)

    def test_custom_provider_streaming(self):
        """Test streaming completion with a custom provider."""
        # Mock the litellm completion stream
        mock_chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": "Custom"},
                        "finish_reason": None,
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "custom-model",
                "created": 1234567890,
            },
            {
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": "stop",
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "custom-model",
                "created": 1234567890,
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 1,
                    "total_tokens": 6,
                },
            },
        ]

        with (
            patch(
                "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
            ) as mock_litellm,
            patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read,
        ):
            # Mock the litellm completion stream
            mock_stream = MagicMock()
            mock_stream.__iter__.return_value = mock_chunks
            mock_litellm.return_value = mock_stream

            # Mock provider and model objects
            mock_provider = tsi.ObjSchema(
                project_id="test_project",
                object_id="custom-provider",
                digest="digest-1",
                base_object_class="Provider",
                val={
                    "base_url": "https://api.custom.com",
                    "api_key_name": "CUSTOM_API_KEY",
                    "extra_headers": {"X-Custom": "value"},
                    "return_type": "openai",
                    "api_base": "https://api.custom.com",
                },
                created_at=datetime.datetime.now(),
                version_index=1,
                is_latest=1,
                kind="object",
                deleted_at=None,
            )

            mock_model = tsi.ObjSchema(
                project_id="test_project",
                object_id="custom-provider-model",
                digest="digest-2",
                base_object_class="ProviderModel",
                val={
                    "name": "custom-model",
                    "provider": "custom-provider",
                    "max_tokens": 4096,
                    "mode": "chat",
                },
                created_at=datetime.datetime.now(),
                version_index=1,
                is_latest=1,
                kind="object",
                deleted_at=None,
            )

            def mock_obj_read_func(req):
                if req.object_id == "custom-provider":
                    return tsi.ObjReadRes(obj=mock_provider)
                elif req.object_id == "custom-provider-model":
                    return tsi.ObjReadRes(obj=mock_model)
                raise MockObjectReadError(f"Unknown object_id: {req.object_id}")

            mock_obj_read.side_effect = mock_obj_read_func

            # Create test request
            req = tsi.CompletionsCreateReq(
                project_id="dGVzdF9wcm9qZWN0",
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="custom-provider/model",
                    messages=[{"role": "user", "content": "Say hello"}],
                ),
                track_llm_call=False,
            )

            # Get the stream
            stream = self.server.completions_create_stream(req)

            # Collect all chunks
            chunks = list(stream)

            # Verify the chunks
            self.assertEqual(len(chunks), 2)
            self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "Custom")
            self.assertEqual(chunks[1]["choices"][0]["finish_reason"], "stop")

            # Verify litellm was called with correct parameters
            mock_litellm.assert_called_once()
            call_args = mock_litellm.call_args[1]
            self.assertEqual(
                call_args.get("api_base") or call_args.get("base_url"),
                "https://api.custom.com",
            )
            self.assertEqual(call_args["extra_headers"], {"X-Custom": "value"})

    def test_missing_api_key(self):
        """Test handling of missing API key in streaming completion."""
        with patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm:
            # Mock litellm to raise MissingLLMApiKeyError
            mock_litellm.side_effect = MissingLLMApiKeyError(
                "No API key found", api_key_name="TEST_API_KEY"
            )

            # Create test request
            req = tsi.CompletionsCreateReq(
                project_id="test_project",
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say hello"}],
                ),
                track_llm_call=False,
            )

            # Get the stream and expect an exception
            with self.assertRaises(MissingLLMApiKeyError):
                list(self.server.completions_create_stream(req))


if __name__ == "__main__":
    unittest.main()
