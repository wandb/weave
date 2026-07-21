"""Functional tests for ClickHouse migrator in cloud, replicated, and distributed modes.

Runs actual SQL against a single-node ClickHouse with embedded Keeper.
"""

import os
import re
import uuid

import clickhouse_connect
import pytest

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.clickhouse_trace_server_migrator import (
    _NON_RECOVERABLE_MIGRATION_VERSIONS,
    MigrationError,
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


def _get_latest_migration_version(migration_dir: str) -> int:
    versions = [
        int(file.split("_", 1)[0])
        for file in os.listdir(migration_dir)
        if file.endswith(".up.sql")
    ]
    assert versions, f"No up migrations found in {migration_dir}"
    return max(versions)


def _reset_migration_version(
    ch_client, mgmt_db: str, target_db: str, version: int
) -> None:
    """Rewind the recorded migration version so apply_migrations re-runs the ups.

    Mirrors the migrator's own status write (ALTER ... UPDATE, mutations_sync=2),
    which is synchronous, so the next version read is immediately consistent.
    """
    ch_client.command(
        f"ALTER TABLE {mgmt_db}.migrations "
        f"UPDATE curr_version = {version}, partially_applied_version = NULL "
        f"WHERE db_name = '{target_db}' SETTINGS mutations_sync = 2"
    )


def _set_partial_migration(
    ch_client, mgmt_db: str, target_db: str, curr: int, partial: int
) -> None:
    """Forge a crashed-mid-migration row: curr_version=curr, partial=partial.

    Reproduces the state a pod leaves behind when it dies after _apply_migration
    records partially_applied_version but before it records curr_version.
    """
    ch_client.command(
        f"ALTER TABLE {mgmt_db}.migrations "
        f"UPDATE curr_version = {curr}, partially_applied_version = {partial} "
        f"WHERE db_name = '{target_db}' SETTINGS mutations_sync = 2"
    )


def _get_partial_version(ch_client, mgmt_db: str, target_db: str) -> int | None:
    result = ch_client.query(
        f"SELECT partially_applied_version FROM {mgmt_db}.migrations "
        f"WHERE db_name = '{target_db}'"
    )
    assert len(result.result_rows) == 1, f"Migration status for {target_db} not found"
    return result.result_rows[0][0]


def _table_swap_versions(migration_dir: str) -> list[int]:
    """Versions whose up.sql performs a bare `RENAME TABLE`.

    A table swap is one-shot by nature: the RENAME errors once its target
    exists, and auto-retrying a swap can lose data on a partial-failure
    interleaving (live rows stranded under the backup name). This is why the
    migrator errors on partial application rather than re-running. Such
    migrations are excluded from the idempotency re-run; their forward run is
    covered by test_all_production_migrations_*.
    """
    swaps = []
    for fname in os.listdir(migration_dir):
        if not fname.endswith(".up.sql"):
            continue
        sql = open(os.path.join(migration_dir, fname), encoding="utf-8").read()
        without_comments = re.sub(r"(?m)^\s*--.*$", "", sql)
        if re.search(r"\bRENAME\s+TABLE\b", without_comments, re.IGNORECASE):
            swaps.append(int(fname.split("_", 1)[0]))
    return sorted(swaps)


def _rerunnable_segments(latest: int, excluded: list[int]) -> list[tuple[int, int]]:
    """Contiguous (reset_to, apply_to) ranges of re-runnable migrations.

    Splits 1..latest around the excluded versions. reset_to is the version to
    rewind curr_version to; apply_to is the target_version to migrate up to.
    """
    segments = []
    lo = 1
    for boundary in [*excluded, latest + 1]:
        if boundary - 1 >= lo:
            segments.append((lo - 1, boundary - 1))
        lo = boundary + 1
    return segments


def _schema_snapshot(ch_client, db_name: str) -> tuple[list, list]:
    """Table engines and (table, column, type) triples for a database.

    Comparing this before and after a re-run upgrades the idempotency check from
    'no error' to 'schema unchanged', so an IF NOT EXISTS guard that silently
    skips a needed change (or a re-run that alters something) is caught rather
    than masked. Column type/existence is the drift IF NOT EXISTS can hide;
    view query text is intentionally not compared (the re-run reverts and
    restores it across segments).
    """
    tables = ch_client.query(
        f"SELECT name, engine FROM system.tables WHERE database = '{db_name}' ORDER BY name"
    ).result_rows
    columns = ch_client.query(
        f"SELECT table, name, type FROM system.columns WHERE database = '{db_name}' "
        "ORDER BY table, name"
    ).result_rows
    return [tuple(r) for r in tables], [tuple(r) for r in columns]


def _row_count_snapshot(ch_client, db_name: str) -> dict[str, int]:
    """Row counts for every MergeTree-family table in a database.

    Comparing this before and after a re-run upgrades the idempotency check from
    schema-only to data too, so a seed that duplicates rows on re-run (like 006) is
    caught unless its version is excluded from the re-run via
    _NON_RECOVERABLE_MIGRATION_VERSIONS. Views and Distributed tables have no
    independent storage and are skipped.
    """
    tables = ch_client.query(
        f"SELECT name FROM system.tables WHERE database = '{db_name}' "
        "AND engine LIKE '%MergeTree%' ORDER BY name"
    ).result_rows
    return {
        name: ch_client.query(f"SELECT count() FROM {db_name}.{name}").result_rows[0][0]
        for (name,) in tables
    }


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


def test_intent_records_schema_and_replacement_lifecycle(ch_client):
    """Intent records retain pipeline history while replacing row versions."""
    mgmt_db = _unique_name("db_mgmt_intents")
    target_db = _unique_name("intents")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=False,
        use_distributed=False,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
        post_migration_hook=None,
    )
    migrator.apply_migrations(target_db)

    table_metadata = ch_client.query(
        "SELECT engine, partition_key, sorting_key, primary_key, "
        "extract(create_table_query, 'TTL (.+) SETTINGS') "
        "FROM system.tables "
        f"WHERE database = '{target_db}' AND name = 'intent_records'"
    ).result_rows
    assert table_metadata == [
        (
            "ReplacingMergeTree",
            "toYYYYMM(event_time)",
            "project_id, event_time, pipeline_version, id",
            "project_id, event_time",
            "expire_at",
        )
    ]

    columns = ch_client.query(
        "SELECT name, type FROM system.columns "
        f"WHERE database = '{target_db}' AND table = 'intent_records' "
        "ORDER BY position"
    ).result_rows
    assert columns == [
        ("project_id", "String"),
        ("id", "String"),
        ("pipeline_version", "UInt32"),
        ("record_version", "UInt64"),
        ("deleted", "Bool"),
        ("space", "Enum8('intent' = 1, 'failure' = 2)"),
        ("category", "LowCardinality(String)"),
        ("status", "LowCardinality(String)"),
        ("signature", "String"),
        ("normalized_signature", "String"),
        ("signature_id", "FixedString(16)"),
        ("embedding_model", "LowCardinality(String)"),
        ("embedding_dimensions", "UInt16"),
        ("vector", "Array(Float32)"),
        ("source", "LowCardinality(String)"),
        ("source_id", "String"),
        ("trace_id", "String"),
        ("span_id", "String"),
        ("parent_span_id", "String"),
        ("conversation_id", "String"),
        ("turn_id", "String"),
        ("intent_ordinal", "UInt16"),
        ("role", "LowCardinality(String)"),
        ("user_id", "String"),
        ("event_time", "DateTime64(6, 'UTC')"),
        ("inserted_at", "DateTime64(3, 'UTC')"),
        ("inserted_by_user_id", "String"),
        ("expire_at", "DateTime"),
        ("attributes", "Map(String, String)"),
    ]

    indexes = ch_client.query(
        "SELECT name, expr, type_full, granularity "
        "FROM system.data_skipping_indices "
        f"WHERE database = '{target_db}' AND table = 'intent_records' "
        "ORDER BY name"
    ).result_rows
    assert indexes == [
        ("idx_conversation_id", "conversation_id", "bloom_filter(0.01)", 1),
        ("idx_id", "id", "bloom_filter(0.01)", 1),
        ("idx_signature_id", "signature_id", "bloom_filter(0.01)", 1),
        ("idx_span_id", "span_id", "bloom_filter(0.01)", 1),
        ("idx_trace_id", "trace_id", "bloom_filter(0.01)", 1),
        (
            "idx_vector",
            "vector",
            "vector_similarity('hnsw', 'cosineDistance', 1024, 'bf16', 64, 512)",
            1,
        ),
    ]

    insert_columns = """
        project_id, id, pipeline_version, record_version, deleted, space,
        category, status, signature, normalized_signature, signature_id,
        embedding_model, vector, source, source_id, trace_id, span_id,
        parent_span_id, conversation_id, turn_id, intent_ordinal, role,
        user_id, event_time, inserted_by_user_id, attributes
    """
    row_template = """
        SELECT
            'project-1', 'intent-1', {pipeline_version}, {record_version}, false,
            'intent', '{category}', 'active', 'Add Stripe checkout',
            'add stripe checkout', unhex('00112233445566778899aabbccddeeff'),
            'text-embedding-3-large', arrayResize([toFloat32(1)], 1024, toFloat32(0)),
            'weave', 'source-1', 'trace-1', 'span-1', 'parent-1',
            'conversation-1', 'turn-1', 0, 'user', 'user-1',
            toDateTime64('2026-06-20 14:32:00', 6, 'UTC'), 'wandb-user-1',
            map('environment', 'test')
    """
    for pipeline_version, record_version, category in [
        (1, 1, "action_request"),
        (1, 2, "payments"),
        (2, 1, "action_request"),
    ]:
        ch_client.command(
            f"INSERT INTO {target_db}.intent_records ({insert_columns}) "
            + row_template.format(
                pipeline_version=pipeline_version,
                record_version=record_version,
                category=category,
            )
        )

    current_rows = ch_client.query(
        "SELECT pipeline_version, record_version, category, deleted, "
        "formatDateTime(expire_at, '%F %T'), length(vector), attributes "
        f"FROM {target_db}.intent_records FINAL "
        "WHERE project_id = 'project-1' ORDER BY pipeline_version"
    ).result_rows
    assert current_rows == [
        (1, 2, "payments", False, "2100-01-01 00:00:00", 1024, {"environment": "test"}),
        (
            2,
            1,
            "action_request",
            False,
            "2100-01-01 00:00:00",
            1024,
            {"environment": "test"},
        ),
    ]

    ch_client.command(
        f"INSERT INTO {target_db}.intent_records "
        "SELECT * REPLACE(3 AS record_version, true AS deleted, now64(3) AS inserted_at) "
        f"FROM {target_db}.intent_records FINAL "
        "WHERE project_id = 'project-1' AND pipeline_version = 1"
    )
    active_rows = ch_client.query(
        "SELECT pipeline_version, id "
        f"FROM {target_db}.intent_records FINAL "
        "WHERE project_id = 'project-1' AND deleted = false "
        "ORDER BY pipeline_version"
    ).result_rows
    assert active_rows == [(2, "intent-1")]

    active_partitions = ch_client.query(
        "SELECT DISTINCT partition "
        "FROM system.parts "
        f"WHERE database = '{target_db}' AND table = 'intent_records' AND active "
        "ORDER BY partition"
    ).result_rows
    assert active_partitions == [("202606",)]


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


