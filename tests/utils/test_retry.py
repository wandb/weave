from __future__ import annotations

from unittest.mock import MagicMock, patch

import weave.utils.retry as retry


@patch("weave.utils.retry.retry_max_attempts")
@patch("weave.utils.retry.retry_max_interval")
def test_settings_are_used(mock_retry_max_attempts, mock_retry_max_interval):
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
def test_retry_creates_correct_instance(mock_retrying):
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
    assert result == "test result"

    # Verify Retrying was called with appropriate parameters
    mock_retrying.assert_called_once()
    call_kwargs = mock_retrying.call_args[1]

    # Check that required parameters are present
    assert "stop" in call_kwargs
    assert "wait" in call_kwargs
    assert "retry" in call_kwargs
    assert "before_sleep" in call_kwargs
    assert "retry_error_callback" in call_kwargs

    # Check that reraise is True
    assert call_kwargs["reraise"] is True
