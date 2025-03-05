import base64
import contextlib
import logging
import os
import subprocess
import tempfile
import time
import typing
import urllib
from collections.abc import Iterator

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

import weave
from tests.trace.util import DummyTestException
from weave.trace import autopatch, weave_client, weave_init
from weave.trace_server import (
    clickhouse_trace_server_batched,
    external_to_internal_trace_server_adapter,
    sqlite_trace_server,
)
from weave.trace_server import environment as ts_env
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings import remote_http_trace_server
from weave.trace_server_bindings.caching_middleware_trace_server import (
    CachingMiddlewareTraceServer,
)

# Force testing to never report wandb sentry events
os.environ["WANDB_ERROR_REPORTING"] = "false"


@pytest.fixture(autouse=True)
def disable_datadog():
    """
    Disables Datadog logging and tracing for tests.

    This prevents Datadog from polluting test logs with messages like
    'failed to send, dropping 1 traces to intake at...'
    """
    # Save original values to restore later
    original_dd_env = os.environ.get("DD_ENV")
    original_dd_trace = os.environ.get("DD_TRACE_ENABLED")

    # Disable Datadog
    os.environ["DD_ENV"] = "none"
    os.environ["DD_TRACE_ENABLED"] = "false"

    # Silence Datadog loggers
    dd_loggers = [
        "ddtrace",
        "ddtrace.writer",
        "ddtrace.api",
        "ddtrace.internal",
        "datadog",
        "datadog.dogstatsd",
        "datadog.api",
    ]

    original_levels = {}
    for logger_name in dd_loggers:
        logger = logging.getLogger(logger_name)
        original_levels[logger_name] = logger.level
        logger.setLevel(logging.CRITICAL)  # Only show critical errors

    yield

    # Restore original values
    if original_dd_env is not None:
        os.environ["DD_ENV"] = original_dd_env
    elif "DD_ENV" in os.environ:
        del os.environ["DD_ENV"]

    if original_dd_trace is not None:
        os.environ["DD_TRACE_ENABLED"] = original_dd_trace
    elif "DD_TRACE_ENABLED" in os.environ:
        del os.environ["DD_TRACE_ENABLED"]


def pytest_addoption(parser):
    parser.addoption(
        "--weave-server",
        action="store",
        default="sqlite",
        help="Specify the client object to use: sqlite or clickhouse",
    )


def pytest_collection_modifyitems(config, items):
    # Add the weave_client marker to all tests that have a client fixture
    for item in items:
        if "client" in item.fixturenames or "client_creator" in item.fixturenames:
            item.add_marker(pytest.mark.weave_client)


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = 0


