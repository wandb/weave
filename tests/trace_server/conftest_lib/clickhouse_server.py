import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Generator

import pytest

from tests.trace_server.conftest_lib.container_management import check_server_up
from weave.trace_server import environment as ts_env


def ensure_clickhouse_db_container_running(host: str, port: int) -> Callable[[], None]:
    """ClickHouse server fixture that automatically starts a server if one isn't already running.

    This fixture checks if a ClickHouse server is already running on the configured host/port.
    If not, it automatically starts a Docker-based ClickHouse server for testing.

    The fixture handles cleanup by stopping the Docker container when the test session ends.
    """
    server_up = check_server_up(host, port, 1)
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


def ensure_clickhouse_db_keeper_container_running(
    host: str, port: int
) -> Callable[[], None]:
    """Start a 2-replica ClickHouse cluster with embedded Keeper for replicated-mode tests.

    Starts two containers on a shared Docker network:
    - ch-node1: Keeper + ClickHouse (tests connect here via host:port)
    - ch-node2: ClickHouse only (connects to node 1's Keeper)

    Two replicas are needed so ON CLUSTER mutations against non-existent tables
    actually fail (single-node setups silently succeed).
    """
    server_up = check_server_up(host, port, 1)
    network_name = "weave-test-ch-replicated"
    node1_name = "ch-node1"
    node2_name = "ch-node2"
    started_containers: list[str] = []

    if not server_up:
        config_dir = os.path.dirname(__file__)
        node1_config = os.path.join(config_dir, "clickhouse_keeper_node1.xml")
        node2_config = os.path.join(config_dir, "clickhouse_keeper_node2.xml")

        # Clean up any existing containers/network
        for name in [node2_name, node1_name]:
            subprocess.run(["docker", "stop", name], capture_output=True, check=False)
            subprocess.run(["docker", "rm", name], capture_output=True, check=False)
        subprocess.run(
            ["docker", "network", "rm", network_name],
            capture_output=True,
            check=False,
        )

        # Create shared network
        subprocess.run(
            ["docker", "network", "create", network_name],
            capture_output=True,
            check=True,
        )

        ch_env = [
            "-e",
            "CLICKHOUSE_DB=default",
            "-e",
            "CLICKHOUSE_USER=default",
            "-e",
            "CLICKHOUSE_PASSWORD=",
            "-e",
            "CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1",
        ]
        ch_image = "clickhouse/clickhouse-server:25.11.2.24"

        # Start node 1 (Keeper + CH, exposed to host)
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--network",
                network_name,
                "--name",
                node1_name,
                *ch_env,
                "-p",
                f"{port}:8123",
                "-v",
                f"{node1_config}:/etc/clickhouse-server/config.d/keeper.xml",
                "--ulimit",
                "nofile=262144:262144",
                ch_image,
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(f"Failed to start CH node 1: {result.stderr.decode()}")
        started_containers.append(node1_name)

        # Wait for node 1 (Keeper must be ready before node 2)
        if not check_server_up(host, port):
            _cleanup_containers(started_containers, network_name)
            pytest.fail(f"CH node 1 failed to become healthy on {host}:{port}")

        # Start node 2 (CH only, not exposed to host)
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--network",
                network_name,
                "--name",
                node2_name,
                *ch_env,
                "-v",
                f"{node2_config}:/etc/clickhouse-server/config.d/keeper.xml",
                "--ulimit",
                "nofile=262144:262144",
                ch_image,
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            _cleanup_containers(started_containers, network_name)
            pytest.fail(f"Failed to start CH node 2: {result.stderr.decode()}")
        started_containers.append(node2_name)

        # Wait for node 2 via docker exec
        for _ in range(30):
            check = subprocess.run(
                [
                    "docker",
                    "exec",
                    node2_name,
                    "wget",
                    "-q",
                    "-O-",
                    "http://localhost:8123/ping",
                ],
                capture_output=True,
                check=False,
            )
            if check.returncode == 0:
                break
            time.sleep(1)
        else:
            _cleanup_containers(started_containers, network_name)
            pytest.fail("CH node 2 failed to become healthy")

    def cleanup():
        _cleanup_containers(started_containers, network_name)

    return cleanup


