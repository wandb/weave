import datetime
import unittest
from unittest.mock import MagicMock

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest, NotFoundError
from weave.trace_server.llm_completion import get_custom_provider_info
from weave.trace_server.secret_fetcher_context import (
    _secret_fetcher_context,
)


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

        # Set up the mock_obj_read_func to return test objects
        def mock_obj_read(req):
            if req.object_id == self.provider_id:
                return tsi.ObjReadRes(obj=self.provider_obj)
            elif req.object_id == f"{self.provider_id}-{self.model_id}":
                return tsi.ObjReadRes(obj=self.provider_model_obj)
            raise NotFoundError(f"Unknown object_id: {req.object_id}")

        self.mock_obj_read_func.side_effect = mock_obj_read

        # Use the context manager to set the secret fetcher
        token = _secret_fetcher_context.set(self.mock_secret_fetcher)
        try:
            # Call the function under test
            base_url, api_key, extra_headers, return_type, actual_model_name = (
                get_custom_provider_info(
                    project_id=self.project_id,
                    model_name=self.model_name,
                    obj_read_func=self.mock_obj_read_func,
                )
            )

            # Verify all returned values match expected configuration
            self.assertEqual(
                base_url,
                "https://api.example.com",
                f"Base URL mismatch. Expected 'https://api.example.com', got '{base_url}'",
            )
            self.assertEqual(
                api_key,
                "test-api-key-value",
                f"API key mismatch. Expected 'test-api-key-value', got '{api_key}'",
            )
            self.assertEqual(
                extra_headers,
                {"X-Header": "value"},
                f"Extra headers mismatch. Expected {{'X-Header': 'value'}}, got {extra_headers}",
            )
            self.assertEqual(
                return_type,
                "openai",
                f"Return type mismatch. Expected 'openai', got '{return_type}'",
            )
            self.assertEqual(
                actual_model_name,
                "actual-model-name",
                f"Model name mismatch. Expected 'actual-model-name', got '{actual_model_name}'",
            )

            # Verify correct object read calls were made
            self.mock_obj_read_func.assert_any_call(
                tsi.ObjReadReq(
                    project_id=self.project_id,
                    object_id=self.provider_id,
                    digest="latest",
                    metadata_only=False,
                )
            )
            self.mock_obj_read_func.assert_any_call(
                tsi.ObjReadReq(
                    project_id=self.project_id,
                    object_id=f"{self.provider_id}-{self.model_id}",
                    digest="latest",
                    metadata_only=False,
                )
            )

            # Verify secret fetch was called correctly
            self.mock_secret_fetcher.fetch.assert_called_once_with("TEST_API_KEY")
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


if __name__ == "__main__":
    unittest.main()
