import contextlib
import json
import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Make the weave-trace sibling importable so tests can use weave_server
# (SqliteTraceServer, ExternalTraceServer, etc.) as a test-only dependency.
# ---------------------------------------------------------------------------
_WEAVE_TRACE_DIR = Path(__file__).resolve().parents[1] / ".." / ".." / "weave-trace"
if _WEAVE_TRACE_DIR.is_dir() and str(_WEAVE_TRACE_DIR) not in sys.path:
    sys.path.insert(0, str(_WEAVE_TRACE_DIR))

import weave
from tests.trace.server_utils import TEST_ENTITY
from tests.trace.util import DummyTestException
from weave.trace import weave_client, weave_init
from weave.trace.context import weave_client_context
from weave.trace.context.call_context import set_call_stack
from weave.trace.settings import UserSettings, parse_and_apply_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.caching_middleware_trace_server import (
    CachingMiddlewareTraceServer,
)
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer
from weave_server.external_to_internal_trace_server_adapter import IdConverter
from weave_server.sqlite_trace_server import SqliteTraceServer

# Force testing to never report wandb sentry events
os.environ["WANDB_ERROR_REPORTING"] = "false"


# ---------------------------------------------------------------------------
# pytest options and fixtures migrated from tests/trace_server/conftest.py
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--trace-server",
            action="store",
            default="sqlite",
            help="Specify the backend to use: sqlite or clickhouse",
        )
        parser.addoption(
            "--ch",
            "--clickhouse",
            action="store_true",
            help="Use clickhouse server (shorthand for --trace-server=clickhouse)",
        )
        parser.addoption(
            "--sq",
            "--sqlite",
            action="store_true",
            help="Use sqlite server (shorthand for --trace-server=sqlite)",
        )
        parser.addoption(
            "--clickhouse-process",
            action="store",
            default="false",
            help="Use a clickhouse process instead of a container",
        )
        parser.addoption(
            "--remote-http-trace-server",
            action="store",
            default="remote",
            help="Specify the remote HTTP trace server implementation: remote or stainless",
        )
    except ValueError:
        pass


def get_trace_server_flag(request):
    if request.config.getoption("--clickhouse"):
        return "clickhouse"
    if request.config.getoption("--sqlite"):
        return "sqlite"
    return request.config.getoption("--trace-server")


class _DummyIdConverter(IdConverter):
    """Minimal IdConverter for test use — maps ids via base64 encoding."""

    import base64 as _b64

    def __init__(self):
        self._project_map: dict[str, str] = {}
        self._run_map: dict[str, str] = {}
        self._user_map: dict[str, str] = {}

    @staticmethod
    def _b64e(s: str) -> str:
        import base64

        return base64.b64encode(s.encode("ascii")).decode("ascii")

    def ext_to_int_project_id(self, project_id: str) -> str:
        return self._project_map.setdefault(project_id, self._b64e(project_id))

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        for k, v in self._project_map.items():
            if v == project_id:
                return k
        val = self._b64e(project_id)
        self._project_map[val] = project_id
        return val

    def ext_to_int_run_id(self, run_id: str) -> str:
        return self._run_map.setdefault(run_id, self._b64e(run_id) + ":" + run_id)

    def int_to_ext_run_id(self, run_id: str) -> str:
        for k, v in self._run_map.items():
            if v == run_id:
                return k
        parts = run_id.split(":")
        return parts[1] if len(parts) > 1 else run_id

    def ext_to_int_user_id(self, user_id: str) -> str:
        return self._user_map.setdefault(user_id, self._b64e(user_id))

    def int_to_ext_user_id(self, user_id: str) -> str:
        for k, v in self._user_map.items():
            if v == user_id:
                return k
        return self._b64e(user_id)


from weave_server.external_to_internal_trace_server_adapter import ExternalTraceServer


