"""Functional tests for ClickHouse migrator in cloud, replicated, and distributed modes.

Runs actual SQL against a single-node ClickHouse with embedded Keeper.
"""

import os
import threading
import time
import uuid

import clickhouse_connect
import pytest

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


def _get_migration_version(ch_client, mgmt_db: str, target_db: str) -> int:
    result = ch_client.query(
        f"SELECT curr_version FROM {mgmt_db}.migrations WHERE db_name = '{target_db}'"
    )
    assert len(result.result_rows) == 1, f"Migration status for {target_db} not found"
    return int(result.result_rows[0][0])


def _partially_applied_version(ch_client, mgmt_db: str, target_db: str) -> int | None:
    result = ch_client.query(
        f"SELECT partially_applied_version FROM {mgmt_db}.migrations WHERE db_name = '{target_db}'"
    )
    assert len(result.result_rows) == 1, f"Migration status for {target_db} not found"
    value = result.result_rows[0][0]
    return None if value is None else int(value)


def _get_latest_migration_version(migration_dir: str) -> int:
    versions = [
        int(file.split("_", 1)[0])
        for file in os.listdir(migration_dir)
        if file.endswith(".up.sql")
    ]
    assert versions, f"No up migrations found in {migration_dir}"
    return max(versions)


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


def _sync_mutations(ch_client, db_name: str) -> None:
    """Block until every table in db_name has no in-flight mutations.

    Bounded wait so a genuinely stuck mutation surfaces as a test failure
    rather than an infinite hang.
    """
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if not _stuck_mutations(ch_client, db_name):
            return
        time.sleep(0.5)


def _stuck_mutations(ch_client, db_name: str) -> list[tuple[str, str]]:
    """{(table, mutation_id)} for mutations still running across the cluster."""
    result = ch_client.query(
        f"SELECT table, mutation_id FROM clusterAllReplicas('{_CLUSTER}', system.mutations) "
        f"WHERE database = '{db_name}' AND is_done = 0"
    )
    return [(row[0], row[1]) for row in result.result_rows]


def _assert_table_schema_converged(ch_client, db_name: str, table_name: str) -> None:
    """Fail if a table is missing from a replica or its columns diverge.

    Compares the (name, type) column set per replica via clusterAllReplicas.
    This is the incident's failure mode (a column present on some replicas,
    absent on others) and is robust to replica-specific DDL/path rendering
    that would make raw create_table_query comparison false-positive.
    """
    result = ch_client.query(
        f"SELECT hostName(), name, type FROM clusterAllReplicas('{_CLUSTER}', system.columns) "
        f"WHERE database = '{db_name}' AND table = '{table_name}' ORDER BY name"
    )
    by_host: dict[str, list[tuple[str, str]]] = {}
    for host, name, col_type in result.result_rows:
        by_host.setdefault(host, []).append((name, col_type))
    expected_count = _cluster_replica_count(ch_client)
    assert len(by_host) == expected_count, (
        f"{db_name}.{table_name} missing from {expected_count - len(by_host)} replica(s). "
        f"Got hosts: {sorted(by_host)}"
    )
    distinct = {tuple(cols) for cols in by_host.values()}
    assert len(distinct) == 1, (
        f"{db_name}.{table_name} columns diverge across replicas: {by_host}"
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


def test_replicated_existing_replicated_target_db_upgrade(ch_client, tmp_path):
    """Upgrade path: existing Replicated data DBs must not receive ON CLUSTER DDL."""
    mgmt_db = _unique_name("db_mgmt_upgrade")
    target_db = _unique_name("test_upgrade")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    replicated_path = _REPLICATED_PATH.replace("{db}", target_db)
    ch_client.command(
        f"CREATE DATABASE {target_db} ON CLUSTER {_CLUSTER}"
        f" ENGINE = Replicated('{replicated_path}', '{{shard}}', '{{replica}}')"
    )

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "001_init.up.sql").write_text(
        "CREATE TABLE already_applied (id String) ENGINE = MergeTree ORDER BY id;"
    )
    (migration_dir / "001_init.down.sql").write_text(
        "DROP TABLE IF EXISTS already_applied;"
    )
    (migration_dir / "002_upgrade.up.sql").write_text(
        """
        -- Mirrors the 026 object_version_first_seen shape that failed for customers.
        CREATE TABLE IF NOT EXISTS object_version_first_seen (
            project_id String,
            object_id String,
            digest String,
            first_created_at SimpleAggregateFunction(min, DateTime64(3))
        ) ENGINE = AggregatingMergeTree()
        ORDER BY (project_id, object_id, digest);
        """
    )
    (migration_dir / "002_upgrade.down.sql").write_text(
        "DROP TABLE IF EXISTS object_version_first_seen;"
    )

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=True,
        use_distributed=False,
        replicated_cluster=_CLUSTER,
        replicated_path=_REPLICATED_PATH,
        management_db=mgmt_db,
        migration_dir=str(migration_dir),
        post_migration_hook=None,
    )
    ch_client.insert(
        f"{mgmt_db}.migrations",
        data=[[target_db, 1, None]],
        column_names=["db_name", "curr_version", "partially_applied_version"],
    )

    migrator.apply_migrations(target_db, target_version=2)

    assert _get_db_engine(ch_client, target_db) == "Replicated"
    assert _get_table_engine_full(
        ch_client, target_db, "object_version_first_seen"
    ).startswith("ReplicatedAggregatingMergeTree")


