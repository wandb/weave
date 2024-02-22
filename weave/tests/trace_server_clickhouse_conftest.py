import os
import pytest


import subprocess
import time
import typing
import requests
import urllib

import pytest

from ..weave_init import InitializedClient
from ..trace_server import (
    graph_client_trace,
    clickhouse_trace_server_batched,
)


@pytest.fixture(scope="session")
def clickhouse_server():
    # host = os.environ.get("TEST_CH_SERVER_HOST", "localhost")
    (host, port, server_up) = _check_server_up()
    if not server_up:
        pytest.fail("clickhouse server is not running")
    yield (host, port)


@pytest.fixture(scope="session")
def clickhouse_trace_server(clickhouse_server):
    (host, port) = clickhouse_server
    clickhouse_trace_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
        host, port, False
    )
    clickhouse_trace_server._run_migrations()
    yield clickhouse_trace_server


@pytest.fixture()
def trace_client(clickhouse_trace_server):
    graph_client = graph_client_trace.GraphClientTrace(
        "test_entity", "test_project", clickhouse_trace_server
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


def _check_server_up(host="localhost", port=18123) -> typing.Tuple[str, int, bool]:
    base_port = 18123
    base_url = f"http://{host}:{port}/"
    endpoint = "/"

    def server_healthy(num_retries=1):
        return _check_server_health(
            base_url=base_url, endpoint=endpoint, num_retries=num_retries
        )

    if os.environ.get("CI") != "true":
        if server_healthy():
            return (host, port, True)

        subprocess.Popen(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-p",
                f"{base_port}:8123",
                "--name",
                "weave-python-test-clickhouse-server",
                "--ulimit",
                "nofile=262144:262144",
                "clickhouse/clickhouse-server",
            ]
        )

    # wait for the server to start
    if server_healthy(num_retries=30):
        return (host, port, True)
    else:
        return (host, port, False)
