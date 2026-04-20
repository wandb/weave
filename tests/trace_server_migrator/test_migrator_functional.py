"""Functional tests for ClickHouse migrator in cloud, replicated, and distributed modes.

Runs actual SQL against a single-node ClickHouse with embedded Keeper.
"""

import os
import time
import uuid

from weave.trace_server.clickhouse_trace_server_migrator import (
    get_clickhouse_trace_server_migrator,
)

_TEST_MIGRATION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "test_migrations")
)
_PROD_MIGRATION_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "weave", "trace_server", "migrations"
    )
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


def _sync_mutations(ch_client, db_name: str, table_name: str) -> None:
    """Wait for all pending mutations to complete on a table."""
    for _ in range(50):
        result = ch_client.query(
            "SELECT count() FROM system.mutations "
            f"WHERE database = '{db_name}' AND table = '{table_name}' AND is_done = 0"
        )
        if result.result_rows[0][0] == 0:
            return
        time.sleep(0.1)
    raise TimeoutError(f"Mutations on {db_name}.{table_name} did not complete")


def _table_exists(ch_client, db_name: str, table_name: str) -> bool:
    result = ch_client.query(
        f"SELECT count() FROM system.tables WHERE database = '{db_name}' AND name = '{table_name}'"
    )
    return result.result_rows[0][0] > 0


def _cluster_replica_count(ch_client) -> int:
    """Return the number of replicas in the test cluster."""
    result = ch_client.query(
        f"SELECT count() FROM system.clusters WHERE cluster = '{_CLUSTER}'"
    )
    return int(result.result_rows[0][0])


def _db_engines_across_cluster(ch_client, db_name: str) -> dict[str, str]:
    """{host: engine} for db_name across every replica in the cluster.

    Uses clusterAllReplicas so this works through a single HTTP entrypoint
    on multi-replica topologies (1s3r / 2s2r) where only one CH node
    exposes a host port. On a single-node local fallback, returns a
    one-entry dict.

    A DB missing from a replica shows up as that host being absent from
    the returned dict — which is exactly the silent-misconfig failure
    mode from the pre-#6659 ON CLUSTER + ENGINE = Replicated bug on
    CH <= 25.3 (peer replicas never got the DB; migrator saw success
    because pod 0 had it).
    """
    result = ch_client.query(
        f"SELECT hostName(), engine FROM clusterAllReplicas('{_CLUSTER}', system.databases) "
        f"WHERE name = '{db_name}'"
    )
    return {row[0]: row[1] for row in result.result_rows}


def _assert_db_on_every_replica(
    ch_client, db_name: str, expected_engine: str | None = None
) -> None:
    """Fail if the DB is missing from any replica or has an inconsistent engine.

    Pass expected_engine to pin the engine; leave it None to only check
    that every replica reports the same engine.
    """
    engines = _db_engines_across_cluster(ch_client, db_name)
    expected_count = _cluster_replica_count(ch_client)
    assert len(engines) == expected_count, (
        f"{db_name} missing from {expected_count - len(engines)} replica(s). "
        f"Got: {engines}"
    )
    distinct = set(engines.values())
    assert len(distinct) == 1, (
        f"{db_name} engine inconsistent across replicas: {engines}"
    )
    if expected_engine is not None:
        (actual,) = distinct
        assert actual == expected_engine, (
            f"{db_name} engine = {actual!r}, expected {expected_engine!r}"
        )


def test_cloud_creates_db_and_tables(ch_client):
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


def test_replicated_creates_replicated_db_and_tables(ch_client):
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

    assert _get_db_engine(ch_client, mgmt_db) == "Replicated"
    assert _get_db_engine(ch_client, target_db) == "Replicated"
    assert _get_table_engine_full(ch_client, mgmt_db, "migrations").startswith(
        "ReplicatedMergeTree"
    )
    assert _get_table_engine_full(ch_client, target_db, "test_tbl").startswith(
        "ReplicatedMergeTree"
    )


def test_distributed_fresh_creates_atomic_management_db(ch_client):
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

    assert _get_db_engine(ch_client, mgmt_db) == "Atomic"

    mgmt_engine = _get_table_engine_full(ch_client, mgmt_db, "migrations")
    assert mgmt_engine.startswith("ReplicatedMergeTree")
    assert "/shared/" in mgmt_engine

    assert _get_db_engine(ch_client, target_db) == "Replicated"
    assert _table_exists(ch_client, target_db, "test_tbl_local")
    assert _get_table_engine_full(ch_client, target_db, "test_tbl_local").startswith(
        "ReplicatedMergeTree"
    )
    assert _get_table_engine_full(ch_client, target_db, "test_tbl").startswith(
        "Distributed"
    )