class UserInjectingExternalTraceServer(ExternalTraceServer):
    """Test wrapper: injects a user id into external-facing requests."""

    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: IdConverter,
        user_id: str,
    ):
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def set_user_id(self, user_id: str) -> None:
        self._user_id = user_id

    def call_start(self, req):
        req.start.wb_user_id = self._user_id
        return super().call_start(req)

    def calls_delete(self, req):
        req.wb_user_id = self._user_id
        return super().calls_delete(req)

    def call_update(self, req):
        req.wb_user_id = self._user_id
        return super().call_update(req)

    def feedback_create(self, req):
        req.wb_user_id = self._user_id
        return super().feedback_create(req)

    def feedback_create_batch(self, req):
        for feedback_req in req.batch:
            feedback_req.wb_user_id = self._user_id
        return super().feedback_create_batch(req)

    def cost_create(self, req):
        req.wb_user_id = self._user_id
        return super().cost_create(req)

    def actions_execute_batch(self, req):
        req.wb_user_id = self._user_id
        return super().actions_execute_batch(req)

    def obj_create(self, req):
        req.obj.wb_user_id = self._user_id
        return super().obj_create(req)

    def evaluate_model(self, req):
        req.wb_user_id = self._user_id
        return super().evaluate_model(req)

    def evaluation_run_delete(self, req):
        req.wb_user_id = self._user_id
        return super().evaluation_run_delete(req)

    def evaluation_run_finish(self, req):
        req.wb_user_id = self._user_id
        return super().evaluation_run_finish(req)

    def prediction_delete(self, req):
        req.wb_user_id = self._user_id
        return super().prediction_delete(req)

    def score_delete(self, req):
        req.wb_user_id = self._user_id
        return super().score_delete(req)

    def obj_add_tags(self, req):
        req.wb_user_id = self._user_id
        return super().obj_add_tags(req)

    def obj_remove_tags(self, req):
        req.wb_user_id = self._user_id
        return super().obj_remove_tags(req)

    def obj_set_aliases(self, req):
        req.wb_user_id = self._user_id
        return super().obj_set_aliases(req)

    def obj_remove_aliases(self, req):
        req.wb_user_id = self._user_id
        return super().obj_remove_aliases(req)

    def projects_info(self, req):
        from weave.trace_server.service_interface import ProjectsInfoRes

        return [
            ProjectsInfoRes(
                external_project_id=pid,
                internal_project_id=self._idc.ext_to_int_project_id(pid),
            )
            for pid in req.project_ids
        ]


def _externalize_trace_server(
    trace_server: tsi.TraceServerInterface,
    user_id: str = "test_user",
    id_converter: IdConverter | None = None,
) -> UserInjectingExternalTraceServer:
    converter = id_converter or _DummyIdConverter()
    return UserInjectingExternalTraceServer(trace_server, converter, user_id)


class _EvaluateModelTestDispatcher:
    """Dispatcher that runs evaluate_model synchronously for testing."""

    def __init__(self, id_converter: IdConverter):
        self.id_converter = id_converter

    def dispatch(self, args) -> None:
        from weave_server.external_to_internal_trace_server_adapter import (
            universal_int_to_ext_ref_converter,
        )
        from weave_server.workers.evaluate_model_worker.evaluate_model_worker import (
            evaluate_model,
        )

        externalized_args = universal_int_to_ext_ref_converter(
            args, self.id_converter.int_to_ext_project_id
        )
        evaluate_model(externalized_args)


