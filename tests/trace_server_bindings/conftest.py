import datetime
from types import MethodType
from unittest.mock import MagicMock

import httpx
import pytest
import tenacity
from weave_server_sdk import models as tsi

from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)

# =============================================================================
# Test Data Generators
# =============================================================================


def generate_start(
    id: str | None = None,
    project_id: str = "test",
) -> tsi.StartedCallSchemaForInsert:
    """Generate a test StartedCallSchemaForInsert."""
    return tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=id or generate_id(),
        op_name="test_name",
        trace_id="test_trace_id",
        parent_id="test_parent_id",
        started_at=datetime.datetime.now(tz=datetime.timezone.utc),
        attributes={"a": 5},
        inputs={"b": 5},
    )


def generate_end(
    id: str | None = None,
    project_id: str = "test",
) -> tsi.EndedCallSchemaForInsert:
    """Generate a test EndedCallSchemaForInsert."""
    return tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=id or generate_id(),
        ended_at=datetime.datetime.now(tz=datetime.timezone.utc)
        + datetime.timedelta(seconds=1),
        outputs={"c": 5},
        error=None,
        summary={"result": "Test summary"},
    )


def generate_call_start_end_pair(
    id: str | None = None,
    project_id: str = "test",
) -> tuple[tsi.CallStartReq, tsi.CallEndReq]:
    """Generate a matching pair of CallStartReq and CallEndReq for testing."""
    start = generate_start(id, project_id)
    end = generate_end(id, project_id)
    return tsi.CallStartReq(start=start), tsi.CallEndReq(end=end)


# =============================================================================
# HTTP transport spy
# =============================================================================


class SpyTransport(httpx.BaseTransport):
    """httpx transport that records requests and replays queued responses.

    Queue items may be ``httpx.Response`` objects or exceptions to raise.
    When the queue is empty, returns ``default_response`` (200 ``{}`` unless
    overridden).
    """

    def __init__(
        self,
        *items: httpx.Response | Exception,
        default_response: httpx.Response | None = None,
    ) -> None:
        self.queue: list[httpx.Response | Exception] = list(items)
        self.requests: list[httpx.Request] = []
        self.default_response = default_response

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if self.default_response is not None:
            return self.default_response
        return httpx.Response(200, json={})

    @property
    def urls(self) -> list[str]:
        return [str(r.url) for r in self.requests]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def server_class():
    """The remote trace server implementation under test."""
    return RemoteHTTPTraceServer


@pytest.fixture
def server(request, server_class):
    """Common server fixture parametrized by batching/retry behavior."""
    server_ = server_class("http://example.com", should_batch=True)

    if request.param == "normal":
        server_._send_batch_to_server = MagicMock()
    elif request.param == "small_limit":
        server_.remote_request_bytes_limit = 1024  # 1kb
        server_._send_batch_to_server = MagicMock()
    elif request.param == "fast_retrying":
        fast_retry = tenacity.retry(
            wait=tenacity.wait_fixed(0.1),
            stop=tenacity.stop_after_attempt(2),
            reraise=True,
        )
        unwrapped_send_batch_to_server = MethodType(
            server_._send_batch_to_server.__wrapped__,  # type: ignore[attr-defined]
            server_,
        )
        server_._send_batch_to_server = fast_retry(unwrapped_send_batch_to_server)

    yield server_

    if server_.call_processor:
        server_.call_processor.stop_accepting_new_work_and_flush_queue()
    if server_.feedback_processor:
        server_.feedback_processor.stop_accepting_new_work_and_flush_queue()


def pytest_collection_modifyitems(config, items):
    """Add trace_server marker to all tests in this directory."""
    for item in items:
        if "trace_server_bindings" in item.path.parts:
            item.add_marker(pytest.mark.trace_server)
