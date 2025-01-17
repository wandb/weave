"""
This file is responsible for setting up the fixtures that allow for weave initialization.

It is the test-friendly version of weave_init.py.
"""

import contextlib
import os
import typing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import weave
from weave.trace import autopatch, weave_client, weave_init
from weave.trace_server import (
    clickhouse_trace_server_batched,
    sqlite_trace_server,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings import remote_http_trace_server

from .conftest_lib.http_trace_server import (
    build_minimal_blind_authenticating_trace_server,
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


def initialize_sqlite_trace_server():
    sqlite_server = sqlite_trace_server.SqliteTraceServer(
        "file::memory:?cache=shared"
    )
    sqlite_server.drop_tables()
    sqlite_server.setup_tables()
    return sqlite_server

def initialize_clickhouse_trace_server():
    ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer.from_env()
    ch_server.ch_client.command("DROP DATABASE IF EXISTS db_management")
    ch_server.ch_client.command("DROP DATABASE IF EXISTS default")
    ch_server._run_migrations()
    return ch_server

def expose_trace_server_api(trace_server: tsi.TraceServerInterface, entity: str):
    return build_minimal_blind_authenticating_trace_server(trace_server, entity)





@contextlib.contextmanager
def with_env_var(key: str, value: str):
    original_value = os.getenv(key)
    os.environ[key] = value
    try:
        yield
    finally:
        os.environ[key] = original_value

def create_client(
    request, autopatch_settings: typing.Optional[autopatch.AutopatchSettings] = None
) -> weave_init.InitializedClient:
    inited_client = None
    weave_server_flag = request.config.getoption("--weave-server")
    server: tsi.TraceServerInterface
    entity = "shawn"
    project = "test-project"


    if weave_server_flag == "sqlite" or weave_server_flag == "clickhouse":
        target_trace_url = "http://localhost:8000"
    elif weave_server_flag == "prod":
        target_trace_url = "https://trace.wandb.ai"
    elif weave_server_flag == "http":
        target_trace_url = weave_server_flag
    else:
        raise ValueError(f"Invalid weave server flag: {weave_server_flag}")

    with with_env_var("WF_TRACE_SERVER_URL", target_trace_url):
        if weave_server_flag == "sqlite":
            sqlite_server = sqlite_trace_server.SqliteTraceServer(
                "file::memory:?cache=shared"
            )
            sqlite_server.drop_tables()
            sqlite_server.setup_tables()
            server = build_minimal_blind_authenticating_trace_server(sqlite_server, entity)
        elif weave_server_flag == "clickhouse":
            ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer.from_env()
            ch_server.ch_client.command("DROP DATABASE IF EXISTS db_management")
            ch_server.ch_client.command("DROP DATABASE IF EXISTS default")
            ch_server._run_migrations()
            server = build_minimal_blind_authenticating_trace_server(ch_server, entity)
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
            autopatch.autopatch(autopatch_settings)

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
    def client(autopatch_settings: typing.Optional[autopatch.AutopatchSettings] = None):
        inited_client = create_client(request, autopatch_settings)
        try:
            yield inited_client.client
        finally:
            inited_client.reset()
            autopatch.reset_autopatch()

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
