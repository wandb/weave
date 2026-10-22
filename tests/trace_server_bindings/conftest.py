import datetime
from collections.abc import Mapping
from types import MethodType
from typing import Any
from unittest.mock import MagicMock

import pydantic
import pytest
import tenacity

from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)
from weave.utils.ids import generate_id
from weave.vendor.weave_server_sdk.types import (
    CallEndParams,
    CallStartParams,
    call_end_params,
    call_start_params,
)

# =============================================================================
# Test Data Generators
# =============================================================================


def generate_start(
    id: str | None = None,
    project_id: str = "test",
) -> call_start_params.Start:
    """Generate a test call start."""
    return {
        "project_id": project_id,
        "id": id or generate_id(),
        "op_name": "test_name",
        "trace_id": "test_trace_id",
        "parent_id": "test_parent_id",
        "started_at": datetime.datetime.now(tz=datetime.timezone.utc),
        "attributes": {"a": 5},
        "inputs": {"b": 5},
    }


def generate_end(
    id: str | None = None,
    project_id: str = "test",
) -> call_end_params.End:
    """Generate a test call end."""
    return {
        "project_id": project_id,
        "id": id or generate_id(),
        "ended_at": datetime.datetime.now(tz=datetime.timezone.utc)
        + datetime.timedelta(seconds=1),
        "output": {"c": 5},
        "exception": None,
        "summary": {"result": "Test summary"},
    }


def generate_call_start_end_pair(
    id: str | None = None,
    project_id: str = "test",
) -> tuple[CallStartParams, CallEndParams]:
    """Generate a matching pair of call start and end requests for testing."""
    start = generate_start(id, project_id)
    end = generate_end(id, project_id)
    return {"start": start}, {"end": end}


def request_model(fields: Mapping[str, Any]) -> pydantic.BaseModel:
    """Stand in for a caller's own pydantic request model with these fields."""
    model = pydantic.create_model("RequestModel", **dict.fromkeys(fields, (Any, ...)))
    return model(**fields)


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
def server(request):
    """A batching RemoteHTTPTraceServer, set up by `request.param`."""
    server_ = RemoteHTTPTraceServer("http://example.com", should_batch=True)

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
