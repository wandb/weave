from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from tests.trace.server_utils import TEST_ENTITY, find_server_layer
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
    UserInjectingExternalTraceServer,
    externalize_trace_server,
)
from tests.trace_server.workers.evaluate_model_test_worker import (
    EvaluateModelTestDispatcher,
)
from weave.trace_server import clickhouse_trace_server_batched
from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server import (
    clickhouse_trace_server_settings as ch_settings,
)
from weave.trace_server import environment as wf_env
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.in_memory_trace_server import InMemoryTraceServer
from weave.trace_server.parallel_bucket_uploads import BucketUploadBatch
from weave.trace_server.project_version import project_version
from weave.trace_server.secret_fetcher_context import secret_fetcher_context

pytest_plugins = ["tests.trace_server.conftest_lib.clickhouse_server"]


@dataclass(frozen=True)
class ClickHouseSessionState:
    """Holds the session-scoped ClickHouse server and its database names."""

    server: clickhouse_trace_server_batched.ClickHouseTraceServer
    management_db: str
    unique_db: str
    # Tables that should be truncated between tests (excludes views)
    truncatable_tables: list[str]


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--trace-server",
            action="store",
            default="clickhouse",
            help="Specify the backend to use: clickhouse or fake (in-memory)",
        )
        parser.addoption(
            "--ch",
            "--clickhouse",
            action="store_true",
            help="Use clickhouse server (shorthand for --trace-server=clickhouse)",
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
            default="stainless",
            help=(
                "Legacy flag retained for CI compatibility. The remote trace "
                "server client is always the generated SDK "
                "(StainlessRemoteHTTPTraceServer)."
            ),
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    # Add the trace_server marker to:
    # 1. All tests in the trace_server directory (regardless of fixture usage)
    # 2. All tests that use the trace_server fixture (for tests outside this directory)
    # Note: Filtering based on remote-http-trace-server flag is handled in tests/trace_server_bindings/conftest.py
    for item in items:
        # Check if the test is in the trace_server directory by checking parent directories
        if "trace_server" in item.path.parts:
            item.add_marker(pytest.mark.trace_server)
        # Also mark tests that use the trace_server fixture (for tests outside this dir)
        elif "trace_server" in item.fixturenames:
            item.add_marker(pytest.mark.trace_server)


def get_trace_server_flag(request):
    if request.config.getoption("--clickhouse"):
        return "clickhouse"
    return request.config.getoption("--trace-server")


def get_remote_http_trace_server_flag(request):
    """Get the remote HTTP trace server flag.

    Legacy: the client is always StainlessRemoteHTTPTraceServer. Retained for
    CI compatibility (the ``--remote-http-trace-server`` option still parses).
    """
    return request.config.getoption("--remote-http-trace-server")


@pytest.fixture(autouse=True)
def reset_project_version_cache():
    project_version.reset_project_residence_cache()
    yield
    project_version.reset_project_residence_cache()


def _get_worker_db_suffix(request, default: str = "_test") -> str:
    """Get database suffix for pytest-xdist worker isolation.

    Returns worker-specific suffix like '_w0' for xdist, or `default` for
    single-process runs.
    """
    worker_input = getattr(request.config, "workerinput", None)
    if worker_input is None:
        return default
    worker_id = worker_input.get("workerid", "master")
    return f"_w{worker_id.replace('gw', '')}"


# Tables with migration-seeded data that should NOT be truncated between tests.
SEED_DATA_TABLES = frozenset({"llm_token_prices"})


def _on_cluster_clause() -> str:
    """`ON CLUSTER <name>` suffix when replicated, else empty."""
    if not wf_env.wf_clickhouse_replicated():
        return ""
    cluster = wf_env.wf_clickhouse_replicated_cluster()
    return f" ON CLUSTER {cluster}" if cluster else ""


def _discover_truncatable_tables(ch_client, database: str) -> list[str]:
    """Non-view, non-Distributed tables eligible for per-test truncate."""
    result = ch_client.query(
        "SELECT name FROM system.tables "
        f"WHERE database = '{database}' "
        "AND engine NOT IN ('View', 'MaterializedView', 'Distributed') "
        "ORDER BY name"
    )
    seed_tables = SEED_DATA_TABLES | {
        t + ch_settings.LOCAL_TABLE_SUFFIX for t in SEED_DATA_TABLES
    }
    return [row[0] for row in result.result_rows if row[0] not in seed_tables]


def _truncate_all_tables(ch_client, database: str, tables: list[str]) -> None:
    """Truncate all data tables in the database for test isolation."""
    on_cluster = _on_cluster_clause()
    for table in tables:
        ch_client.command(f"TRUNCATE TABLE {database}.{table}{on_cluster} SYNC")


def _reset_server_state(server: ClickHouseTraceServer) -> None:
    """Reset cached/accumulated state on a ClickHouseTraceServer instance.

    IMPORTANT: If you add new cached/mutable state to ClickHouseTraceServer,
    you must reset it here too — otherwise it will leak between tests and cause
    hard-to-debug order-dependent failures.
    """
    # Clear op ref cache
    server._op_ref_cache.clear()
    # Clear placeholder file projects set
    server._placeholder_file_projects.clear()
    # Reset table routing resolver to None so it's lazily re-created
    # (tests may have set _mode to AUTO or accessed the resolver)
    server._table_routing_resolver = None
    # Reset file storage client so tests that mock env vars get a fresh client
    server._file_storage_client = None
    server._file_storage_client_initialized = False
    # Reset batch queues (thread-local, for current thread)
    server._call_batch = []
    server._file_batch = []
    server._calls_complete_batch = []
    server._bucket_uploads = BucketUploadBatch()
    server._flush_immediately = False


@pytest.fixture(scope="session")
def _ch_session_server(
    ensure_clickhouse_db,
    request,
) -> ClickHouseSessionState | None:
    """Session-scoped ClickHouse server: created once, migrated once.

    Returns None if ClickHouse is not the selected backend (e.g. the
    `prod`/`http` escape hatches), so dependents can skip instead of
    spinning up a server that won't be used.
    """
    backend = get_trace_server_flag(request)
    if backend != "clickhouse":
        yield None
        return

    host, port = next(ensure_clickhouse_db())
    db_suffix = _get_worker_db_suffix(request)

    original_db = os.environ.get("WF_CLICKHOUSE_DATABASE")
    base_db = original_db or "default"
    unique_db = f"{base_db}{db_suffix}"
    management_db = f"db_management{db_suffix}"

    os.environ["WF_CLICKHOUSE_DATABASE"] = unique_db

    id_converter = DummyIdConverter()
    ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
        host=host,
        port=port,
        database=unique_db,
        evaluate_model_dispatcher=EvaluateModelTestDispatcher(
            id_converter=id_converter
        ),
    )

    # Drop and recreate from scratch once
    on_cluster = _on_cluster_clause()
    ch_server.ch_client.command(
        f"DROP DATABASE IF EXISTS {management_db}{on_cluster} SYNC"
    )
    ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {unique_db}{on_cluster} SYNC")
    ch_server._database_ensured = False

    def patched_run_migrations():
        migrator = wf_migrator.get_clickhouse_trace_server_migrator(
            ch_server._mint_client(),
            management_db=management_db,
            replicated=wf_env.wf_clickhouse_replicated(),
            replicated_path=wf_env.wf_clickhouse_replicated_path(),
            replicated_cluster=wf_env.wf_clickhouse_replicated_cluster(),
            use_distributed=wf_env.wf_clickhouse_use_distributed_tables(),
        )
        migrator.apply_migrations(ch_server._database)

    ch_server._run_migrations = patched_run_migrations  # type: ignore[assignment]
    ch_server._run_migrations()

    truncatable = _discover_truncatable_tables(ch_server.ch_client, unique_db)

    yield ClickHouseSessionState(
        server=ch_server,
        management_db=management_db,
        unique_db=unique_db,
        truncatable_tables=truncatable,
    )

    # Restore env
    if original_db is None:
        os.environ.pop("WF_CLICKHOUSE_DATABASE", None)
    else:
        os.environ["WF_CLICKHOUSE_DATABASE"] = original_db

    # Session cleanup: drop databases
    teardown_on_cluster = _on_cluster_clause()
    try:
        ch_server.ch_client.command(
            f"DROP DATABASE IF EXISTS {management_db}{teardown_on_cluster} SYNC"
        )
    except Exception:
        pass
    try:
        ch_server.ch_client.command(
            f"DROP DATABASE IF EXISTS {unique_db}{teardown_on_cluster} SYNC"
        )
    except Exception:
        pass
    try:
        ch_server.ch_client.close()
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _disable_query_condition_cache() -> None:
    # TODO: remove once https://github.com/ClickHouse/ClickHouse/issues/104781 ships.
    # The bloom-filter CTE on calls_merged matches the trigger shape (PREWHERE
    # pk-prefix + WHERE non-pk equality on a skip-indexed column) that poisons
    # CH's query condition cache and returns wrong counts on subsequent reads.
    # Force-off the setting for the test session by mutating the trace server's
    # default settings dicts in place. Every query path goes through these.
    ch_settings.CLICKHOUSE_BASE_QUERY_SETTINGS["use_query_condition_cache"] = 0
    ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS["use_query_condition_cache"] = 0


