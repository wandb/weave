import os
import subprocess

import clickhouse_connect
import pytest

from tests.trace_server.conftest_lib.container_management import check_server_up

_CONTAINER_NAME = "weave-python-test-clickhouse-keeper-server"
_KEEPER_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "trace_server",
    "conftest_lib",
    "clickhouse_keeper_config.xml",
)
_DEFAULT_PORT = 8130


@pytest.fixture(scope="session")
def ch_keeper_server(worker_id):
    """Start a single-node ClickHouse with embedded Keeper for replicated tests."""
    host = "localhost"
    port = int(os.environ.get("WF_CLICKHOUSE_KEEPER_PORT", _DEFAULT_PORT))

    if os.environ.get("CI"):
        yield host, port
        return

    # Under xdist every worker runs this session fixture, so exactly one worker
    # owns the container and the rest wait on it. The owner leaves it running on
    # teardown when distributed: workers exit independently, and stopping the
    # server under a sibling still running its tests would fail that worker.
    owns_container = worker_id in {"master", "gw0"}
    started_container = False

    if not check_server_up(host, port, 1):
        if not owns_container:
            if not check_server_up(host, port):
                pytest.fail(f"ClickHouse Keeper server never came up on {host}:{port}")
        else:
            _start_keeper_container(port)
            started_container = True
            if not check_server_up(host, port):
                subprocess.run(
                    ["docker", "stop", _CONTAINER_NAME],
                    capture_output=True,
                    check=False,
                )
                pytest.fail(
                    f"ClickHouse Keeper server failed to become healthy on {host}:{port}"
                )

    yield host, port

    if started_container and worker_id == "master":
        subprocess.run(
            ["docker", "stop", _CONTAINER_NAME], capture_output=True, check=False
        )


@pytest.fixture
def ch_client(ch_keeper_server):
    """Create a clickhouse_connect client and track databases for cleanup."""
    host, port = ch_keeper_server
    # Mirror production SyncClickHouseTransport.mint kwargs (cosmetic; migrator is single-threaded).
    client = clickhouse_connect.get_client(
        host=host, port=port, autogenerate_session_id=False
    )
    tracked_dbs: list[str] = []

    # Attach a tracking helper directly on the client instance
    client._tracked_dbs = tracked_dbs
    client.track_db = tracked_dbs.append

    yield client

    for db in reversed(tracked_dbs):
        try:
            client.command(f"DROP DATABASE IF EXISTS {db}")
        except Exception:
            pass
    client.close()


def _start_keeper_container(port: int) -> None:
    """Replace any stale container with a fresh Keeper-enabled ClickHouse."""
    subprocess.run(
        ["docker", "stop", _CONTAINER_NAME], capture_output=True, check=False
    )
    subprocess.run(["docker", "rm", _CONTAINER_NAME], capture_output=True, check=False)

    config_path = os.path.abspath(_KEEPER_CONFIG_PATH)
    result = subprocess.run(
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
            "-v",
            f"{config_path}:/etc/clickhouse-server/config.d/keeper.xml",
            "--name",
            _CONTAINER_NAME,
            "--ulimit",
            "nofile=262144:262144",
            "clickhouse/clickhouse-server",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to start ClickHouse Keeper container: {result.stderr.decode()}"
        )