def test_migration_client_timeout_outlasts_replicated_ddl(ch_keeper_server):
    """A client minted with the production migration timeout runs a full
    replicated migration and carries the incident-fixing HTTP read timeout.
    """
    host, port = ch_keeper_server
    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        autogenerate_session_id=False,
        send_receive_timeout=ch_settings.MIGRATION_CLIENT_SEND_RECEIVE_TIMEOUT_SEC,
    )
    assert client.timeout.read_timeout == (
        ch_settings.MIGRATION_CLIENT_SEND_RECEIVE_TIMEOUT_SEC
    )

    mgmt_db = _unique_name("db_mgmt_timeout")
    target_db = _unique_name("timeout_repl")
    try:
        migrator = get_clickhouse_trace_server_migrator(
            client,
            replicated=True,
            use_distributed=False,
            replicated_cluster=_CLUSTER,
            replicated_path=_REPLICATED_PATH,
            management_db=mgmt_db,
            migration_dir=_PROD_MIGRATION_DIR,
            post_migration_hook=None,
        )
        latest_version = _get_latest_migration_version(_PROD_MIGRATION_DIR)
        migrator.apply_migrations(target_db)
        assert _get_migration_version(client, mgmt_db, target_db) == latest_version
    finally:
        for db in (target_db, mgmt_db):
            client.command(f"DROP DATABASE IF EXISTS {db}")
        client.close()