@pytest.fixture
def trace_server(request) -> tsi.TraceServerInterface:
    """Create a SQLite-backed trace server for testing."""
    from weave_server.secret_fetcher_context import secret_fetcher_context

    class _LocalSecretFetcher:
        def fetch(self, secret_name: str) -> dict:
            return {"secrets": {secret_name: os.getenv(secret_name)}}

    id_converter = _DummyIdConverter()
    db_path = "file::memory:?cache=shared"
    sqlite_server = SqliteTraceServer(
        db_path,
        evaluate_model_dispatcher=_EvaluateModelTestDispatcher(id_converter),
    )
    sqlite_server.setup_tables()

    server = _externalize_trace_server(
        sqlite_server, TEST_ENTITY, id_converter=id_converter
    )

    with secret_fetcher_context(_LocalSecretFetcher()):
        yield server

    try:
        sqlite_server.drop_tables()
    except Exception:
        pass
    try:
        sqlite_server.close()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def patch_kafka_producer():
    """Patch the Kafka producer. Without this, attempt to connect to the brokers will fail.
    This is ok but this introduces a `message.timeout.ms` (500ms) delay in each test.

    If a test needs to test the Kafka producer, they should override this patch explicitly.
    """
    with patch(
        "weave_server.kafka.KafkaProducer.from_env",
        return_value=MagicMock(),
    ):
        yield


@pytest.fixture(autouse=True)
def reset_serializer_load_refs():
    """Reset refs on serializer load functions between tests.

    When encode_custom_obj wraps a serializer's load function as an Op and saves it,
    a ref is attached to the Op. This ref persists in memory across tests since
    serializers are module-level globals. If a subsequent test runs with a fresh
    database (same project name), the _save_object_basic method sees the ref and
    returns early without saving - but the referenced object doesn't exist!

    This fixture clears those refs before each test to ensure proper test isolation.
    """
    from weave.trace.op_protocol import Op
    from weave.trace.ref_util import remove_ref
    from weave.trace.serialization.serializer import SERIALIZERS

    # Before test: clear refs from serializer load functions
    for serializer in SERIALIZERS:
        if isinstance(serializer.load, Op):
            remove_ref(serializer.load)

    yield

    # After test: clear refs again to prevent pollution to other tests
    for serializer in SERIALIZERS:
        if isinstance(serializer.load, Op):
            remove_ref(serializer.load)


@pytest.fixture(autouse=True)
def reset_project_residence_cache():
    """Reset the project residence cache between tests.

    The project residence cache stores the residence (merged/complete/both) of a project's data.
    This needs to be cleared between tests to prevent state leakage, especially when tests
    create projects with the same name but different data characteristics.
    """
    from weave_server.project_version.project_version import (
        _project_residence_cache,
    )

    _project_residence_cache.clear()
    yield
    _project_residence_cache.clear()


@pytest.fixture(autouse=True)
def reset_digest_settings():
    """Reset client-side digest settings after each test."""
    yield
    parse_and_apply_settings(UserSettings())


@pytest.fixture(autouse=True)
def disable_datadog():
    """Disables Datadog logging and tracing for tests.

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


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = 0


_TRACE_SERVER_METHOD_NAMES = frozenset(
    {
        name
        for interface in (tsi.TraceServerInterface, tsi.ObjectInterface)
        for name, value in vars(interface).items()
        if callable(value) and not name.startswith("_")
    }
)


class ThrowingServer(tsi.TraceServerInterface):
    def __getattribute__(self, name: str) -> Any:
        if name in _TRACE_SERVER_METHOD_NAMES:

            def _raise(*args: Any, **kwargs: Any) -> Any:
                if len(args) > 0:
                    req = args[0]
                elif "req" in kwargs:
                    req = kwargs["req"]
                else:
                    req = None
                raise DummyTestException(f"FAILURE - {name}, req:", req)

            return _raise

        return super().__getattribute__(name)


@pytest.fixture
def client_with_throwing_server(client):
    curr_server = client.server
    client.server = ThrowingServer()
    try:
        yield client
    finally:
        client.server = curr_server


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
            # Exclude legacy
            and not record.name.startswith("weave.weave_server")
            and "legacy" not in record.name
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
    """A WeaveClient that automatically flushes after every method call.

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

        def __init__(self, server: tsi.TraceServerInterface):
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
    trace_server,
    global_attributes: dict[str, Any] | None = None,
) -> weave_client.WeaveClient:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag == "prod":
        # Note: this is only for local dev testing and should be removed
        return weave_init.init_weave("dev_testing")
    elif trace_server_flag == "http":
        server = RemoteHTTPTraceServer(trace_server_flag)
    else:
        server = trace_server

    # Removing this as it lead to passing tests that were not passing in prod!
    # Keeping off for now until it is the default behavior.
    # os.environ["WEAVE_USE_SERVER_CACHE"] = "true"
    caching_server = CachingMiddlewareTraceServer.from_env(server)
    # ensure_project_exists=False because local backends (SQLite) don't
    # implement ServiceInterface — project creation is a remote-only concern.
    # In tests we assume the project already exists.
    client = TestOnlyFlushingWeaveClient(
        TEST_ENTITY,
        "test-project",
        make_server_recorder(caching_server),
        ensure_project_exists=False,
    )
    weave_client_context.set_weave_client_global(client)
    if global_attributes is not None:
        weave.trace.api._global_attributes = global_attributes

    return client


