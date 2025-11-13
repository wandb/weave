import os
from typing import Callable
from unittest import mock

import pytest

from tests.trace_server.conftest_lib.clickhouse_server import *
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
    TestOnlyUserInjectingExternalTraceServer,
    externalize_trace_server,
)
from tests.trace_server.workers.evaluate_model_test_worker import (
    EvaluateModelTestDispatcher,
)
from weave.trace_server import (
    clickhouse_trace_server_batched,
    clickhouse_trace_server_migrator,
)
from weave.trace_server.secret_fetcher_context import secret_fetcher_context
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

TEST_ENTITY = "shawn"


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--trace-server",
            action="store",
            default="clickhouse",
            help="Specify the client object to use: sqlite or clickhouse",
        )
        parser.addoption(
            "--ch",
            "--clickhouse",
            action="store_true",
            help="Use clickhouse server (shorthand for --trace-server=clickhouse)",
        )
        parser.addoption(
            "--sq",
            "--sqlite",
            action="store_true",
            help="Use sqlite server (shorthand for --trace-server=sqlite)",
        )
        parser.addoption(
            "--clickhouse-process",
            action="store",
            default="false",
            help="Use a clickhouse process instead of a container",
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    # Add the trace_server marker to:
    # 1. All tests in the trace_server directory (regardless of fixture usage)
    # 2. All tests that use the trace_server fixture (for tests outside this directory)
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
    if request.config.getoption("--sqlite"):
        return "sqlite"
    weave_server_flag = request.config.getoption("--trace-server")
    return weave_server_flag


@pytest.fixture
def get_ch_trace_server(
    ensure_clickhouse_db,
    request,
) -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def ch_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        host, port = next(ensure_clickhouse_db())

        # Get pytest-xdist worker id if running in parallel
        # worker_id will be 'gw0', 'gw1', etc. when running with -n
        # or None when running without parallelization
        worker_input = getattr(request.config, "workerinput", None)

        # Create a unique database suffix for this worker
        if worker_input is None:
            # Not running in parallel
            db_suffix = ""
        else:
            # Running in parallel - use worker id
            worker_id = worker_input.get("workerid", "master")
            # Extract the numeric part from 'gw0', 'gw1', etc.
            db_suffix = f"_w{worker_id.replace('gw', '')}"

        # Store original environment variables
        original_db = os.environ.get("WF_CLICKHOUSE_DATABASE")

        # Set unique database names for this worker
        base_db = original_db or "default"
        unique_db = f"{base_db}{db_suffix}"
        os.environ["WF_CLICKHOUSE_DATABASE"] = unique_db

        try:
            id_converter = DummyIdConverter()
            ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
                host=host,
                port=port,
                evaluate_model_dispatcher=EvaluateModelTestDispatcher(
                    id_converter=id_converter
                ),
            )

            # Clean up databases with worker-specific names
            management_db = f"db_management{db_suffix}"
            ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {management_db}")
            ch_server.ch_client.command(f"DROP DATABASE IF EXISTS {unique_db}")

            # Patch the migrator to use worker-specific db_management database
            # This ensures complete isolation between parallel test workers
            original_create_db_sql = clickhouse_trace_server_migrator.ClickHouseTraceServerMigrator._create_db_sql
            original_initialize_migration_db = clickhouse_trace_server_migrator.ClickHouseTraceServerMigrator._initialize_migration_db

            def patched_create_db_sql(self, db_name):
                # Use worker-specific name for db_management
                if db_name == "db_management":
                    db_name = management_db
                return original_create_db_sql(self, db_name)

            def patched_initialize_migration_db(self):
                # Initialize with worker-specific db_management database
                self.ch_client.command(self._create_db_sql(management_db))
                create_table_sql = f"""
                    CREATE TABLE IF NOT EXISTS {management_db}.migrations
                    (
                        db_name String,
                        curr_version UInt64,
                        partially_applied_version Nullable(UInt64)
                    ) ENGINE = MergeTree() ORDER BY db_name
                """
                self.ch_client.command(create_table_sql)

            with (
                mock.patch.object(
                    clickhouse_trace_server_migrator.ClickHouseTraceServerMigrator,
                    "_create_db_sql",
                    patched_create_db_sql,
                ),
                mock.patch.object(
                    clickhouse_trace_server_migrator.ClickHouseTraceServerMigrator,
                    "_initialize_migration_db",
                    patched_initialize_migration_db,
                ),
                mock.patch(
                    "weave.trace_server.clickhouse_trace_server_migrator.ClickHouseTraceServerMigrator._get_migration_status",
                    side_effect=lambda db_name: {
                        "curr_version": 0,
                        "partially_applied_version": None,
                        "db_name": db_name,
                    },
                ) as mock_status,
                mock.patch(
                    "weave.trace_server.clickhouse_trace_server_migrator.ClickHouseTraceServerMigrator._update_migration_status"
                ) as mock_update,
            ):
                # Patch _get_migration_status to use worker-specific db_management
                # Create closures that capture ch_client and management_db
                # Note: side_effect receives only method arguments (excluding self)
                def make_patched_get_status(ch_client, mgmt_db):
                    def patched_get_status(db_name):
                        # Query from worker-specific db_management database
                        column_names = [
                            "db_name",
                            "curr_version",
                            "partially_applied_version",
                        ]
                        select_columns = ", ".join(column_names)
                        query = f"""
                            SELECT {select_columns} FROM {mgmt_db}.migrations WHERE db_name = '{db_name}'
                        """
                        res = ch_client.query(query)
                        result_rows = res.result_rows
                        if res is None or len(result_rows) == 0:
                            ch_client.insert(
                                f"{mgmt_db}.migrations",
                                data=[[db_name, 0, None]],
                                column_names=column_names,
                            )
                            return {
                                "curr_version": 0,
                                "partially_applied_version": None,
                                "db_name": db_name,
                            }
                        return dict(zip(column_names, result_rows[0]))

                    return patched_get_status

                # Patch _update_migration_status to use worker-specific db_management
                def make_patched_update_status(ch_client, mgmt_db):
                    def patched_update_status(target_db, target_version, is_start=True):
                        if is_start:
                            ch_client.command(
                                f"ALTER TABLE {mgmt_db}.migrations UPDATE partially_applied_version = {target_version} WHERE db_name = '{target_db}'"
                            )
                        else:
                            ch_client.command(
                                f"ALTER TABLE {mgmt_db}.migrations UPDATE curr_version = {target_version}, partially_applied_version = NULL WHERE db_name = '{target_db}'"
                            )

                    return patched_update_status

                mock_status.side_effect = make_patched_get_status(
                    ch_server.ch_client, management_db
                )
                mock_update.side_effect = make_patched_update_status(
                    ch_server.ch_client, management_db
                )

                # Run migrations with patched methods
                ch_server._run_migrations()

            result = externalize_trace_server(
                ch_server, TEST_ENTITY, id_converter=id_converter
            )

            return result
        finally:
            # Restore the original database name
            if original_db is None:
                os.environ.pop("WF_CLICKHOUSE_DATABASE", None)
            else:
                os.environ["WF_CLICKHOUSE_DATABASE"] = original_db

    return ch_trace_server_inner