def _cleanup_containers(containers: list[str], network: str) -> None:
    for name in reversed(containers):
        subprocess.run(["docker", "stop", name], capture_output=True, check=False)
    subprocess.run(
        ["docker", "network", "rm", network], capture_output=True, check=False
    )


def ensure_clickhouse_db_process_running(host: str, port: int) -> Callable[[], None]:
    """ClickHouse server fixture that automatically starts a server process if one isn't already running.

    This fixture checks if a ClickHouse server is already running on the configured host/port.
    If not, it automatically starts a ClickHouse server process for testing.

    The fixture handles cleanup by stopping the process when the test session ends.
    """
    server_up = check_server_up(host, port, 1)
    started_process = None
    temp_dir = None

    if not server_up:
        # Check if clickhouse-server is available
        clickhouse_binary = shutil.which("clickhouse-server")
        if not clickhouse_binary:
            pytest.fail(
                "ClickHouse server binary not found. Please install ClickHouse or use Docker version."
            )

        # Create temporary directory for ClickHouse data and config
        temp_dir = tempfile.mkdtemp(prefix="weave-clickhouse-test-")

        # Start the ClickHouse server process
        try:
            process = subprocess.Popen(
                [
                    clickhouse_binary,
                    # "--config-file", config_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=temp_dir,
                # Create new process group on Unix.
                preexec_fn=(os.setsid if os.name != "nt" else None),  # noqa: PLW1509
            )
            started_process = process

            # Give the server a moment to start
            time.sleep(2)

            # Wait for the server to be healthy
            server_up = check_server_up(host, port)
            if not server_up:
                # Clean up the process if server didn't start properly
                if process.poll() is None:  # Process is still running
                    if os.name != "nt":
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()
                    process.wait()
                pytest.fail(
                    f"ClickHouse server process failed to start and become healthy on {host}:{port}"
                )

        except Exception as e:
            pytest.fail(f"Failed to start ClickHouse server process: {e!s}")

    def cleanup():
        if (
            started_process and started_process.poll() is None
        ):  # Process is still running
            try:
                if os.name != "nt":
                    # On Unix, terminate the entire process group
                    os.killpg(os.getpgid(started_process.pid), signal.SIGTERM)
                else:
                    # On Windows, just terminate the process
                    started_process.terminate()
                started_process.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                # If graceful termination fails, force kill
                try:
                    if os.name != "nt":
                        os.killpg(os.getpgid(started_process.pid), signal.SIGKILL)
                    else:
                        started_process.kill()
                except ProcessLookupError:
                    pass  # Process already dead

        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # Best effort cleanup

    return cleanup


@pytest.fixture(scope="session")
def ensure_clickhouse_db(
    request,
) -> Callable[[], Generator[tuple[str, int], None, None]]:
    def ensure_clickhouse_db_inner() -> Generator[tuple[str, int], None, None]:
        host, port = ts_env.wf_clickhouse_host(), ts_env.wf_clickhouse_port()
        if os.environ.get("CI"):
            yield host, port
            return
        use_replicated = request.config.getoption(
            "--clickhouse-replicated", default=False
        )
        if use_replicated:
            cleanup = ensure_clickhouse_db_keeper_container_running(
                host=host,
                port=port,
            )
        elif request.config.getoption("--clickhouse-process") == "true":
            cleanup = ensure_clickhouse_db_process_running(
                host=host,
                port=port,
            )
        else:
            cleanup = ensure_clickhouse_db_container_running(
                host=host,
                port=port,
            )
        yield host, port
        cleanup()

    return ensure_clickhouse_db_inner