@pytest.mark.parametrize(
    ("case_name", "replicated", "use_distributed"),
    [
        pytest.param("cloud", False, False, id="cloud"),
        pytest.param("replicated", True, False, id="replicated"),
        pytest.param("distributed", True, True, id="distributed"),
    ],
)
def test_production_migrations_are_idempotent(
    ch_client, case_name: str, replicated: bool, use_distributed: bool
):
    """Re-running the migration stack on an already-migrated DB is a safe no-op.

    Partial-failure recovery re-runs a migration after the operator clears the
    partial flag, so every migration's statements must tolerate re-execution.
    This applies all migrations, then rewinds the recorded version and
    re-applies the ups through each shape's SQL rewriter. Table-swap migrations
    (see _table_swap_versions) are one-shot and excluded from the re-run; the
    006 seed re-inserts without erroring.
    """
    mgmt_db = _unique_name(f"db_mgmt_idem_{case_name}")
    target_db = _unique_name(f"idem_{case_name}")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    kwargs = {
        "replicated": replicated,
        "use_distributed": use_distributed,
        "management_db": mgmt_db,
        "migration_dir": _PROD_MIGRATION_DIR,
        "post_migration_hook": None,
    }
    if replicated:
        kwargs["replicated_cluster"] = _CLUSTER
        kwargs["replicated_path"] = _REPLICATED_PATH
    migrator = get_clickhouse_trace_server_migrator(ch_client, **kwargs)

    latest = _get_latest_migration_version(_PROD_MIGRATION_DIR)
    migrator.apply_migrations(target_db)
    assert _get_migration_version(ch_client, mgmt_db, target_db) == latest

    # 024 is the only table-swap; a new one must be a deliberate decision, not a
    # silent addition, so pin the set. See _table_swap_versions for why swaps
    # are one-shot.
    swaps = _table_swap_versions(_PROD_MIGRATION_DIR)
    assert swaps == [24], (
        f"unexpected table-swap migration(s) {swaps}; a RENAME TABLE is one-shot, "
        "so reassess idempotency and update this assertion deliberately"
    )
    # A structural swap is not re-runnable, so the recovery denylist must contain
    # every one. This ties the SQL scan to the production denylist so the two can't
    # drift; the row-count check below covers the seeds the scan can't detect.
    assert set(swaps) <= _NON_RECOVERABLE_MIGRATION_VERSIONS, (
        f"table-swap migration(s) {swaps} are missing from "
        "_NON_RECOVERABLE_MIGRATION_VERSIONS"
    )

    # Re-apply every re-runnable migration by rewinding the recorded version and
    # migrating back up through each contiguous segment around the excluded (one-
    # shot) versions. Excluding exactly the production denylist means the re-run
    # covers precisely the migrations recovery would re-run in prod. Schema and row
    # counts must both be unchanged, so a guard that silently skips a needed change,
    # or a non-idempotent seed that isn't denylisted, is caught rather than masked.
    excluded = sorted(_NON_RECOVERABLE_MIGRATION_VERSIONS)
    before = _schema_snapshot(ch_client, target_db)
    before_counts = _row_count_snapshot(ch_client, target_db)
    for reset_to, apply_to in _rerunnable_segments(latest, excluded):
        _reset_migration_version(ch_client, mgmt_db, target_db, reset_to)
        migrator.apply_migrations(target_db, target_version=apply_to)

    assert _get_migration_version(ch_client, mgmt_db, target_db) == latest
    assert _schema_snapshot(ch_client, target_db) == before, (
        "re-running migrations changed the table/column schema"
    )
    assert _row_count_snapshot(ch_client, target_db) == before_counts, (
        "re-running migrations changed row counts; a non-idempotent seed is not in "
        "_NON_RECOVERABLE_MIGRATION_VERSIONS"
    )


