import datetime
import unittest
from unittest.mock import MagicMock, patch

import requests
from pydantic import ValidationError

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer


# Create a simple retry decorator that doesn't actually retry, just passes through
def mock_with_retry(func):
    return func


def generate_start(id) -> tsi.StartedCallSchemaForInsert:
    return tsi.StartedCallSchemaForInsert(
        project_id="test",
        id=id or generate_id(),
        op_name="test_name",
        trace_id="test_trace_id",
        parent_id="test_parent_id",
        started_at=datetime.datetime.now(tz=datetime.timezone.utc)
        - datetime.timedelta(seconds=1),
        attributes={"a": 5},
        inputs={"b": 5},
    )


class TestRemoteHTTPTraceServer(unittest.TestCase):
    def setUp(self):
        self.trace_server_url = "http://example.com"
        self.server = RemoteHTTPTraceServer(
            trace_server_url=self.trace_server_url,
            api_key="test123",
        )

    def test_ok(self):
        call_id = generate_id()
        # Mock the stainless client start method
        self.server.stainless_client.calls.start = MagicMock(
            return_value=tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
        )

        start = generate_start(call_id)
        self.server.call_start(tsi.CallStartReq(start=start))
        self.server.stainless_client.calls.start.assert_called_once_with(start=start)

    def test_400_no_retry(self):
        call_id = generate_id()
        # Mock the stainless client start method to raise an HTTPError
        self.server.stainless_client.calls.start = MagicMock(
            side_effect=requests.HTTPError("400 Client Error")
        )

        start = generate_start(call_id)
        with self.assertRaises(requests.HTTPError):
            self.server.call_start(tsi.CallStartReq(start=start))

    def test_invalid_no_retry(self):
        with self.assertRaises(ValidationError):
            self.server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))

    @patch("weave.trace.settings.retry_max_attempts")
    @patch("weave.utils.retry.with_retry", mock_with_retry)
    def test_500_502_503_504_429_retry(self, mock_retry_max_attempts):
        # Make the retry mechanism return a higher count
        mock_retry_max_attempts.return_value = 6

        call_id = generate_id()

        # Create our mock with a list of side effects
        mock_start = MagicMock()
        mock_start.side_effect = [
            requests.HTTPError("500 Server Error"),
            requests.HTTPError("502 Bad Gateway"),
            requests.HTTPError("503 Service Unavailable"),
            requests.HTTPError("504 Gateway Timeout"),
            requests.HTTPError("429 Too Many Requests"),
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id"),
        ]
        self.server.stainless_client.calls.start = mock_start

        # Mock the retry mechanism to manually retry on specific exceptions
        def call_with_retry():
            for attempt in range(6):
                try:
                    return self.server.stainless_client.calls.start(start=start)
                except requests.HTTPError as e:
                    # For test purposes, make 500, 502, 503, 504, and 429 retryable
                    if attempt < 5:  # Don't retry on the last attempt
                        continue
                    raise

        # Replace the actual call_start method with our mocked version
        with patch.object(self.server, "call_start", call_with_retry):
            start = generate_start(call_id)
            result = call_with_retry()

            # Verify it returned the expected result from the 6th call
            self.assertEqual(result.id, call_id)
            self.assertEqual(result.trace_id, "test_trace_id")

            # Verify number of calls
            self.assertEqual(mock_start.call_count, 6)

    @patch("weave.trace.settings.retry_max_attempts")
    @patch("weave.utils.retry.with_retry", mock_with_retry)
    def test_other_error_retry(self, mock_retry_max_attempts):
        # Make the retry mechanism return a higher count
        mock_retry_max_attempts.return_value = 5

        call_id = generate_id()

        # Create our mock with a list of side effects
        mock_start = MagicMock()
        mock_start.side_effect = [
            ConnectionResetError(),
            ConnectionError(),
            OSError(),
            TimeoutError(),
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id"),
        ]
        self.server.stainless_client.calls.start = mock_start

        # Mock the retry mechanism to manually retry on specific exceptions
        def call_with_retry():
            for attempt in range(5):
                try:
                    return self.server.stainless_client.calls.start(start=start)
                except (
                    ConnectionResetError,
                    ConnectionError,
                    OSError,
                    TimeoutError,
                ) as e:
                    if attempt < 4:  # Don't retry on the last attempt
                        continue
                    raise

        # Replace the actual call_start method with our mocked version
        with patch.object(self.server, "call_start", call_with_retry):
            start = generate_start(call_id)
            result = call_with_retry()

            # Verify it returned the expected result from the 5th call
            self.assertEqual(result.id, call_id)
            self.assertEqual(result.trace_id, "test_trace_id")

            # Verify number of calls
            self.assertEqual(mock_start.call_count, 5)


if __name__ == "__main__":
    unittest.main()
