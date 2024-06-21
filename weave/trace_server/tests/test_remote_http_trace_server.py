import datetime
import unittest
import uuid
from unittest.mock import patch

import requests
from pydantic import ValidationError

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.remote_http_trace_server import RemoteHTTPTraceServer


def generate_id() -> str:
    return str(uuid.uuid4())


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
        self.server = RemoteHTTPTraceServer(self.trace_server_url)

    @patch("requests.post")
    def test_ok(self, mock_post):
        call_id = generate_id()
        mock_post.return_value = requests.Response()
        mock_post.return_value.json = lambda: dict(
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
        )
        mock_post.return_value.status_code = 200
        start = generate_start(call_id)
        self.server.call_start(tsi.CallStartReq(start=start))
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_400_500_no_retry(self, mock_post):
        call_id = generate_id()
        resp1 = requests.Response()
        resp1.json = lambda: dict(
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
        )
        resp1.status_code = 400

        resp2 = requests.Response()
        resp2.status_code = 500

        mock_post.side_effect = [
            resp1,
            resp2,
        ]

        start = generate_start(call_id)
        with self.assertRaises(requests.HTTPError):
            self.server.call_start(tsi.CallStartReq(start=start))

        with self.assertRaises(requests.HTTPError):
            self.server.call_start(tsi.CallStartReq(start=start))

    def test_invalid_no_retry(self):
        with self.assertRaises(ValidationError):
            self.server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))

    @patch("requests.post")
    def test_502_503_504_429_retry(self, mock_post):
        call_id = generate_id()

        resp1 = requests.Response()
        resp1.status_code = 502

        resp2 = requests.Response()
        resp2.status_code = 503

        resp3 = requests.Response()
        resp3.status_code = 504

        resp4 = requests.Response()
        resp4.status_code = 429

        resp5 = requests.Response()
        resp5.json = lambda: dict(
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
        )
        resp5.status_code = 200

        mock_post.side_effect = [resp1, resp2, resp3, resp4, resp5]
        start = generate_start(call_id)
        self.server.call_start(tsi.CallStartReq(start=start))

    @patch("requests.post")
    def test_other_error_retry(self, mock_post):
        call_id = generate_id()

        resp2 = requests.Response()
        resp2.json = lambda: dict(
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
        )
        resp2.status_code = 200

        mock_post.side_effect = [
            ConnectionResetError(),
            ConnectionError(),
            OSError(),
            TimeoutError(),
            resp2,
        ]
        start = generate_start(call_id)
        self.server.call_start(tsi.CallStartReq(start=start))


if __name__ == "__main__":
    unittest.main()