@pytest.fixture
def get_ch_trace_server(
    _ch_session_server: ClickHouseSessionState | None,
    request,
) -> Callable[[], UserInjectingExternalTraceServer]:
    """Function-scoped CH fixture factory. Reuses session-scoped DB, truncates between tests."""

    def ch_trace_server_inner() -> UserInjectingExternalTraceServer:
        if _ch_session_server is None:
            pytest.skip("ClickHouse session not available")

        state = _ch_session_server
        server = state.server

        # Truncate all tables for a clean slate
        _truncate_all_tables(
            server.ch_client, state.unique_db, state.truncatable_tables
        )

        # Reset any accumulated in-memory state
        _reset_server_state(server)

        # Force synchronous writes so tests see data immediately
        server._flush_immediately = True

        # Wrap in the external adapter (fresh id_converter per test)
        id_converter = DummyIdConverter()
        server._evaluate_model_dispatcher = EvaluateModelTestDispatcher(
            id_converter=id_converter
        )
        return externalize_trace_server(server, TEST_ENTITY, id_converter=id_converter)

    return ch_trace_server_inner


@pytest.fixture
def get_fake_trace_server(
    request,
) -> Callable[[], UserInjectingExternalTraceServer]:
    def fake_trace_server_inner() -> UserInjectingExternalTraceServer:
        id_converter = DummyIdConverter()
        fake_server = InMemoryTraceServer(
            evaluate_model_dispatcher=EvaluateModelTestDispatcher(
                id_converter=id_converter
            ),
        )
        return externalize_trace_server(
            fake_server, TEST_ENTITY, id_converter=id_converter
        )

    return fake_trace_server_inner


