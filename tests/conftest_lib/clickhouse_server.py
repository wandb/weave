

import subprocess
import typing
import pytest

from tests.conftest_lib.container_management import check_server_up
from weave.trace_server import environment as ts_env

def ensure_clickhouse_db_instance_running(host: str, port: int) -> typing.Callable[[], None]:
    """
    ClickHouse server fixture that automatically starts a server if one isn't already running.

    This fixture checks if a ClickHouse server is already running on the configured host/port.
    If not, it automatically starts a Docker-based ClickHouse server for testing.

    The fixture handles cleanup by stopping the Docker container when the test session ends.
    """

    server_up = check_server_up(host, port, 0)
    started_container = None

    if not server_up:
        # Try to start a ClickHouse server using Docker
        container_name = "weave-python-test-clickhouse-server"

        # First, ensure any existing container is stopped and removed
        subprocess.run(
            ["docker", "stop", container_name], capture_output=True, check=False
        )
        subprocess.run(
            ["docker", "rm", container_name], capture_output=True, check=False
        )

        # Start the ClickHouse container
        process = subprocess.Popen(
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
                container_name,
                "--ulimit",
                "nofile=262144:262144",
                "clickhouse/clickhouse-server",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the process to complete and get the container ID
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            pytest.fail(f"Failed to start ClickHouse container: {stderr.decode()}")

        started_container = container_name

        # Wait for the server to be healthy
        server_up = check_server_up(host, port)
        if not server_up:
            # Clean up the container if server didn't start properly
            subprocess.run(
                ["docker", "stop", container_name], capture_output=True, check=False
            )
            pytest.fail(
                f"ClickHouse server failed to start and become healthy on {host}:{port}"
            )

    def cleanup():
        if started_container:
            subprocess.run(
                ["docker", "stop", started_container], capture_output=True, check=False
            )

    return cleanup


@pytest.fixture(scope="session", autouse=True)
def ensure_clickhouse_db():
    host, port = ts_env.wf_clickhouse_host(), ts_env.wf_clickhouse_port()
    cleanup = ensure_clickhouse_db_instance_running(
        host=host,
        port=port,
    )
    yield host, port
    cleanup()