@pytest.mark.parametrize(
    ("case_name", "use_distributed", "precreate_replicated_db", "expected_engine"),
    [
        pytest.param("repl_atomic", False, False, "Atomic", id="replicated-atomic-db"),
        pytest.param(
            "repl_replicated",
            False,
            True,
            "Replicated",
            id="replicated-legacy-replicated-db",
        ),
        pytest.param("dist_atomic", True, False, "Atomic", id="distributed-atomic-db"),
        pytest.param(
            "dist_replicated",
            True,
            True,
            "Replicated",
            id="distributed-legacy-replicated-db",
        ),
    ],
)
def test_recent_production_upgrade_path(
    ch_client,
    case_name: str,
    use_distributed: bool,
    precreate_replicated_db: bool,
    expected_engine: str,
):
    """Customer-style upgrades from an existing DB run the latest migration batch."""
    latest_version = _get_latest_migration_version(_PROD_MIGRATION_DIR)
    seed_version = latest_version - 5
    assert seed_version > 0

    def make_migrator(*, mgmt_db: str, use_distributed: bool):
        return get_clickhouse_trace_server_migrator(
            ch_client,
            replicated=True,
            use_distributed=use_distributed,
            replicated_cluster=_CLUSTER,
            replicated_path=_REPLICATED_PATH,
            management_db=mgmt_db,
            migration_dir=_PROD_MIGRATION_DIR,
            post_migration_hook=None,
        )

    mgmt_db = _unique_name(f"db_mgmt_recent_{case_name}")
    target_db = _unique_name(f"prod_recent_{case_name}")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    if precreate_replicated_db:
        replicated_path = _REPLICATED_PATH.replace("{db}", target_db)
        ch_client.command(
            f"CREATE DATABASE {target_db} ON CLUSTER {_CLUSTER}"
            f" ENGINE = Replicated('{replicated_path}', '{{shard}}', '{{replica}}')"
        )

    # Seed a real old schema using production migrations, not hand-written DDL.
    seed_migrator = make_migrator(mgmt_db=mgmt_db, use_distributed=use_distributed)
    seed_migrator.apply_migrations(target_db, target_version=seed_version)
    assert _get_migration_version(ch_client, mgmt_db, target_db) == seed_version
    assert _get_db_engine(ch_client, target_db) == expected_engine

    # A new init container starts with an empty engine cache, then upgrades.
    upgrade_migrator = make_migrator(mgmt_db=mgmt_db, use_distributed=use_distributed)
    upgrade_migrator.apply_migrations(target_db)
    assert _get_migration_version(ch_client, mgmt_db, target_db) == latest_version
    assert _get_db_engine(ch_client, target_db) == expected_engine
    assert _table_exists(ch_client, target_db, "object_version_first_seen")

    if use_distributed:
        assert _table_exists(ch_client, target_db, "object_version_first_seen_local")
        engine_table = "object_version_first_seen_local"
    else:
        engine_table = "object_version_first_seen"

    assert _get_table_engine_full(ch_client, target_db, engine_table).startswith(
        "ReplicatedAggregatingMergeTree"
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
    assert _get_db_engine(ch_client, target_db) == "Atomic"

    # Migrate all the way back down
    migrator.apply_migrations(target_db, target_version=0)


@pytest.mark.parametrize("use_distributed", [False, True])
def test_production_migrations_converge_across_replicas(ch_client, use_distributed):
    """After the full prod dir, every replica agrees on schema and status.

    Guards the load/topology-dependent class where the initiating node sees
    success but a peer replica never converged: version at max, no partial
    version left set, no stuck mutations, and identical create_table_query on
    every replica for the key tables.
    """
    mode = "dist" if use_distributed else "repl"
    mgmt_db = _unique_name(f"db_mgmt_converge_{mode}")
    target_db = _unique_name(f"converge_{mode}")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=True,
        use_distributed=use_distributed,
        replicated_cluster=_CLUSTER,
        replicated_path=_REPLICATED_PATH,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migrator.apply_migrations(target_db)

    latest_version = _get_latest_migration_version(_PROD_MIGRATION_DIR)
    assert _get_migration_version(ch_client, mgmt_db, target_db) == latest_version
    assert _partially_applied_version(ch_client, mgmt_db, target_db) is None

    _sync_mutations(ch_client, target_db)
    assert _stuck_mutations(ch_client, target_db) == []

    # In distributed mode the ReplicatedMergeTree data lives in the `_local`
    # twin; the bare name is a Distributed router. Check whichever exists.
    for base in ("calls_complete", "call_parts", "calls_merged"):
        local = f"{base}_local"
        table = local if _table_exists(ch_client, target_db, local) else base
        if _table_exists(ch_client, target_db, table):
            _assert_table_schema_converged(ch_client, target_db, table)


def test_concurrent_inserts_during_migration_converge(ch_client, tmp_path):
    """Writes during a schema change still converge with no partial version.

    Approximates the write-during-DDL class: pre-populate a table, then run an
    ADD COLUMN migration while a background thread inserts, and assert the
    migration lands cleanly on every replica.
    """
    mgmt_db = _unique_name("db_mgmt_concurrent")
    target_db = _unique_name("concurrent")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "001_init.up.sql").write_text(
        "CREATE TABLE events (id String, project_id String) "
        "ENGINE = MergeTree ORDER BY (project_id, id);"
    )
    (migration_dir / "001_init.down.sql").write_text("DROP TABLE IF EXISTS events;")
    (migration_dir / "002_add_col.up.sql").write_text(
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS created_at DateTime64(3) DEFAULT now64();"
    )
    (migration_dir / "002_add_col.down.sql").write_text(
        "ALTER TABLE events DROP COLUMN IF EXISTS created_at;"
    )

    def make_migrator():
        return get_clickhouse_trace_server_migrator(
            ch_client,
            replicated=True,
            use_distributed=False,
            replicated_cluster=_CLUSTER,
            replicated_path=_REPLICATED_PATH,
            management_db=mgmt_db,
            migration_dir=str(migration_dir),
            post_migration_hook=None,
        )

    make_migrator().apply_migrations(target_db, target_version=1)
    ch_client.insert(
        f"{target_db}.events",
        data=[[uuid.uuid4().hex, "p1"] for _ in range(200)],
        column_names=["id", "project_id"],
    )

    stop = threading.Event()
    writer_client = clickhouse_connect.get_client(
        host=ch_client.test_host,
        port=ch_client.test_port,
        autogenerate_session_id=False,
    )

    def writer():
        while not stop.is_set():
            writer_client.command(
                f"INSERT INTO {target_db}.events (id, project_id) "
                f"VALUES ('{uuid.uuid4().hex}', 'p1')"
            )
            time.sleep(0.01)

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    try:
        make_migrator().apply_migrations(target_db, target_version=2)
    finally:
        stop.set()
        thread.join(timeout=30)
        writer_client.close()

    assert not thread.is_alive()
    assert _get_migration_version(ch_client, mgmt_db, target_db) == 2
    assert _partially_applied_version(ch_client, mgmt_db, target_db) is None
    _sync_mutations(ch_client, target_db)
    assert _stuck_mutations(ch_client, target_db) == []
    _assert_table_schema_converged(ch_client, target_db, "events")