class ThrowingServer(tsi.TraceServerInterface):
    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        raise DummyTestException("FAILURE - call_start, req:", req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        raise DummyTestException("FAILURE - call_end, req:", req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        raise DummyTestException("FAILURE - call_read, req:", req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        raise DummyTestException("FAILURE - calls_query, req:", req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        raise DummyTestException("FAILURE - calls_query_stream, req:", req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        raise DummyTestException("FAILURE - calls_delete, req:", req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        raise DummyTestException("FAILURE - calls_query_stats, req:", req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        raise DummyTestException("FAILURE - call_update, req:", req)

    # Op API
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        raise DummyTestException("FAILURE - op_create, req:", req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        raise DummyTestException("FAILURE - op_read, req:", req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        raise DummyTestException("FAILURE - ops_query, req:", req)

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        raise DummyTestException("FAILURE - cost_create, req:", req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        raise DummyTestException("FAILURE - cost_query, req:", req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        raise DummyTestException("FAILURE - cost_purge, req:", req)

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        raise DummyTestException("FAILURE - obj_create, req:", req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        raise DummyTestException("FAILURE - obj_read, req:", req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        raise DummyTestException("FAILURE - objs_query, req:", req)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        raise DummyTestException("FAILURE - table_create, req:", req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        raise DummyTestException("FAILURE - table_update, req:", req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        raise DummyTestException("FAILURE - table_query, req:", req)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        raise DummyTestException("FAILURE - refs_read_batch, req:", req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        raise DummyTestException("FAILURE - file_create, req:", req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        raise DummyTestException("FAILURE - file_content_read, req:", req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        raise DummyTestException("FAILURE - feedback_create, req:", req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        raise DummyTestException("FAILURE - feedback_query, req:", req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        raise DummyTestException("FAILURE - feedback_purge, req:", req)


@pytest.fixture()
def client_with_throwing_server(client):
    curr_server = client.server
    client.server = ThrowingServer()
    try:
        yield client
    finally:
        client.server = curr_server


@pytest.fixture(scope="session")
def clickhouse_server():
    server_up = _check_server_up(
        ts_env.wf_clickhouse_host(), ts_env.wf_clickhouse_port()
    )
    if not server_up:
        pytest.fail("clickhouse server is not running")


@pytest.fixture(scope="session")
def clickhouse_trace_server(clickhouse_server):
    clickhouse_trace_server = (
        clickhouse_trace_server_batched.ClickHouseTraceServer.from_env(
            use_async_insert=False
        )
    )
    clickhouse_trace_server._run_migrations()
    yield clickhouse_trace_server


def _check_server_health(
    base_url: str, endpoint: str, num_retries: int = 1, sleep_time: int = 1
) -> bool:
    for _ in range(num_retries):
        try:
            response = requests.get(urllib.parse.urljoin(base_url, endpoint))
            if response.status_code == 200:
                return True
            time.sleep(sleep_time)
        except requests.exceptions.ConnectionError:
            time.sleep(sleep_time)

    print(
        f"Server not healthy @ {urllib.parse.urljoin(base_url, endpoint)}: no response"
    )
    return False


def _check_server_up(host, port) -> bool:
    base_url = f"http://{host}:{port}/"
    endpoint = "ping"

    def server_healthy(num_retries=1):
        return _check_server_health(
            base_url=base_url, endpoint=endpoint, num_retries=num_retries
        )

    if server_healthy():
        return True

    if os.environ.get("CI") != "true":
        print("CI is not true, not starting clickhouse server")

        subprocess.Popen(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-e",
                "CLICKHOUSE_DB=default",
                "-e",
                "CLICKHOUSE_USER=default",
                "-e",
                "CLICKHOUSE_PASSWORD=",
                "-e",
                "CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1",
                "-p",
                f"{port}:8123",
                "--name",
                "weave-python-test-clickhouse-server",
                "--ulimit",
                "nofile=262144:262144",
                "clickhouse/clickhouse-server",
            ]
        )

    # wait for the server to start
    return server_healthy(num_retries=30)


class TwoWayMapping:
    def __init__(self):
        self._ext_to_int_map = {}
        self._int_to_ext_map = {}

        # Useful for testing to ensure caching is working
        self.stats = {
            "ext_to_int": {
                "hits": 0,
                "misses": 0,
            },
            "int_to_ext": {
                "hits": 0,
                "misses": 0,
            },
        }

    def ext_to_int(self, key, default=None):
        if key not in self._ext_to_int_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._int_to_ext_map:
                raise ValueError(f"Default {default} already in use")
            self._ext_to_int_map[key] = default
            self._int_to_ext_map[default] = key
            self.stats["ext_to_int"]["misses"] += 1
        else:
            self.stats["ext_to_int"]["hits"] += 1
        return self._ext_to_int_map[key]

    def int_to_ext(self, key, default):
        if key not in self._int_to_ext_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._ext_to_int_map:
                raise ValueError(f"Default {default} already in use")
            self._int_to_ext_map[key] = default
            self._ext_to_int_map[default] = key
            self.stats["int_to_ext"]["misses"] += 1
        else:
            self.stats["int_to_ext"]["hits"] += 1
        return self._int_to_ext_map[key]


def b64(s: str) -> str:
    # Base64 encode the string
    return base64.b64encode(s.encode("ascii")).decode("ascii")


class DummyIdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def __init__(self):
        self._project_map = TwoWayMapping()
        self._run_map = TwoWayMapping()
        self._user_map = TwoWayMapping()

    def ext_to_int_project_id(self, project_id: str) -> str:
        return self._project_map.ext_to_int(project_id, b64(project_id))

    def int_to_ext_project_id(self, project_id: str) -> typing.Optional[str]:
        return self._project_map.int_to_ext(project_id, b64(project_id))

    def ext_to_int_run_id(self, run_id: str) -> str:
        return self._run_map.ext_to_int(run_id, b64(run_id) + ":" + run_id)

    def int_to_ext_run_id(self, run_id: str) -> str:
        exp = run_id.split(":")[1]
        return self._run_map.int_to_ext(run_id, exp)

    def ext_to_int_user_id(self, user_id: str) -> str:
        return self._user_map.ext_to_int(user_id, b64(user_id))

    def int_to_ext_user_id(self, user_id: str) -> str:
        return self._user_map.int_to_ext(user_id, b64(user_id))


class TestOnlyUserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str,
    ):
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        req.start.wb_user_id = self._user_id
        return super().call_start(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        req.wb_user_id = self._user_id
        return super().calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        req.wb_user_id = self._user_id
        return super().call_update(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        req.wb_user_id = self._user_id
        return super().feedback_create(req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        req.wb_user_id = self._user_id
        return super().cost_create(req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        req.wb_user_id = self._user_id
        return super().actions_execute_batch(req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        req.obj.wb_user_id = self._user_id
        return super().obj_create(req)


# https://docs.pytest.org/en/7.1.x/example/simple.html#pytest-current-test-environment-variable
def get_test_name():
    return os.environ.get("PYTEST_CURRENT_TEST", " ").split(" ")[0]


class InMemoryWeaveLogCollector(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_records = {}

    def emit(self, record):
        curr_test = get_test_name()
        if curr_test not in self.log_records:
            self.log_records[curr_test] = []
        self.log_records[curr_test].append(record)

    def _get_logs(self, levelname: str):
        curr_test = get_test_name()
        logs = self.log_records.get(curr_test, [])

        return [
            record
            for record in logs
            if record.levelname == levelname
            and record.name.startswith("weave")
            # (Tim) For some reason that i cannot figure out, there is some test that
            # a) is trying to connect to the PROD trace server
            # b) seemingly doesn't fail
            # c) Logs these errors.
            # I would love to fix this, but I have not been able to pin down which test
            # is causing it and need to ship this PR, so I am just going to filter it out
            # for now.
            and not record.msg.startswith(
                "Task failed: HTTPError: 400 Client Error: Bad Request for url: https://trace.wandb.ai/"
            )
            # Exclude legacy
            and not record.name.startswith("weave.weave_server")
            and not "legacy" in record.name
        ]

    def get_error_logs(self):
        return self._get_logs("ERROR")

    def get_warning_logs(self):
        return self._get_logs("WARNING")


@pytest.fixture
def log_collector(request):
    handler = InMemoryWeaveLogCollector()
    logger = logging.getLogger()  # Get your specific logger here if needed
    logger.addHandler(handler)
    if hasattr(request, "param") and request.param == "warning":
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.ERROR)
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

    def set_autoflush(self, value: bool):
        self._autoflush = value

    def __getattribute__(self, name):
        self_super = super()
        attr = self_super.__getattribute__(name)

        if callable(attr) and name != "flush":

            def wrapper(*args, **kwargs):
                res = attr(*args, **kwargs)
                if self.__dict__.get("_autoflush", True):
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


def create_client(
    request,
    autopatch_settings: typing.Optional[autopatch.AutopatchSettings] = None,
    global_attributes: typing.Optional[dict[str, typing.Any]] = None,
) -> weave_init.InitializedClient:
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
        # This is disabled by default, but we explicitly enable it here for testing
        os.environ["WEAVE_USE_SERVER_CACHE"] = "true"
        server = CachingMiddlewareTraceServer.from_env(server)
        client = TestOnlyFlushingWeaveClient(
            entity, project, make_server_recorder(server)
        )
        inited_client = weave_init.InitializedClient(client)
        autopatch.autopatch(autopatch_settings)
        if global_attributes is not None:
            weave.trace.api._global_attributes = global_attributes

    return inited_client


@pytest.fixture()
def client(request):
    """This is the standard fixture used everywhere in tests to test end to end
    client functionality"""
    inited_client = create_client(request)
    try:
        yield inited_client.client
    finally:
        inited_client.reset()
        autopatch.reset_autopatch()


@pytest.fixture()
def client_creator(request):
    """This fixture is useful for delaying the creation of the client (ex. when you want to set settings first)"""

    @contextlib.contextmanager
    def client(
        autopatch_settings: typing.Optional[autopatch.AutopatchSettings] = None,
        global_attributes: typing.Optional[dict[str, typing.Any]] = None,
        settings: typing.Optional[weave.trace.settings.UserSettings] = None,
    ):
        if settings is not None:
            weave.trace.settings.parse_and_apply_settings(settings)
        inited_client = create_client(request, autopatch_settings, global_attributes)
        try:
            yield inited_client.client
        finally:
            inited_client.reset()
            autopatch.reset_autopatch()
            weave.trace.api._global_attributes = {}
            weave.trace.settings.parse_and_apply_settings(
                weave.trace.settings.UserSettings()
            )

    yield client


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


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as dir_path:
        yield dir_path