@pytest.fixture
def get_sqlite_trace_server() -> Callable[[], TestOnlyUserInjectingExternalTraceServer]:
    def sqlite_trace_server_inner() -> TestOnlyUserInjectingExternalTraceServer:
        id_converter = DummyIdConverter()
        sqlite_server = SqliteTraceServer(
            "file::memory:?cache=shared",
            evaluate_model_dispatcher=EvaluateModelTestDispatcher(
                id_converter=id_converter
            ),
        )
        sqlite_server.drop_tables()
        sqlite_server.setup_tables()
        return externalize_trace_server(
            sqlite_server, TEST_ENTITY, id_converter=id_converter
        )

    return sqlite_trace_server_inner


class LocalSecretFetcher:
    def fetch(self, secret_name: str) -> dict:
        return {"secrets": {secret_name: os.getenv(secret_name)}}


@pytest.fixture
def local_secret_fetcher():
    with secret_fetcher_context(LocalSecretFetcher()):
        yield


@pytest.fixture
def trace_server(
    request, local_secret_fetcher, get_ch_trace_server, get_sqlite_trace_server
) -> TestOnlyUserInjectingExternalTraceServer:
    trace_server_flag = get_trace_server_flag(request)
    if trace_server_flag == "clickhouse":
        return get_ch_trace_server()
    elif trace_server_flag == "sqlite":
        return get_sqlite_trace_server()
    else:
        # Once we split the trace server and client code, we can raise here.
        # For now, just return the sqlite trace server so we don't break existing tests.
        # raise ValueError(f"Invalid trace server: {trace_server_flag}")
        return get_sqlite_trace_server()