@pytest.fixture
def zero_stack():
    with set_call_stack([]):
        yield


@pytest.fixture
def client(zero_stack, request, trace_server, caching_client_isolation):
    """This is the standard fixture used everywhere in tests to test end to end
    client functionality.

    Note: caching_client_isolation is explicitly depended on to ensure the cache
    directory is set before the client is created. Without this, the cache might
    be shared across tests causing flaky test failures.
    """
    client = create_client(request, trace_server)
    try:
        yield client
    finally:
        weave_client_context.set_weave_client_global(None)
        try:
            client.server.close()
        except Exception:
            pass


@pytest.fixture
def client_creator(zero_stack, request, trace_server, caching_client_isolation):
    """This fixture is useful for delaying the creation of the client (ex. when you want to set settings first).

    Note: caching_client_isolation is explicitly depended on to ensure the cache
    directory is set before the client is created.
    """

    @contextlib.contextmanager
    def client(
        global_attributes: dict[str, Any] | None = None,
        settings: weave.trace.settings.UserSettings | None = None,
    ):
        if settings is not None:
            weave.trace.settings.parse_and_apply_settings(settings)
        client = create_client(request, trace_server, global_attributes)
        try:
            yield client
        finally:
            weave_client_context.set_weave_client_global(None)
            weave.trace.api._global_attributes = {}
            weave.trace.settings.parse_and_apply_settings(
                weave.trace.settings.UserSettings()
            )
            # Only close the caching layer, not the underlying trace_server.
            # The trace_server is shared across multiple clients within this
            # fixture and will be cleaned up by its own fixture teardown.
            try:
                client.server._cache.close()
            except Exception:
                pass

    return client


