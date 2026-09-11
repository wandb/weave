from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from weave.utils import retry
from weave.vendor.weave_server_sdk import APIStatusError


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


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [
        (400, False),
        (401, False),
        (403, False),
        (404, False),
        (422, False),
        (429, True),
        (500, True),
    ],
)
def test_status_errors_are_classified_by_status_code(status_code, retryable):
    """The Stainless client's error is classified like the httpx one."""
    request = httpx.Request("POST", "http://example.com")
    response = httpx.Response(status_code, json={}, request=request)

    assert (
        retry._is_retryable_exception(
            APIStatusError(str(status_code), response=response, body=None)
        )
        is retryable
    )
    assert (
        retry._is_retryable_exception(
            httpx.HTTPStatusError(str(status_code), request=request, response=response)
        )
        is retryable
    )
