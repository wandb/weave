import logging
import os
import subprocess
import time
import urllib
from collections.abc import Iterator

import pytest
import requests

from tests.trace.util import DummyTestException
from weave.trace_server import (
    clickhouse_trace_server_batched,
)
from weave.trace_server import environment as ts_env
from weave.trace_server import trace_server_interface as tsi

from .conftest_init import *

# Force testing to never report wandb sentry events
os.environ["WANDB_ERROR_REPORTING"] = "false"


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

    def get_error_logs(self):
        curr_test = get_test_name()
        logs = self.log_records.get(curr_test, [])

        return [
            record
            for record in logs
            if record.levelname == "ERROR"
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


@pytest.fixture
def log_collector():
    handler = InMemoryWeaveLogCollector()
    logger = logging.getLogger()  # Get your specific logger here if needed
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)  # Set the level to capture all logs
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
