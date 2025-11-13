import datetime
import unittest
from unittest.mock import MagicMock, patch

import pytest

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
            leaf_object_class="Provider",
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
            leaf_object_class="ProviderModel",
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
            elif req.object_id == self.model_name:
                return tsi.ObjReadRes(obj=self.provider_model_obj)
            raise NotFoundError(f"Unknown object_id: {req.object_id}")

        self.mock_obj_read_func.side_effect = mock_obj_read

        # Set up the secret fetcher context
        token = _secret_fetcher_context.set(self.mock_secret_fetcher)
        try:
            # Call the function under test
            provider_info = get_custom_provider_info(
                project_id=self.project_id,
                provider_name=self.provider_id,
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
                    provider_name=self.provider_id,
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
                    provider_name=self.provider_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )

            self.assertIn(
                "Failed to fetch provider model information",
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
                    provider_name=self.provider_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )

            self.assertIn(
                "Could not find Provider",
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
                    provider_name=self.provider_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )

            self.assertIn(
                "Could not find Provider",
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

        class StreamingException(Exception): ...

        with patch(
            "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
        ) as mock_litellm:
            # Mock litellm to raise an exception
            mock_litellm.side_effect = StreamingException("Test error")

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
            with self.assertRaises(StreamingException):
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
                leaf_object_class="Provider",
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
                leaf_object_class="ProviderModel",
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
                    model="custom::custom-provider::model",
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


class TestPromptResolution(unittest.TestCase):
    """Tests for prompt resolution and template variable substitution."""

    def setUp(self):
        """Set up test fixtures before each test."""
        self.project_id = "test-project"
        self.mock_secret_fetcher = MagicMock()
        self.mock_secret_fetcher.fetch.return_value = {
            "secrets": {"OPENAI_API_KEY": "test-api-key"}
        }
        self.token = _secret_fetcher_context.set(self.mock_secret_fetcher)

    def tearDown(self):
        _secret_fetcher_context.reset(self.token)

    def test_replace_template_vars_in_messages(self):
        """Test template variable replacement in messages."""
        from weave.trace_server.llm_completion import replace_template_vars_in_messages

        messages = [
            {"role": "system", "content": "You are {assistant_name}."},
            {"role": "user", "content": "My name is {user_name}."},
        ]

        template_vars = {"assistant_name": "Claude", "user_name": "Alice"}

        result = replace_template_vars_in_messages(messages, template_vars)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["content"], "You are Claude.")
        self.assertEqual(result[1]["content"], "My name is Alice.")

    def test_replace_template_vars_with_missing_variable(self):
        """Test template variable replacement when a variable is missing."""
        from weave.trace_server.errors import InvalidRequest
        from weave.trace_server.llm_completion import replace_template_vars_in_messages

        messages = [
            {"role": "system", "content": "You are {assistant_name}."},
        ]

        template_vars = {}  # Missing assistant_name

        # Should raise InvalidRequest when variable is missing
        with self.assertRaises(InvalidRequest) as context:
            replace_template_vars_in_messages(messages, template_vars)

        self.assertIn("assistant_name", str(context.exception))

    def test_replace_template_vars_with_complex_content(self):
        """Test template variable replacement with list content (not currently supported)."""
        from weave.trace_server.llm_completion import replace_template_vars_in_messages

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello {name}"},
                    {"type": "image_url", "image_url": {"url": "https://example.com"}},
                ],
            }
        ]

        template_vars = {"name": "World"}

        # Current implementation doesn't replace variables in list content, it just passes through
        result = replace_template_vars_in_messages(messages, template_vars)

        # Content should remain unchanged (list content replacement not implemented)
        self.assertEqual(result[0]["content"][0]["text"], "Hello {name}")
        self.assertEqual(
            result[0]["content"][1]["image_url"]["url"], "https://example.com"
        )

    def test_resolve_prompt_messages(self):
        """Test resolving prompt messages from a MessagesPrompt object."""
        from weave.trace_server.llm_completion import resolve_prompt_messages

        # Create a mock MessagesPrompt object
        mock_prompt_obj = tsi.ObjSchema(
            project_id=self.project_id,
            object_id="test-prompt",
            digest="digest-1",
            base_object_class="MessagesPrompt",
            leaf_object_class="MessagesPrompt",
            val={
                "messages": [
                    {"role": "system", "content": "You are {assistant_name}."},
                    {"role": "user", "content": "Hello!"},
                ]
            },
            created_at=datetime.datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        def mock_obj_read(req):
            return tsi.ObjReadRes(obj=mock_prompt_obj)

        prompt_uri = (
            f"weave-trace-internal:///{self.project_id}/object/test-prompt:digest-1"
        )

        # Test without template vars
        messages = resolve_prompt_messages(
            prompt=prompt_uri,
            project_id=self.project_id,
            obj_read_func=mock_obj_read,
            template_vars=None,
        )

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "You are {assistant_name}.")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "Hello!")

    def test_resolve_prompt_messages_with_template_vars(self):
        """Test resolving prompt messages with template variable substitution."""
        from weave.trace_server.llm_completion import resolve_prompt_messages

        # Create a mock MessagesPrompt object
        mock_prompt_obj = tsi.ObjSchema(
            project_id=self.project_id,
            object_id="test-prompt",
            digest="digest-1",
            base_object_class="MessagesPrompt",
            leaf_object_class="MessagesPrompt",
            val={
                "messages": [
                    {"role": "system", "content": "You are {assistant_name}."},
                    {"role": "user", "content": "My topic is {topic}."},
                ]
            },
            created_at=datetime.datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        def mock_obj_read(req):
            return tsi.ObjReadRes(obj=mock_prompt_obj)

        prompt_uri = (
            f"weave-trace-internal:///{self.project_id}/object/test-prompt:digest-1"
        )
        template_vars = {"assistant_name": "MathBot", "topic": "mathematics"}

        # Test with template vars
        messages = resolve_prompt_messages(
            prompt=prompt_uri,
            project_id=self.project_id,
            obj_read_func=mock_obj_read,
            template_vars=template_vars,
        )

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "You are MathBot.")
        self.assertEqual(messages[1]["content"], "My topic is mathematics.")

    def test_resolve_prompt_messages_invalid_prompt(self):
        """Test error handling when prompt object is not a Prompt or MessagesPrompt."""
        from weave.trace_server.errors import InvalidRequest
        from weave.trace_server.llm_completion import resolve_prompt_messages

        # Create a mock object that is NOT a MessagesPrompt
        mock_not_prompt = tsi.ObjSchema(
            project_id=self.project_id,
            object_id="test-obj",
            digest="digest-1",
            base_object_class="Model",
            leaf_object_class="Model",
            val={"name": "test"},
            created_at=datetime.datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        def mock_obj_read(req):
            return tsi.ObjReadRes(obj=mock_not_prompt)

        prompt_uri = (
            f"weave-trace-internal:///{self.project_id}/object/test-obj:digest-1"
        )

        # Should raise InvalidRequest when object is not a Prompt or MessagesPrompt
        with self.assertRaises(InvalidRequest) as context:
            resolve_prompt_messages(
                prompt=prompt_uri,
                project_id=self.project_id,
                obj_read_func=mock_obj_read,
                template_vars=None,
            )

        self.assertIn("is not a Prompt or MessagesPrompt", str(context.exception))


class TestStreamingWithPrompts(unittest.TestCase):
    """Tests for streaming completions with prompt resolution and template variables."""

    def setUp(self):
        """Set up test fixtures before each test."""
        self.server = chts.ClickHouseTraceServer(host="test_host")
        self.project_id = "test-project"
        self.mock_secret_fetcher = MagicMock()
        self.mock_secret_fetcher.fetch.return_value = {
            "secrets": {"OPENAI_API_KEY": "test-api-key"}
        }
        self.token = _secret_fetcher_context.set(self.mock_secret_fetcher)

    def tearDown(self):
        _secret_fetcher_context.reset(self.token)

    def test_streaming_with_prompt_resolution(self):
        """Test streaming completion with prompt resolution."""
        # Mock the MessagesPrompt object
        mock_prompt_obj = tsi.ObjSchema(
            project_id=self.project_id,
            object_id="test-prompt",
            digest="digest-1",
            base_object_class="MessagesPrompt",
            leaf_object_class="MessagesPrompt",
            val={
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                ]
            },
            created_at=datetime.datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        # Mock response chunks
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
                "model": "gpt-3.5-turbo",
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
                "model": "gpt-3.5-turbo",
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
            patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read,
        ):
            # Mock the litellm completion stream
            mock_stream = MagicMock()
            mock_stream.__iter__.return_value = mock_chunks
            mock_litellm.return_value = mock_stream

            # Mock obj_read to return the prompt
            mock_obj_read.return_value = tsi.ObjReadRes(obj=mock_prompt_obj)

            prompt_uri = (
                f"weave-trace-internal:///{self.project_id}/object/test-prompt:digest-1"
            )

            # Create test request with prompt
            req = tsi.CompletionsCreateReq(
                project_id=self.project_id,
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Hi there"}],
                    prompt=prompt_uri,
                ),
                track_llm_call=False,
            )

            # Get the stream
            stream = self.server.completions_create_stream(req)

            # Collect all chunks
            chunks = list(stream)

            # Verify the chunks
            self.assertEqual(len(chunks), 2)
            self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "Hello")
            self.assertEqual(chunks[1]["choices"][0]["finish_reason"], "stop")

            # Verify obj_read was called to resolve the prompt
            mock_obj_read.assert_called_once()

    def test_streaming_with_prompt_and_template_vars(self):
        """Test streaming completion with prompt resolution and template variables."""
        # Mock the MessagesPrompt object with template variables
        mock_prompt_obj = tsi.ObjSchema(
            project_id=self.project_id,
            object_id="test-prompt",
            digest="digest-1",
            base_object_class="MessagesPrompt",
            leaf_object_class="MessagesPrompt",
            val={
                "messages": [
                    {"role": "system", "content": "You are {assistant_name}."},
                    {"role": "user", "content": "Tell me about {topic}."},
                ]
            },
            created_at=datetime.datetime.now(),
            version_index=1,
            is_latest=1,
            kind="object",
            deleted_at=None,
        )

        # Mock response chunks
        mock_chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": "Mathematics"},
                        "finish_reason": None,
                        "index": 0,
                    }
                ],
                "id": "test-id",
                "model": "gpt-3.5-turbo",
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
                "model": "gpt-3.5-turbo",
                "created": 1234567890,
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 1,
                    "total_tokens": 16,
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

            # Mock obj_read to return the prompt
            mock_obj_read.return_value = tsi.ObjReadRes(obj=mock_prompt_obj)

            prompt_uri = (
                f"weave-trace-internal:///{self.project_id}/object/test-prompt:digest-1"
            )

            # Create test request with prompt and template_vars
            req = tsi.CompletionsCreateReq(
                project_id=self.project_id,
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="gpt-3.5-turbo",
                    messages=[],
                    prompt=prompt_uri,
                    template_vars={"assistant_name": "MathBot", "topic": "mathematics"},
                ),
                track_llm_call=False,
            )

            # Get the stream
            stream = self.server.completions_create_stream(req)

            # Collect all chunks
            chunks = list(stream)

            # Verify the chunks
            self.assertEqual(len(chunks), 2)
            self.assertEqual(chunks[0]["choices"][0]["delta"]["content"], "Mathematics")
            self.assertEqual(chunks[1]["choices"][0]["finish_reason"], "stop")

            # Verify litellm was called with substituted messages
            mock_litellm.assert_called_once()
            call_kwargs = mock_litellm.call_args[1]
            messages = call_kwargs["inputs"].messages

            # Should have 2 messages with template vars replaced
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]["content"], "You are MathBot.")
            self.assertEqual(messages[1]["content"], "Tell me about mathematics.")

    @pytest.mark.disable_logging_error_check
    def test_streaming_with_prompt_error(self):
        """Test error handling when prompt resolution fails during streaming."""
        with patch.object(chts.ClickHouseTraceServer, "obj_read") as mock_obj_read:
            # Mock obj_read to raise an error
            from weave.trace_server.errors import NotFoundError

            mock_obj_read.side_effect = NotFoundError("Prompt not found")

            prompt_uri = f"weave-trace-internal:///{self.project_id}/object/missing-prompt:digest-1"

            # Create test request with non-existent prompt
            req = tsi.CompletionsCreateReq(
                project_id=self.project_id,
                inputs=tsi.CompletionsCreateRequestInputs(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Hi"}],
                    prompt=prompt_uri,
                ),
                track_llm_call=False,
            )

            # Get the stream
            stream = self.server.completions_create_stream(req)

            # Collect all chunks - should get error chunk
            chunks = list(stream)

            # Should have exactly one error chunk
            self.assertEqual(len(chunks), 1)
            self.assertIn("error", chunks[0])
            self.assertIn("Failed to resolve prompt", chunks[0]["error"])


if __name__ == "__main__":
    unittest.main()
