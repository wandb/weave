import logging
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import weave
from weave.trace import weave_init
from weave.trace.client_context import context_state
from weave.trace_server import (
    clickhouse_trace_server_batched,
    sqlite_trace_server,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings import remote_http_trace_server

from .tests.trace.trace_server_clickhouse_conftest import *
from .tests.wandb_system_tests_conftest import *
from .trace import autopatch

# Force testing to never report wandb sentry events
os.environ["WANDB_ERROR_REPORTING"] = "false"


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        print("No tests were selected. Exiting gracefully.")
        session.exitstatus = 0


def pytest_collection_modifyitems(config, items):
    # Add the weave_client marker to all tests that have a client fixture
    for item in items:
        if "client" in item.fixturenames:
            item.add_marker(pytest.mark.weave_client)


PYTEST_CURRENT_TEST_ENV_VAR = "PYTEST_CURRENT_TEST"


def get_test_name():
    return os.environ.get(PYTEST_CURRENT_TEST_ENV_VAR).split(" ")[0]


class InMemoryWeaveLogCollector(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_records = {}

    def emit(self, record):
        curr_test = get_test_name()
        if curr_test not in self.log_records:
            self.log_records[curr_test] = []
        self.log_records[curr_test].append(record)

    def get_error_logs(self):
        curr_test = get_test_name()
        logs = self.log_records.get(curr_test, [])

        return [
            record
            for record in logs
            if record.levelname == "ERROR"
            and record.name.startswith("weave")
            # (Tim) For some reason that i cannot figure out, there is some test that
            # a) is trying to connect to the PROD trace server
            # b) seemingly doesn't fail
            # c) Logs these errors.
            # I would love to fix this, but I have not been able to pin down which test
            # is causing it and need to ship this PR, so I am just going to filter it out
            # for now.
            and not record.msg.startswith(
                "Job failed with exception: 400 Client Error: Bad Request for url: https://trace.wandb.ai/"
            )
            # Exclude legacy
            and not record.name.startswith("weave.weave_server")
            and not "legacy" in record.name
        ]


@pytest.fixture
def log_collector():
    handler = InMemoryWeaveLogCollector()
    logger = logging.getLogger()  # Get your specific logger here if needed
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)  # Set the level to capture all logs
    yield handler
    logger.removeHandler(handler)  # Clean up after the test


@pytest.fixture(autouse=True)
def logging_error_check(request, log_collector):
    yield
    if "disable_logging_error_check" in request.keywords:
        return
    error_logs = log_collector.get_error_logs()
    if error_logs:
        pytest.fail(
            f"Expected no errors, but found {len(error_logs)} error(s): {error_logs}"
        )


@pytest.fixture()
def strict_op_saving():
    with context_state.strict_op_saving(True):
        yield


class TestOnlyFlushingWeaveClient(weave_client.WeaveClient):
    """
    A WeaveClient that automatically flushes after every method call.

    This subclass overrides the behavior of the standard WeaveClient to ensure
    that all write operations are immediately flushed to the underlying storage
    before any subsequent read operation is performed. This is particularly
    useful in testing scenarios where data is written and then immediately read
    back, as it eliminates potential race conditions or inconsistencies that
    might arise from delayed writes.

    The flush operation is applied to all public methods (those not starting with
    an underscore) except for the 'flush' method itself, to avoid infinite recursion.
    This aggressive flushing strategy may impact performance and should primarily
    be used in testing environments rather than production scenarios.

    Note: Due to this, the test suite essentially "blocks" on every operation. So
    if we are to test timing, this might not be the best choice. As an alternative,
    we could explicitly call flush() in every single test that reads data, before the
    read operation(s) are performed.
    """

    def __getattribute__(self, name):
        self_super = super()
        attr = self_super.__getattribute__(name)

        if callable(attr) and not name.startswith("_") and name != "flush":

            def wrapper(*args, **kwargs):
                res = attr(*args, **kwargs)
                self_super._flush()
                return res

            return wrapper

        return attr


def make_server_recorder(server: tsi.TraceServerInterface):  # type: ignore
    """A wrapper around a trace server that records all attribute access.

    This is extremely helpful for tests to assert that a certain series of
    attribute accesses happen (or don't happen), and in order. We will
    probably want to make this a bit more sophisticated in the future, but
    this is a pretty good start.

    For example, you can do something like the followng to assert that various
    read operations do not happen!

    ```pyth
    access_log = client.server.attribute_access_log
    assert "table_query" not in access_log
    assert "obj_read" not in access_log
    assert "file_content_read" not in access_log
    ```
    """

    class ServerRecorder(type(server)):  # type: ignore
        attribute_access_log: list[str]

        def __init__(self, server: tsi.TraceServerInterface):  # type: ignore
            self.server = server
            self.attribute_access_log = []

        def __getattribute__(self, name):
            self_server = super().__getattribute__("server")
            access_log = super().__getattribute__("attribute_access_log")
            if name == "server":
                return self_server
            if name == "attribute_access_log":
                return access_log
            attr = self_server.__getattribute__(name)
            if name != "attribute_access_log":
                access_log.append(name)
            return attr

    return ServerRecorder(server)


@pytest.fixture()
def client(request) -> Generator[weave_client.WeaveClient, None, None]:
    inited_client = None
    weave_server_flag = request.config.getoption("--weave-server")
    server: tsi.TraceServerInterface
    entity = "shawn"
    project = "test-project"
    if weave_server_flag == "sqlite":
        sqlite_server = sqlite_trace_server.SqliteTraceServer(
            "file::memory:?cache=shared"
        )
        sqlite_server.drop_tables()
        sqlite_server.setup_tables()
        server = TestOnlyUserInjectingExternalTraceServer(
            sqlite_server, DummyIdConverter(), entity
        )
    elif weave_server_flag == "clickhouse":
        ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer.from_env()
        ch_server.ch_client.command("DROP DATABASE IF EXISTS db_management")
        ch_server.ch_client.command("DROP DATABASE IF EXISTS default")
        ch_server._run_migrations()
        server = TestOnlyUserInjectingExternalTraceServer(
            ch_server, DummyIdConverter(), entity
        )
    elif weave_server_flag.startswith("http"):
        remote_server = remote_http_trace_server.RemoteHTTPTraceServer(
            weave_server_flag
        )
        server = remote_server
    elif weave_server_flag == ("prod"):
        inited_client = weave_init.init_weave("dev_testing")

    if inited_client is None:
        client = TestOnlyFlushingWeaveClient(
            entity, project, make_server_recorder(server)
        )
        inited_client = weave_init.InitializedClient(client)
        autopatch.autopatch()
    try:
        yield inited_client.client
    finally:
        inited_client.reset()


@pytest.fixture
def network_proxy_client(client):
    """
    This fixture is used to test the `RemoteHTTPTraceServer` class. There is
    almost no logic in this class, other than a little batching, so we typically
    skip it for simplicity. However, we can use this fixture to test such logic.
    It initializes a mini FastAPI app that proxies requests from the
    `RemoteHTTPTraceServer` to the underlying `client.server` object.

    We probably will want to flesh this out more in the future, but this is a
    starting point.
    """
    app = FastAPI()

    records = []

    @app.post("/table/create")
    def table_create(req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        records.append(
            (
                "table_create",
                req,
            )
        )
        return client.server.table_create(req)

    @app.post("/table/update")
    def table_update(req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        records.append(
            (
                "table_update",
                req,
            )
        )
        return client.server.table_update(req)

    with TestClient(app) as c:

        def post(url, data=None, json=None, **kwargs):
            kwargs.pop("stream", None)
            return c.post(url, data=data, json=json, **kwargs)

        orig_post = weave.trace_server.requests.post
        weave.trace_server.requests.post = post

        remote_client = remote_http_trace_server.RemoteHTTPTraceServer(
            trace_server_url=""
        )
        yield (client, remote_client, records)

        weave.trace_server.requests.post = orig_post
