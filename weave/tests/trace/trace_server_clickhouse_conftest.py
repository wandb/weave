import base64
import os
import subprocess
import time
import typing
import urllib
import uuid

import pytest
import requests

from weave import weave_client
from weave.trace_server import (
    clickhouse_trace_server_batched,
    external_to_internal_trace_server_adapter,
)
from weave.trace_server import environment as wf_env
from weave.trace_server import trace_server_interface as tsi
from weave.weave_init import InitializedClient


@pytest.fixture(scope="session")
def clickhouse_server():
    server_up = _check_server_up(
        wf_env.wf_clickhouse_host(), wf_env.wf_clickhouse_port()
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


@pytest.fixture()
def trace_init_client(clickhouse_trace_server, user_by_api_key_in_env):
    # Generate a random project name to avoid conflicts between tests
    # using the same shared backend server
    random_project_name = str(uuid.uuid4())
    server = TestOnlyUserInjectingExternalTraceServer(
        clickhouse_trace_server, DummyIdConverter(), user_by_api_key_in_env.username
    )
    graph_client = weave_client.WeaveClient(
        user_by_api_key_in_env.username, random_project_name, server
    )

    inited_client = InitializedClient(graph_client)

    try:
        yield inited_client
    finally:
        inited_client.reset()


@pytest.fixture()
def trace_client(trace_init_client):
    return trace_init_client.client


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
