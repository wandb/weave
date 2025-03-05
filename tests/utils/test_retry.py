import unittest
from unittest.mock import MagicMock, patch

import weave.utils.retry as retry


class TestRetry(unittest.TestCase):
    @patch("weave.utils.retry.retry_max_attempts")
    @patch("weave.utils.retry.retry_max_interval")
    def test_settings_are_used(self, mock_retry_max_interval, mock_retry_max_attempts):
        # Mocking the settings functions to return specific values
        mock_retry_max_attempts.return_value = 5
        mock_retry_max_interval.return_value = 20

        # Create a decorated function
        @retry.with_retry
        def test_func():
            return "test"

        # Call the function to trigger the retry code
        test_func()

        # Verify our mocks were called
        mock_retry_max_attempts.assert_called()
        mock_retry_max_interval.assert_called()

    @patch("weave.utils.retry.tenacity.Retrying")
    def test_retry_creates_correct_instance(self, mock_retrying):
        """Test that with_retry creates the Retrying instance with correct parameters."""
        # Make the retry instance callable and return the function's result
        mock_retry_instance = MagicMock()
        mock_retrying.return_value = mock_retry_instance
        mock_retry_instance.side_effect = lambda f: f()

        # Create a decorated function
        @retry.with_retry
        def test_func():
            return "test result"

        # Call the function to trigger the retry code
        result = test_func()

        # Verify the result
        self.assertEqual(result, "test result")

        # Verify Retrying was called with appropriate parameters
        mock_retrying.assert_called_once()
        call_kwargs = mock_retrying.call_args[1]

        # Check that required parameters are present
        self.assertIn("stop", call_kwargs)
        self.assertIn("wait", call_kwargs)
        self.assertIn("retry", call_kwargs)
        self.assertIn("before_sleep", call_kwargs)
        self.assertIn("retry_error_callback", call_kwargs)

        # Check that reraise is True
        self.assertTrue(call_kwargs["reraise"])


if __name__ == "__main__":
    unittest.main()