@pytest.mark.parametrize(
    ("case_name", "replicated", "use_distributed"),
    [
        pytest.param("cloud", False, False, id="cloud"),
        pytest.param("replicated", True, False, id="replicated"),
        pytest.param("distributed", True, True, id="distributed"),
    ],
)
def test_partial_migration_auto_recovers(
    ch_client, case_name: str, replicated: bool, use_distributed: bool
):
    """A crash mid-migration self-heals on the next startup instead of crash-looping.

    _apply_migration records partially_applied_version before running the DDL and
    clears it after, so a crash in between leaves the flag set. Recovery re-runs
    that idempotent migration and converges to latest (the incident hard-raised
    here and crash-looped for 44h). A one-shot migration (024 table swap) is never
    auto-recovered: it raises for manual repair with the flag left intact.
    """
    mgmt_db = _unique_name(f"db_mgmt_recover_{case_name}")
    target_db = _unique_name(f"recover_{case_name}")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    kwargs = {
        "replicated": replicated,
        "use_distributed": use_distributed,
        "management_db": mgmt_db,
        "migration_dir": _PROD_MIGRATION_DIR,
        "post_migration_hook": None,
    }
    if replicated:
        kwargs["replicated_cluster"] = _CLUSTER
        kwargs["replicated_path"] = _REPLICATED_PATH
    migrator = get_clickhouse_trace_server_migrator(ch_client, **kwargs)

    latest = _get_latest_migration_version(_PROD_MIGRATION_DIR)
    swaps = _table_swap_versions(_PROD_MIGRATION_DIR)
    recoverable = latest not in swaps and latest != 6
    assert recoverable, (
        f"test assumes migration {latest} is re-runnable; it is one-shot, so forge "
        "the partial state on a recoverable version instead"
    )

    migrator.apply_migrations(target_db)
    clean_schema = _schema_snapshot(ch_client, target_db)

    # Happy path: forge a crash mid-`latest`, then recover to a clean converge.
    _set_partial_migration(ch_client, mgmt_db, target_db, latest - 1, latest)
    migrator.apply_migrations(target_db)
    assert _get_migration_version(ch_client, mgmt_db, target_db) == latest
    assert _get_partial_version(ch_client, mgmt_db, target_db) is None
    assert _schema_snapshot(ch_client, target_db) == clean_schema, (
        "auto-recovery changed the schema; the re-run was not a no-op"
    )

    # Denylist: a one-shot swap is refused and the flag survives for manual repair.
    swap = swaps[0]
    _set_partial_migration(ch_client, mgmt_db, target_db, swap - 1, swap)
    with pytest.raises(MigrationError, match="cannot be auto-recovered"):
        migrator.apply_migrations(target_db)
    assert _get_partial_version(ch_client, mgmt_db, target_db) == swap
    assert _get_migration_version(ch_client, mgmt_db, target_db) == swap - 1


