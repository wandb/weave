import datetime
import unittest
from unittest.mock import patch
import uuid

from pydantic import ValidationError
import requests
from weave.trace_server.remote_http_trace_server import RemoteHTTPTraceServer
from weave.trace_server import trace_server_interface as tsi


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
    def test_400_no_retry(self, mock_post):
        call_id = generate_id()
        mock_post.return_value = requests.Response()
        mock_post.return_value.json = lambda: dict(
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
        )
        mock_post.return_value.status_code = 400
        start = generate_start(call_id)
        with self.assertRaises(requests.HTTPError):
            self.server.call_start(tsi.CallStartReq(start=start))

    def test_invalid_no_retry(self):
        call_id = generate_id()
        with self.assertRaises(ValidationError):
            self.server.call_start(tsi.CallStartReq(start={"invalid": "broken"}))

    @patch("requests.post")
    def test_500_retry(self, mock_post):
        call_id = generate_id()

        resp1 = requests.Response()
        resp1.status_code = 500

        resp2 = requests.Response()
        resp2.json = lambda: dict(
            tsi.CallStartRes(id=call_id, trace_id="test_trace_id")
        )
        resp2.status_code = 200

        mock_post.side_effect = [
            resp1,
            resp2,
        ]
        start = generate_start(call_id)
        self.server.call_start(tsi.CallStartReq(start=start))


if __name__ == "__main__":
    unittest.main()