def test_distributed_legacy_replicated_management_db(ch_client):
    """Existing deployment: management DB already Replicated, falls back to MergeTree."""
    mgmt_db = _unique_name("db_mgmt_legacy")
    target_db = _unique_name("test_legacy")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

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

    assert _get_db_engine(ch_client, mgmt_db) == "Replicated"

    mgmt_engine = _get_table_engine_full(ch_client, mgmt_db, "migrations")
    assert "/shared/" not in mgmt_engine

    migrator.apply_migrations(target_db)

    assert _get_db_engine(ch_client, target_db) == "Replicated"
    assert _table_exists(ch_client, target_db, "test_tbl_local")
    assert _get_table_engine_full(ch_client, target_db, "test_tbl_local").startswith(
        "ReplicatedMergeTree"
    )
    assert _get_table_engine_full(ch_client, target_db, "test_tbl").startswith(
        "Distributed"
    )


def test_all_production_migrations_replicated(ch_client):
    """All production migrations apply cleanly in replicated mode."""
    mgmt_db = _unique_name("db_mgmt_prod_repl")
    target_db = _unique_name("prod_repl")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=True,
        use_distributed=False,
        replicated_cluster=_CLUSTER,
        replicated_path=_REPLICATED_PATH,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migrator.apply_migrations(target_db)

    assert _get_db_engine(ch_client, target_db) == "Replicated"
    # On multi-replica topologies (1s3r / 2s2r in CI), the DB must exist on
    # every replica with a consistent engine. A silent-misconfig bug like
    # the pre-#6659 ON CLUSTER + ENGINE = Replicated collision would leave
    # the DB on only the migrator's entrypoint pod — this assertion is the
    # observable signal for that class of failure.
    _assert_db_on_every_replica(ch_client, target_db, expected_engine="Replicated")


def test_all_production_migrations_distributed(ch_client):
    """All production migrations apply cleanly in distributed mode."""
    mgmt_db = _unique_name("db_mgmt_prod_dist")
    target_db = _unique_name("prod_dist")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=True,
        use_distributed=True,
        replicated_cluster=_CLUSTER,
        replicated_path=_REPLICATED_PATH,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migrator.apply_migrations(target_db)

    assert _get_db_engine(ch_client, mgmt_db) == "Atomic"
    assert _get_db_engine(ch_client, target_db) == "Replicated"
    # Distributed mode uses ON CLUSTER to fan DBs to every shard/replica.
    # If the fan-out is broken (e.g. the pre-#6659 ON CLUSTER + Replicated
    # collision), peer replicas never receive the CREATE DATABASE.
    _assert_db_on_every_replica(ch_client, mgmt_db, expected_engine="Atomic")
    _assert_db_on_every_replica(ch_client, target_db, expected_engine="Replicated")


def test_all_production_down_migrations_replicated(ch_client):
    """All production down migrations apply cleanly in replicated mode."""
    mgmt_db = _unique_name("db_mgmt_down_repl")
    target_db = _unique_name("down_repl")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=True,
        use_distributed=False,
        replicated_cluster=_CLUSTER,
        replicated_path=_REPLICATED_PATH,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )

    # Migrate up to latest
    migrator.apply_migrations(target_db)
    assert _get_db_engine(ch_client, target_db) == "Replicated"

    # ALTER TABLE UPDATE mutations are async; wait for them to settle
    _sync_mutations(ch_client, mgmt_db, "migrations")

    # Migrate all the way back down
    migrator.apply_migrations(target_db, target_version=0)


def test_all_production_down_migrations_distributed(ch_client):
    """All production down migrations apply cleanly in distributed mode."""
    mgmt_db = _unique_name("db_mgmt_down_dist")
    target_db = _unique_name("down_dist")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=True,
        use_distributed=True,
        replicated_cluster=_CLUSTER,
        replicated_path=_REPLICATED_PATH,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )

    # Migrate up to latest
    migrator.apply_migrations(target_db)
    assert _get_db_engine(ch_client, mgmt_db) == "Atomic"
    assert _get_db_engine(ch_client, target_db) == "Replicated"

    # ALTER TABLE UPDATE mutations are async; wait for them to settle
    _sync_mutations(ch_client, mgmt_db, "migrations")

    # Migrate all the way back down
    migrator.apply_migrations(target_db, target_version=0)
