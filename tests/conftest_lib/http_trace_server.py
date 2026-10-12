from __future__ import annotations

import datetime
import os
from collections.abc import Callable

import httpx
import pytest

from tests.conftest_lib.http_error_decoding import HTTPErrorDecodingTraceServer
from tests.trace.server_utils import TEST_ENTITY
from weave.shared import common_interface
from weave.shared import trace_server_interface as tsi
from weave.shared.ids import generate_id
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer
from weave.wandb_interface import project_creator
from weave.wandb_interface.auth import ApiKeyCredentials


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--remote-http-trace-server",
            action="store",
            default="remote",
            help="Specify the remote HTTP trace server implementation: remote or stainless",
        )
    except ValueError:
        pass


def pytest_configure(config):
    # The reset clears the whole database, so each xdist worker (gw0, gw1, ...)
    # takes its own server from the comma-separated list.
    urls = os.environ.get("WEAVE_TEST_TRACE_SERVER_URLS")
    if not urls:
        return
    servers = urls.split(",")
    workers = len(config.getoption("tx", None) or [])
    if workers > len(servers):
        raise pytest.UsageError(
            f"{workers} xdist workers, but WEAVE_TEST_TRACE_SERVER_URLS lists "
            f"{len(servers)} servers"
        )
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker:
        return
    index = int(worker.removeprefix("gw"))
    if index >= len(servers):
        # xdist numbers a worker that replaces a crashed one past the others.
        raise pytest.UsageError(f"{worker} replaced a crashed worker; no server left")
    os.environ["WF_TRACE_SERVER_URL"] = servers[index]


_crashed_workers: list[str] = []


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    if error is not None:
        _crashed_workers.append(node.gateway.id)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    # xdist exits 0 when a worker dies before collecting, and the worker that
    # replaces it has no server, so a crash must fail the run. trylast: after
    # tests/conftest.py turns exit 5 into 0.
    if _crashed_workers and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_collection_modifyitems(config, items):
    # Add the trace_server marker to all tests that use the trace_server fixture.
    # Note: Filtering based on remote-http-trace-server flag is handled in tests/trace_server_bindings/conftest.py
    for item in items:
        if "trace_server" in item.fixturenames:
            item.add_marker(pytest.mark.trace_server)


@pytest.fixture(autouse=True)
def reset_extra_field_warnings():
    """The memo of reported ignored-field sets would silence later tests."""
    common_interface._warned_field_sets.clear()
    yield
    common_interface._warned_field_sets.clear()


# The user id the HTTP server stamps on writes, keyed by server url. The
# server derives it from the API key, so one probe per session is enough.
_http_user_ids: dict[str, str] = {}


def _probe_http_user_id(server: RemoteHTTPTraceServer) -> str:
    """Write one call and read back the user id the server stamped on it."""
    project_id = f"{TEST_ENTITY}/test-project"
    call_id = generate_id()
    server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                op_name="probe_user_id",
                trace_id=generate_id(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={},
                inputs={},
            )
        )
    )
    user_id = server.call_read(
        tsi.CallReadReq(project_id=project_id, id=call_id)
    ).call.wb_user_id
    assert user_id is not None
    return user_id


@pytest.fixture
def trace_server() -> HTTPErrorDecodingTraceServer:
    """A trace server reached over HTTP, reset before each test.

    WF_TRACE_SERVER_URL must point at core's resettable test app, and
    WANDB_API_KEY must belong to a user named TEST_ENTITY.
    """
    url = os.environ["WF_TRACE_SERVER_URL"]
    server = RemoteHTTPTraceServer(
        url, auth=ApiKeyCredentials(os.environ["WANDB_API_KEY"])
    )
    if url not in _http_user_ids:
        httpx.post(f"{url}/testonly/reset").raise_for_status()
        _http_user_ids[url] = _probe_http_user_id(server)
    httpx.post(f"{url}/testonly/reset").raise_for_status()
    return HTTPErrorDecodingTraceServer(server)


@pytest.fixture
def ensure_project(trace_server) -> Callable[[str], str]:
    """Return the id of a project called `name` under TEST_ENTITY that exists.

    The server resolves the project in W&B first, so the fixture creates it
    there, through the W&B API at WANDB_BASE_URL.
    """

    def ensure_project_inner(name: str) -> str:
        project_creator.ensure_project_exists(TEST_ENTITY, name)
        return f"{TEST_ENTITY}/{name}"

    return ensure_project_inner


@pytest.fixture
def wb_user_id(trace_server) -> str:
    """The user id the backend stamps on everything the test writes."""
    return _http_user_ids[os.environ["WF_TRACE_SERVER_URL"]]
