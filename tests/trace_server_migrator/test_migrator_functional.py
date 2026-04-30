"""Functional tests for ClickHouse migrator in cloud, replicated, and distributed modes.

Runs actual SQL against a single-node ClickHouse with embedded Keeper.
"""

import os
import time
import uuid

from weave.trace_server.clickhouse_trace_server_migrator import (
    SQUASH_MIGRATION_VERSION,
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
    the returned dict. That is the silent-misconfig failure mode of the
    `ON CLUSTER + ENGINE = Replicated` combination on CH <= 25.3: peer
    replicas never got the DB, and the migrator saw success because the
    entrypoint pod had it.
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


def test_replicated_creates_atomic_dbs_and_replicated_tables(ch_client):
    """New replicated-mode deployment: DBs are Atomic + ON CLUSTER, tables
    inside are ReplicatedMergeTree.

    Atomic databases don't race the Replicated DB engine against the
    distributed-DDL queue, and ON CLUSTER fans CREATE DATABASE out to
    every replica, so every replica ends up with the DB (no split-brain).
    """
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

    assert _get_db_engine(ch_client, mgmt_db) == "Atomic"
    assert _get_db_engine(ch_client, target_db) == "Atomic"
    assert _get_table_engine_full(ch_client, mgmt_db, "migrations").startswith(
        "ReplicatedMergeTree"
    )
    assert _get_table_engine_full(ch_client, target_db, "test_tbl").startswith(
        "ReplicatedMergeTree"
    )


def test_distributed_fresh_creates_atomic_dbs(ch_client):
    """New deployment: both management DB and data DB are Atomic + ON CLUSTER.

    Atomic + ON CLUSTER is the only shape that fans out across every shard
    without racing the Replicated DB engine's own DDL propagation. Tables
    inside Atomic DBs get explicit ReplicatedMergeTree with per-shard ZK
    paths so data still replicates within each shard.
    """
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

    assert _get_db_engine(ch_client, target_db) == "Atomic"
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

    # Legacy Replicated management DB: the migrator sends plain
    # `ENGINE = MergeTree()` and lets the DB engine handle replication.
    # On single-node CI the DB engine does NOT auto-convert to
    # ReplicatedMergeTree (single host, no peers to replicate to), so the
    # engine_full column reports plain MergeTree. The important property
    # here is the absence of the Atomic branch's shared ZK path
    # (`/clickhouse/tables/shared/...`) - this assertion pins both the
    # engine and the full ORDER BY / SETTINGS tail so any drift surfaces.
    mgmt_engine = _get_table_engine_full(ch_client, mgmt_db, "migrations")
    assert mgmt_engine == "MergeTree ORDER BY db_name SETTINGS index_granularity = 8192"

    migrator.apply_migrations(target_db)

    # target_db is freshly created by the migrator, which now uses Atomic +
    # ON CLUSTER for every DB in distributed mode. The legacy Replicated
    # management DB keeps its engine via IF NOT EXISTS.
    assert _get_db_engine(ch_client, target_db) == "Atomic"
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

    assert _get_db_engine(ch_client, target_db) == "Atomic"
    # On multi-replica topologies (1s3r / 2s2r in CI), the DB must exist on
    # every replica with a consistent engine. Historical failure modes this
    # assertion guards against:
    #   * `ON CLUSTER` combined with `ENGINE = Replicated` (silent plain
    #     MergeTree on CH <= 25.3, deadlock on CH >= 25.10).
    #   * `ENGINE = Replicated` with `ON CLUSTER` stripped (split-brain:
    #     only the migrator's entrypoint pod gets the DB, sibling replicas
    #     never join the ZK path).
    _assert_db_on_every_replica(ch_client, target_db, expected_engine="Atomic")


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
    assert _get_db_engine(ch_client, target_db) == "Atomic"
    # Distributed mode uses ON CLUSTER to fan DBs to every shard/replica.
    # If the fan-out is broken (e.g. the `ON CLUSTER + ENGINE = Replicated`
    # collision), peer replicas never receive the CREATE DATABASE.
    _assert_db_on_every_replica(ch_client, mgmt_db, expected_engine="Atomic")
    _assert_db_on_every_replica(ch_client, target_db, expected_engine="Atomic")


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
    assert _get_db_engine(ch_client, target_db) == "Atomic"

    # ALTER TABLE UPDATE mutations are async; wait for them to settle
    _sync_mutations(ch_client, mgmt_db, "migrations")

    # Migrate all the way back down (squash does not affect down migrations)
    migrator.use_squash_migration = False
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
    assert _get_db_engine(ch_client, target_db) == "Atomic"

    # ALTER TABLE UPDATE mutations are async; wait for them to settle
    _sync_mutations(ch_client, mgmt_db, "migrations")

    # Migrate all the way back down
    migrator.apply_migrations(target_db, target_version=0)


# ---------------------------------------------------------------------------
# Squash migration tests
# ---------------------------------------------------------------------------

# Tables created by intermediate migration steps (e.g., rename dances) that
# exist in the sequential path but NOT in the squash path.
_MIGRATION_ARTIFACT_TABLES = {"calls_complete_old"}


def _get_all_tables(ch_client, db_name: str) -> list[str]:
    """Return sorted list of table/view names in a database."""
    result = ch_client.query(
        f"SELECT name FROM system.tables WHERE database = '{db_name}' ORDER BY name"
    )
    return [row[0] for row in result.result_rows]


def _get_create_table_normalized(ch_client, db_name: str, table_name: str) -> str:
    """Return SHOW CREATE TABLE output with the database name replaced."""
    result = ch_client.query(f"SHOW CREATE TABLE {db_name}.{table_name}")
    ddl = result.result_rows[0][0]
    return ddl.replace(db_name, "TARGET_DB")


def test_squash_migration_version_matches_migration_count(ch_client):
    """SQUASH_MIGRATION_VERSION must equal the number of individual migrations."""
    mgmt_db = _unique_name("db_mgmt_count")
    target_db = _unique_name("count")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=False,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migration_map = migrator._get_migrations()
    assert SQUASH_MIGRATION_VERSION == len(migration_map), (
        f"SQUASH_MIGRATION_VERSION ({SQUASH_MIGRATION_VERSION}) != "
        f"migration count ({len(migration_map)}). "
        f"Update SQUASH_MIGRATION_VERSION after adding a new migration."
    )


def test_squash_migration_matches_sequential(ch_client):
    """Squash migration produces the same schema as running all migrations."""
    # --- Path A: sequential (squash disabled) ---
    mgmt_db_seq = _unique_name("db_mgmt_seq")
    target_db_seq = _unique_name("seq")
    ch_client.track_db(mgmt_db_seq)
    ch_client.track_db(target_db_seq)

    migrator_seq = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=False,
        management_db=mgmt_db_seq,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migrator_seq.use_squash_migration = False
    migrator_seq.apply_migrations(target_db_seq)

    # --- Path B: squash ---
    mgmt_db_squash = _unique_name("db_mgmt_squash")
    target_db_squash = _unique_name("squash")
    ch_client.track_db(mgmt_db_squash)
    ch_client.track_db(target_db_squash)

    migrator_squash = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=False,
        management_db=mgmt_db_squash,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migrator_squash.apply_migrations(target_db_squash)

    # --- Compare schemas ---
    tables_seq = _get_all_tables(ch_client, target_db_seq)
    tables_squash = _get_all_tables(ch_client, target_db_squash)

    # Filter out migration artifacts from the sequential path
    tables_seq_filtered = [t for t in tables_seq if t not in _MIGRATION_ARTIFACT_TABLES]

    assert tables_seq_filtered == tables_squash, (
        f"Table sets differ.\n"
        f"  Sequential only: {set(tables_seq_filtered) - set(tables_squash)}\n"
        f"  Squash only:     {set(tables_squash) - set(tables_seq_filtered)}"
    )

    for table_name in tables_squash:
        ddl_seq = _get_create_table_normalized(ch_client, target_db_seq, table_name)
        ddl_squash = _get_create_table_normalized(
            ch_client, target_db_squash, table_name
        )
        assert ddl_seq == ddl_squash, (
            f"Schema mismatch for `{table_name}`:\n"
            f"--- sequential ---\n{ddl_seq}\n"
            f"--- squash ---\n{ddl_squash}"
        )


def test_squash_migration_sets_correct_version(ch_client):
    """After squash, db_management records SQUASH_MIGRATION_VERSION."""
    mgmt_db = _unique_name("db_mgmt_ver")
    target_db = _unique_name("ver")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=False,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migrator.apply_migrations(target_db)

    _sync_mutations(ch_client, mgmt_db, "migrations")

    result = ch_client.query(
        f"SELECT curr_version, partially_applied_version "
        f"FROM {mgmt_db}.migrations WHERE db_name = '{target_db}'"
    )
    assert len(result.result_rows) == 1
    curr_version, partial = result.result_rows[0]
    assert curr_version == SQUASH_MIGRATION_VERSION
    assert partial is None
