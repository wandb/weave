import os
import shutil
import signal
import subprocess
import tempfile
import time
import typing

import pytest

from tests.conftest_lib.container_management import check_server_up
from weave.trace_server import environment as ts_env


def ensure_clickhouse_db_container_running(
    host: str, port: int
) -> typing.Callable[[], None]:
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


def ensure_clickhouse_db_process_running(
    host: str, port: int
) -> typing.Callable[[], None]:
    """
    ClickHouse server fixture that automatically starts a server process if one isn't already running.

    This fixture checks if a ClickHouse server is already running on the configured host/port.
    If not, it automatically starts a ClickHouse server process for testing.

    The fixture handles cleanup by stopping the process when the test session ends.
    """
    server_up = check_server_up(host, port, 0)
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
        #         data_dir = os.path.join(temp_dir, "data")
        #         logs_dir = os.path.join(temp_dir, "logs")
        #         os.makedirs(data_dir, exist_ok=True)
        #         os.makedirs(logs_dir, exist_ok=True)

        #         # Create a minimal ClickHouse configuration
        #         config_content = f"""<?xml version="1.0"?>
        # <yandex>
        #     <logger>
        #         <level>warning</level>
        #         <log>{logs_dir}/clickhouse-server.log</log>
        #         <errorlog>{logs_dir}/clickhouse-server.err.log</errorlog>
        #         <size>1000M</size>
        #         <count>10</count>
        #     </logger>

        #     <http_port>{port}</http_port>
        #     <tcp_port>9000</tcp_port>

        #     <path>{data_dir}/</path>
        #     <tmp_path>{temp_dir}/tmp/</tmp_path>
        #     <user_files_path>{temp_dir}/user_files/</user_files_path>
        #     <format_schema_path>{temp_dir}/format_schemas/</format_schema_path>

        #     <users_config>users.xml</users_config>

        #     <default_profile>default</default_profile>
        #     <default_database>default</default_database>

        #     <timezone>UTC</timezone>

        #     <mlock_executable>false</mlock_executable>

        #     <remap_executable>false</remap_executable>

        #     <query_log>
        #         <database>system</database>
        #         <table>query_log</table>
        #     </query_log>

        #     <listen_host>{host}</listen_host>
        # </yandex>
        # """

        #         users_content = """<?xml version="1.0"?>
        # <yandex>
        #     <profiles>
        #         <default>
        #             <max_memory_usage>10000000000</max_memory_usage>
        #             <use_uncompressed_cache>0</use_uncompressed_cache>
        #             <load_balancing>random</load_balancing>
        #         </default>
        #     </profiles>

        #     <users>
        #         <default>
        #             <password></password>
        #             <networks incl="networks_config">
        #                 <ip>::/0</ip>
        #             </networks>
        #             <profile>default</profile>
        #             <quota>default</quota>
        #         </default>
        #     </users>

        #     <quotas>
        #         <default>
        #             <interval>
        #                 <duration>3600</duration>
        #                 <queries>0</queries>
        #                 <errors>0</errors>
        #                 <result_rows>0</result_rows>
        #                 <read_rows>0</read_rows>
        #                 <execution_time>0</execution_time>
        #             </interval>
        #         </default>
        #     </quotas>
        # </yandex>
        # """

        #         config_path = os.path.join(temp_dir, "config.xml")
        #         users_path = os.path.join(temp_dir, "users.xml")

        #         with open(config_path, "w") as f:
        #             f.write(config_content)

        #         with open(users_path, "w") as f:
        #             f.write(users_content)

        #         # Create additional required directories
        #         os.makedirs(os.path.join(temp_dir, "tmp"), exist_ok=True)
        #         os.makedirs(os.path.join(temp_dir, "user_files"), exist_ok=True)
        #         os.makedirs(os.path.join(temp_dir, "format_schemas"), exist_ok=True)

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
                preexec_fn=os.setsid
                if os.name != "nt"
                else None,  # Create new process group on Unix
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
            pytest.fail(f"Failed to start ClickHouse server process: {str(e)}")

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
def ensure_clickhouse_db(request):
    host, port = ts_env.wf_clickhouse_host(), ts_env.wf_clickhouse_port()
    if os.environ.get("CI"):
        yield host, port
        return
    if request.config.getoption("--clickhouse-process") == "true":
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
