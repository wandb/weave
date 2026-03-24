"""Functional tests for ClickHouse migrator in cloud, replicated, and distributed modes.

Runs actual SQL against a single-node ClickHouse with embedded Keeper.
"""

import os
import uuid

from weave.trace_server.clickhouse_trace_server_migrator import (
    get_clickhouse_trace_server_migrator,
)

_TEST_MIGRATION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "test_migrations")
)
_CLUSTER = "weave_cluster"
_REPLICATED_PATH = "/clickhouse/tables/{db}"


def _unique_name(prefix: str) -> str:
    """Generate a unique DB name to avoid ZK path collisions between test runs."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _get_db_engine(ch_client, db_name: str) -> str:
    result = ch_client.query(
        f"SELECT engine FROM system.databases WHERE name = '{db_name}'"
    )
    assert len(result.result_rows) == 1, f"Database {db_name} not found"
    return result.result_rows[0][0]


def _get_table_engine_full(ch_client, db_name: str, table_name: str) -> str:
    """Return engine_full string."""
    result = ch_client.query(
        f"SELECT engine_full FROM system.tables WHERE database = '{db_name}' AND name = '{table_name}'"
    )
    assert len(result.result_rows) == 1, f"Table {db_name}.{table_name} not found"
    return result.result_rows[0][0]


def _table_exists(ch_client, db_name: str, table_name: str) -> bool:
    result = ch_client.query(
        f"SELECT count() FROM system.tables WHERE database = '{db_name}' AND name = '{table_name}'"
    )
    return result.result_rows[0][0] > 0


class TestCloudMigrator:
    def test_creates_db_and_tables(self, ch_client):
        mgmt_db = _unique_name("db_mgmt_cloud")
        target_db = _unique_name("test_cloud")
        ch_client.track_db(mgmt_db)
        ch_client.track_db(target_db)

        migrator = get_clickhouse_trace_server_migrator(
            ch_client,
            replicated=False,
            use_distributed=False,
            management_db=mgmt_db,
            migration_dir=_TEST_MIGRATION_DIR,
            post_migration_hook=None,
        )
        migrator.apply_migrations(target_db)

        assert _get_db_engine(ch_client, mgmt_db) == "Atomic"
        assert _get_table_engine_full(ch_client, mgmt_db, "migrations").startswith(
            "MergeTree"
        )
        assert _get_table_engine_full(ch_client, target_db, "test_tbl").startswith(
            "MergeTree"
        )


class TestReplicatedMigrator:
    def test_creates_replicated_db_and_tables(self, ch_client):
        mgmt_db = _unique_name("db_mgmt_repl")
        target_db = _unique_name("test_repl")
        ch_client.track_db(mgmt_db)
        ch_client.track_db(target_db)

        migrator = get_clickhouse_trace_server_migrator(
            ch_client,
            replicated=True,
            use_distributed=False,
            replicated_cluster=_CLUSTER,
            replicated_path=_REPLICATED_PATH,
            management_db=mgmt_db,
            migration_dir=_TEST_MIGRATION_DIR,
            post_migration_hook=None,
        )
        migrator.apply_migrations(target_db)

        # Both DBs should be Replicated
        assert _get_db_engine(ch_client, mgmt_db) == "Replicated"
        assert _get_db_engine(ch_client, target_db) == "Replicated"

        # Tables exist and are MergeTree (Replicated DB handles replication at DB level)
        assert _table_exists(ch_client, mgmt_db, "migrations")
        assert _table_exists(ch_client, target_db, "test_tbl")


class TestDistributedMigrator:
    def test_fresh_creates_atomic_management_db(self, ch_client):
        """New deployment: management DB is Atomic with explicit shared ReplicatedMergeTree."""
        mgmt_db = _unique_name("db_mgmt_dist")
        target_db = _unique_name("test_dist")
        ch_client.track_db(mgmt_db)
        ch_client.track_db(target_db)

        migrator = get_clickhouse_trace_server_migrator(
            ch_client,
            replicated=True,
            use_distributed=True,
            replicated_cluster=_CLUSTER,
            replicated_path=_REPLICATED_PATH,
            management_db=mgmt_db,
            migration_dir=_TEST_MIGRATION_DIR,
            post_migration_hook=None,
        )
        migrator.apply_migrations(target_db)

        # Management DB should be Atomic (not Replicated)
        assert _get_db_engine(ch_client, mgmt_db) == "Atomic"

        # Migrations table should be explicit ReplicatedMergeTree with shared ZK path
        mgmt_engine = _get_table_engine_full(ch_client, mgmt_db, "migrations")
        assert mgmt_engine.startswith("ReplicatedMergeTree")
        assert "/shared/" in mgmt_engine

        # Data DB should be Replicated
        assert _get_db_engine(ch_client, target_db) == "Replicated"

        # Distributed mode creates local + distributed table pairs
        assert _table_exists(ch_client, target_db, "test_tbl_local")
        assert _get_table_engine_full(ch_client, target_db, "test_tbl").startswith(
            "Distributed"
        )

    def test_legacy_replicated_management_db(self, ch_client):
        """Existing deployment: management DB already Replicated, falls back to MergeTree."""
        mgmt_db = _unique_name("db_mgmt_legacy")
        target_db = _unique_name("test_legacy")
        ch_client.track_db(mgmt_db)
        ch_client.track_db(target_db)

        # Pre-create management DB with Replicated engine (simulates legacy deployment)
        replicated_path = _REPLICATED_PATH.replace("{db}", mgmt_db)
        ch_client.command(
            f"CREATE DATABASE {mgmt_db} ON CLUSTER {_CLUSTER}"
            f" ENGINE = Replicated('{replicated_path}', '{{shard}}', '{{replica}}')"
        )

        migrator = get_clickhouse_trace_server_migrator(
            ch_client,
            replicated=True,
            use_distributed=True,
            replicated_cluster=_CLUSTER,
            replicated_path=_REPLICATED_PATH,
            management_db=mgmt_db,
            migration_dir=_TEST_MIGRATION_DIR,
            post_migration_hook=None,
        )

        # Management DB should still be Replicated (IF NOT EXISTS is a no-op)
        assert _get_db_engine(ch_client, mgmt_db) == "Replicated"

        # Migrations table exists (no shared ZK path — DB-level replication)
        mgmt_engine = _get_table_engine_full(ch_client, mgmt_db, "migrations")
        assert "/shared/" not in mgmt_engine

        # Apply migrations should still work
        migrator.apply_migrations(target_db)

        # Data DB should be Replicated with local + distributed tables
        assert _get_db_engine(ch_client, target_db) == "Replicated"
        assert _table_exists(ch_client, target_db, "test_tbl_local")
        assert _get_table_engine_full(ch_client, target_db, "test_tbl").startswith(
            "Distributed"
        )
