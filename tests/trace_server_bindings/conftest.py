import datetime
from importlib.util import find_spec
from types import MethodType
from unittest.mock import MagicMock

import pytest
import tenacity

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)

HAS_STAINLESS = find_spec("weave_server_sdk") is not None

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
# Fixtures
# =============================================================================


@pytest.fixture
def success_response():
    """Common fixture for mocking a successful HTTP response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "test_id", "trace_id": "test_trace_id"}
    return response


@pytest.fixture
def server_class(request):
    """Returns the appropriate server class based on --remote-http-trace-server flag."""
    flag = request.config.getoption("--remote-http-trace-server", default="remote")
    if flag == "stainless":
        if not HAS_STAINLESS:
            pytest.skip(
                "weave_server_sdk is required for stainless trace server tests. "
                "Install it with `pip install \"weave[stainless]\"`."
            )
        return StainlessRemoteHTTPTraceServer
    return RemoteHTTPTraceServer


@pytest.fixture
def server(request, server_class):
    """Common server fixture that uses server_class based on the CLI flag."""
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


def pytest_ignore_collect(collection_path, config):
    """Ignore test files based on --remote-http-trace-server flag.

    This runs before collection, preventing files from being imported at all.
    """
    if "trace_server_bindings" not in collection_path.parts:
        return None

    flag = config.getoption("--remote-http-trace-server", default="remote")
    filename = collection_path.name

    if flag == "remote" and filename.endswith("_stainless.py"):
        return True
    if flag == "stainless" and filename.endswith("_remote.py"):
        return True

    return None


def pytest_collection_modifyitems(config, items):
    """Add trace_server marker to all tests in this directory."""
    for item in items:
        if "trace_server_bindings" in item.path.parts:
            item.add_marker(pytest.mark.trace_server)