@pytest.fixture
def network_proxy_client(client):
    """This fixture is used to test the `RemoteHTTPTraceServer` class. There is
    almost no logic in this class, other than a little batching, so we typically
    skip it for simplicity. However, we can use this fixture to test such logic.
    It initializes a mini FastAPI app that proxies requests from the
    `RemoteHTTPTraceServer` to the underlying `client.server` object.

    We probably will want to flesh this out more in the future, but this is a
    starting point.
    """
    app = FastAPI()

    records = []

    @app.post("/calls/stream_query")
    def calls_stream_query(req: tsi.CallsQueryReq):
        records.append(
            (
                "calls_stream_query",
                req,
            )
        )

        def generate():
            calls = client.server.calls_query_stream(req)
            for call in calls:
                # Convert datetime objects to ISO format for JSON serialization
                call_dict = call.model_dump()
                for key, value in call_dict.items():
                    if isinstance(value, datetime):
                        call_dict[key] = value.isoformat()
                yield f"{json.dumps(call_dict)}\n"

        return StreamingResponse(generate(), media_type="application/x-ndjson")

    @app.post("/table/create")
    def table_create(req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        records.append(
            (
                "table_create",
                req,
            )
        )
        return client.server.table_create(req)

    @app.post("/table/create_from_digests")
    def table_create_from_digests(
        req: tsi.TableCreateFromDigestsReq,
    ) -> tsi.TableCreateFromDigestsRes:
        records.append(
            (
                "table_create_from_digests",
                req,
            )
        )
        return client.server.table_create_from_digests(req)

    @app.post("/table/update")
    def table_update(req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        records.append(
            (
                "table_update",
                req,
            )
        )
        return client.server.table_update(req)

    @app.post("/feedback/create")
    def feedback_create(req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        records.append(
            (
                "feedback_create",
                req,
            )
        )
        return client.server.feedback_create(req)

    @app.post("/feedback/batch/create")
    def feedback_create_batch(
        req: tsi.FeedbackCreateBatchReq,
    ) -> tsi.FeedbackCreateBatchRes:
        records.append(
            (
                "feedback_create_batch",
                req,
            )
        )
        return client.server.feedback_create_batch(req)

    @app.post("/obj/create")
    def obj_create(req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        records.append(
            (
                "obj_create",
                req,
            )
        )
        return client.server.obj_create(req)

    @app.post("/obj/read")
    def obj_read(req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        records.append(
            (
                "obj_read",
                req,
            )
        )
        return client.server.obj_read(req)

    with TestClient(app) as c:

        def post(url, data=None, json=None, **kwargs):
            kwargs.pop("stream", None)
            return c.post(url, data=data, json=json, **kwargs)

        orig_post = weave.utils.http_requests.post
        weave.utils.http_requests.post = post

        remote_client = RemoteHTTPTraceServer(
            trace_server_url="",
            should_batch=True,
        )
        yield (client, remote_client, records)

        weave.utils.http_requests.post = orig_post


@pytest.fixture(autouse=True)
def caching_client_isolation(monkeypatch, tmp_path):
    """Isolate cache directories for each test to prevent cross-test contamination."""
    # Replace characters that are invalid in Windows paths
    # Windows disallows: < > : " / \ | ? *
    test_name = get_test_name()
    for char in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]:
        test_name = test_name.replace(char, "_")
    test_name = test_name.replace("::", "_")
    test_specific_cache_dir = tmp_path / f"weave_cache_{test_name}"
    test_specific_cache_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("WEAVE_SERVER_CACHE_DIR", str(test_specific_cache_dir))
    return test_specific_cache_dir
    # tmp_path and monkeypatch automatically handle cleanup


@pytest.fixture
def make_evals(client):
    # First eval
    ev = weave.EvaluationLogger(model="abc", dataset="def")
    pred = ev.log_prediction(inputs={"x": 1}, output=2)
    pred.log_score("score", 3)
    pred.log_score("score2", 4)
    pred2 = ev.log_prediction(inputs={"x": 2}, output=3)
    pred2.log_score("score", 33)
    pred2.log_score("score2", 44)
    ev.log_summary(summary={"y": 5})

    # Make a second eval.  Later we will check to see that we don't get this eval's data when querying
    ev2 = weave.EvaluationLogger(model="ghi", dataset="jkl")
    pred3 = ev2.log_prediction(inputs={"alpha": 12}, output=34)
    pred3.log_score("second_score", 56)
    pred3.log_score("second_score2", 78)

    pred4 = ev2.log_prediction(inputs={"alpha": 34}, output=45)
    pred4.log_score("second_score", 5656)
    pred4.log_score("second_score2", 7878)
    ev2.log_summary(summary={"z": 90})

    return ev._pseudo_evaluation.ref, ev2._pseudo_evaluation.ref


@pytest.fixture
def mock_wandb_api():
    """Fixture that provides a mocked wandb Api instance."""
    with patch("weave.compat.wandb.Api") as mock_api_class:
        mock_api_instance = MagicMock()
        mock_api_class.return_value = mock_api_instance
        yield mock_api_instance