@pytest.mark.parametrize(
    ("case_name", "replicated", "use_distributed"),
    [
        pytest.param("cloud", False, False, id="cloud"),
        pytest.param("replicated", True, False, id="replicated"),
    ],
)
def test_migrations_refuse_populated_db_without_history(
    ch_client, case_name: str, replicated: bool, use_distributed: bool
):
    """Refuse to migrate a populated data DB whose migration history is absent.

    Simulates a diverged management DB (e.g. a renamed management_db): the data
    DB already has tables, but a fresh management DB has no row for it. Without
    this guard the IF [NOT] EXISTS migrations would silently re-run from version
    0 against tables of unknown schema.
    """

    def make_migrator(mgmt_db: str):
        kwargs = {
            "replicated": replicated,
            "use_distributed": use_distributed,
            "management_db": mgmt_db,
            "migration_dir": _PROD_MIGRATION_DIR,
            "post_migration_hook": None,
        }
        if replicated:
            kwargs["replicated_cluster"] = _CLUSTER
            kwargs["replicated_path"] = _REPLICATED_PATH
        return get_clickhouse_trace_server_migrator(ch_client, **kwargs)

    target_db = _unique_name(f"orphan_{case_name}")
    mgmt_a = _unique_name(f"db_mgmt_orphan_a_{case_name}")
    mgmt_b = _unique_name(f"db_mgmt_orphan_b_{case_name}")
    for db in (target_db, mgmt_a, mgmt_b):
        ch_client.track_db(db)

    make_migrator(mgmt_a).apply_migrations(target_db)
    latest = _get_latest_migration_version(_PROD_MIGRATION_DIR)
    assert _get_migration_version(ch_client, mgmt_a, target_db) == latest

    # A fresh management DB has no history for the already-populated data DB.
    with pytest.raises(MigrationError, match="no history"):
        make_migrator(mgmt_b).apply_migrations(target_db)

    # The guard refused before touching anything: the real history is intact and
    # no version-0 row was seeded into the fresh management DB.
    assert _get_migration_version(ch_client, mgmt_a, target_db) == latest
    orphan_rows = ch_client.query(
        f"SELECT count() FROM {mgmt_b}.migrations WHERE db_name = '{target_db}'"
    ).result_rows[0][0]
    assert orphan_rows == 0