class LocalSecretFetcher:
    def fetch(self, secret_name: str) -> dict:
        return {"secrets": {secret_name: os.getenv(secret_name)}}


@pytest.fixture
def local_secret_fetcher():
    with secret_fetcher_context(LocalSecretFetcher()):
        yield


@pytest.fixture
def trace_server(
    request, local_secret_fetcher, get_ch_trace_server, get_fake_trace_server
) -> UserInjectingExternalTraceServer:
    backend = get_trace_server_flag(request)
    if backend == "clickhouse":
        return get_ch_trace_server()
    elif backend == "fake":
        return get_fake_trace_server()
    raise ValueError(f"Invalid trace server: {backend}")


@pytest.fixture
def ch_server(request, trace_server):
    """Extract the ClickHouseTraceServer from the test fixture, or skip."""
    if get_trace_server_flag(request) != "clickhouse":
        pytest.skip("ClickHouse-only test")
    server = trace_server._internal_trace_server
    assert isinstance(server, ClickHouseTraceServer)
    return server


@pytest.fixture
def internal_server(client):
    """Return the underlying fake or ClickHouse server from the middleware chain."""
    for layer_type in (InMemoryTraceServer, ClickHouseTraceServer):
        try:
            return find_server_layer(client.server, layer_type)
        except TypeError:
            continue
    raise TypeError(
        "No known internal trace server (InMemoryTraceServer or "
        "ClickHouseTraceServer) found in the client's middleware chain"
    )
