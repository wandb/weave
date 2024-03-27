import os
import pytest


import subprocess
import time
import requests
import urllib

import pytest

from weave.trace_server import environment as wf_env

from ..weave_init import InitializedClient
import uuid
from weave import weave_client
from ..trace_server import (
    clickhouse_trace_server_batched,
)


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
def trace_client(clickhouse_trace_server, user_by_api_key_in_env):
    # Generate a random project name to avoid conflicts between tests
    # using the same shared backend server
    random_project_name = str(uuid.uuid4())
    graph_client = weave_client.WeaveClient(
        user_by_api_key_in_env.username, random_project_name, clickhouse_trace_server
    )
    inited_client = InitializedClient(graph_client)

    try:
        yield graph_client
    finally:
        inited_client.reset()


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
