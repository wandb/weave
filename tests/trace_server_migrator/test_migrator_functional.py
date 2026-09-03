"""Functional tests for ClickHouse migrator in cloud, replicated, and distributed modes.

Runs actual SQL against a single-node ClickHouse with embedded Keeper.
"""

import os
import re
import uuid

import clickhouse_connect
import pytest
from clickhouse_connect.driver.exceptions import DatabaseError

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.clickhouse_trace_server_migrator import (
    _NON_RECOVERABLE_MIGRATION_VERSIONS,
    MigrationError,
    get_clickhouse_trace_server_migrator,
)
from weave.trace_server.costs.insert_costs import (
    COSTS_TABLE,
    costs_schema_is_ready,
    get_current_costs,
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


@pytest.mark.parametrize(
    "use_distributed", [False, True], ids=["replicated", "distributed"]
)
def test_all_production_migrations_round_trip(ch_client, use_distributed: bool):
    """Every production migration applies cleanly, then reverses cleanly.

    Up and down live in one test because a completed up is the only valid
    starting point for a down. Running them as separate tests replayed the same
    full migration set twice per mode, and each statement carries a fixed
    round-trip cost against Keeper.
    """
    suffix = "dist" if use_distributed else "repl"
    mgmt_db = _unique_name(f"db_mgmt_prod_{suffix}")
    target_db = _unique_name(f"prod_{suffix}")
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

    assert _get_db_engine(ch_client, mgmt_db) == "Atomic"
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
    if use_distributed:
        # Distributed mode uses ON CLUSTER to fan DBs to every shard/replica.
        # If the fan-out is broken, peer replicas never receive the management
        # DB either.
        _assert_db_on_every_replica(ch_client, mgmt_db, expected_engine="Atomic")

    # Migrate all the way back down
    migrator.apply_migrations(target_db, target_version=0)


_INTENT_COLUMNS = [
    ("project_id", "String"),
    ("id", "UUID"),
    ("config_sha", "LowCardinality(String)"),
    ("signature", "String"),
    ("category", "String"),
    ("language", "LowCardinality(String)"),
    ("sentiment", "LowCardinality(String)"),
    ("sentiment_rationale", "String"),
    ("vector", "Array(Float32)"),
    ("conversation_id", "String"),
    ("trace_id", "String"),
    ("span_id", "String"),
    ("user_id", "String"),
    ("agent_name", "String"),
    ("turn_duration_ms", "UInt32"),
    ("turn_cost_usd", "Float64"),
    ("turn_input_tokens", "UInt64"),
    ("turn_output_tokens", "UInt64"),
    ("turn_reasoning_tokens", "UInt64"),
    ("turn_cache_creation_input_tokens", "UInt64"),
    ("turn_cache_read_input_tokens", "UInt64"),
    ("turn_signature_count", "UInt16"),
    ("trace_started_at", "DateTime64(6, 'UTC')"),
    ("trace_ended_at", "DateTime64(6, 'UTC')"),
    ("extracted_at", "DateTime64(6, 'UTC')"),
    ("inserted_at", "DateTime64(6, 'UTC')"),
    ("expire_at", "DateTime"),
]

_FAILURE_COLUMNS = [
    ("project_id", "String"),
    ("id", "UUID"),
    ("config_sha", "LowCardinality(String)"),
    ("signature", "String"),
    ("failure_reason", "String"),
    ("category", "String"),
    ("severity", "LowCardinality(String)"),
    ("vector", "Array(Float32)"),
    ("conversation_id", "String"),
    ("current_trace_id", "String"),
    ("span_id", "String"),
    ("affected_trace_ids", "Array(String)"),
    ("evidence_span_ids", "Array(String)"),
    ("user_id", "String"),
    ("agent_name", "String"),
    ("turn_duration_ms", "UInt32"),
    ("turn_cost_usd", "Float64"),
    ("turn_input_tokens", "UInt64"),
    ("turn_output_tokens", "UInt64"),
    ("turn_reasoning_tokens", "UInt64"),
    ("turn_cache_creation_input_tokens", "UInt64"),
    ("turn_cache_read_input_tokens", "UInt64"),
    ("turn_signature_count", "UInt16"),
    ("trace_started_at", "DateTime64(6, 'UTC')"),
    ("trace_ended_at", "DateTime64(6, 'UTC')"),
    ("extracted_at", "DateTime64(6, 'UTC')"),
    ("inserted_at", "DateTime64(6, 'UTC')"),
    ("expire_at", "DateTime"),
]

# The column lists below are deliberately spelled out twice rather than composed
# from a shared block: the assert is ORDER BY position, and shared columns
# interleave with grain-specific ones differently in each table. Growing this
# count is a decision, not a side effect.
_EXPECTED_SHARED_COLUMNS = 23

_SIGNATURE_TABLES = [
    (
        "intent_signatures",
        _INTENT_COLUMNS,
        [
            ("idx_conversation_id", "conversation_id"),
            ("idx_trace_id", "trace_id"),
        ],
    ),
    (
        "failure_signatures",
        _FAILURE_COLUMNS,
        [
            ("idx_affected_trace_ids", "affected_trace_ids"),
            ("idx_conversation_id", "conversation_id"),
            ("idx_current_trace_id", "current_trace_id"),
        ],
    ),
]


def _migrate_signatures_db(ch_client, name: str) -> str:
    """Apply production migrations to a fresh db and return its name."""
    mgmt_db = _unique_name(f"db_mgmt_{name}")
    target_db = _unique_name(name)
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
    return target_db


# Source month is a month before extraction, so a partition that followed
# extraction time would file the row under the wrong month.
_TRACE_STARTED_AT = "toDateTime64('2026-05-30 09:15:00', 6, 'UTC')"
_TRACE_ENDED_AT = "toDateTime64('2026-05-30 09:16:00', 6, 'UTC')"
_SPAN_ID = "span-7"
_EXTRACTED_AT = "toDateTime64('2026-06-20 14:32:00', 6, 'UTC')"
_UNIT_VECTOR = "arrayResize([toFloat32(1)], 1024, toFloat32(0))"

# Every value distinct, so a pair transposed on the way in fails the assert. Written
# in schema order, which is what lets one dict drive both the insert and the read.
_TURN_TOKENS = {
    "turn_input_tokens": 12000,
    "turn_output_tokens": 800,
    "turn_reasoning_tokens": 320,
    "turn_cache_creation_input_tokens": 4096,
    "turn_cache_read_input_tokens": 65536,
}
_TOKEN_COLUMNS = ", ".join(_TURN_TOKENS)
_TOKEN_VALUES = ", ".join(str(count) for count in _TURN_TOKENS.values())

# The sorting key, and therefore the dedup key: a read that collapses a retry
# groups by all three terms, because no read here uses FINAL.
_SIGNATURE_KEY = "project_id, toDate(trace_started_at), id"

# Writer-minted uuidv7 values. Reused verbatim to stand for a retry of the same
# row, which is the only thing ReplacingMergeTree collapses here.
_INTENT_ID = "019ff277-bba3-7232-aeb3-0632fd183e1e"
_FAILURE_ID_1 = "019ff277-bba3-7232-aeb3-0632fd183e2f"
_FAILURE_ID_2 = "019ff288-c1d4-7333-bfc4-1743fe294f3a"
_CLUSTER_ID = "019ff4bc-2ae1-744d-ae3a-285998a9051a"
# Stable across runs, unlike `_CLUSTER_ID`, which a run re-mints.
_TOPIC_ID = "019ff4bc-2ae1-744d-ae3a-285998a9051b"
_NIL_UUID = "00000000-0000-0000-0000-000000000000"


def _insert_intent(ch_client, target_db: str, category: str, cost: float) -> None:
    """Insert one intent_signatures row for _INTENT_ID in 'project-1'."""
    ch_client.command(
        f"INSERT INTO {target_db}.intent_signatures "
        "(project_id, id, config_sha, signature, category, language, "
        "sentiment, vector, conversation_id, trace_id, span_id, user_id, agent_name, "
        f"turn_duration_ms, turn_cost_usd, {_TOKEN_COLUMNS}, "
        "trace_started_at, trace_ended_at, extracted_at) VALUES "
        f"('project-1', '{_INTENT_ID}', 'cfg-a', 'add stripe checkout', "
        f"'{category}', 'es', 'frustrated', {_UNIT_VECTOR}, "
        f"'conversation-1', 'trace-4', '{_SPAN_ID}', 'user-1', 'checkout-agent', "
        f"9000, {cost}, {_TOKEN_VALUES}, "
        f"{_TRACE_STARTED_AT}, {_TRACE_ENDED_AT}, {_EXTRACTED_AT})"
    )


def _insert_failure(
    ch_client, target_db: str, row_id: str, current: str, affected: str, cost: float
) -> None:
    """Insert one failure_signatures row in 'project-1'."""
    ch_client.command(
        f"INSERT INTO {target_db}.failure_signatures "
        "(project_id, id, config_sha, signature, failure_reason, category, "
        "severity, vector, conversation_id, current_trace_id, span_id, "
        f"affected_trace_ids, user_id, agent_name, turn_duration_ms, turn_cost_usd, "
        f"{_TOKEN_COLUMNS}, trace_started_at, trace_ended_at, extracted_at) VALUES "
        f"('project-1', '{row_id}', 'cfg-a', "
        "'ignored the stated output path', 'The user specified /tmp/out.json.', "
        f"'requirement_violation', 'major', {_UNIT_VECTOR}, 'conversation-1', "
        f"'{current}', '{_SPAN_ID}', {affected}, 'user-1', 'checkout-agent', "
        f"16000, {cost}, {_TOKEN_VALUES}, "
        f"{_TRACE_STARTED_AT}, {_TRACE_ENDED_AT}, {_EXTRACTED_AT})"
    )


def test_signature_tables_schema(ch_client):
    """Both signature tables pin their key and engine, and neither carries a constraint.

    Engine, PARTITION BY and ORDER BY are the one-way doors: none can be altered
    on a populated table. Both tables come from one migration, so they share the
    one migrated database rather than paying for a chain each.
    """
    target_db = _migrate_signatures_db(ch_client, "signatures")

    for table_name, expected_columns, expected_indexes in _SIGNATURE_TABLES:
        assert ch_client.query(
            "SELECT engine, partition_key, sorting_key, primary_key, "
            "extract(create_table_query, 'TTL (.+) SETTINGS') "
            f"FROM system.tables WHERE database = '{target_db}' "
            f"AND name = '{table_name}'"
        ).result_rows == [
            (
                "ReplacingMergeTree",
                "toYYYYMM(trace_started_at)",
                _SIGNATURE_KEY,
                _SIGNATURE_KEY,
                "expire_at",
            )
        ]

        # Pins the column list, which is also what rules out an Enum: the writer
        # gates the vocabulary, because an insert is batched at 256 rows and one
        # bad candidate must not reject 255 good ones.
        assert (
            ch_client.query(
                "SELECT name, type FROM system.columns "
                f"WHERE database = '{target_db}' AND table = '{table_name}' "
                "ORDER BY position"
            ).result_rows
            == expected_columns
        )

        # A CONSTRAINT is the same 256-row problem and shows up nowhere else.
        assert (
            "CONSTRAINT"
            not in ch_client.query(
                "SELECT create_table_query FROM system.tables "
                f"WHERE database = '{target_db}' AND name = '{table_name}'"
            ).result_rows[0][0]
        )

        # Bloom filters only. No ANN index: measured on this schema, HNSW cost
        # 126-196x on inserts.
        assert (
            ch_client.query(
                "SELECT name, expr FROM system.data_skipping_indices "
                f"WHERE database = '{target_db}' AND table = '{table_name}' "
                "ORDER BY name"
            ).result_rows
            == expected_indexes
        )

        # inserted_at is only DEFAULTed so a writer can override it (e.g. for a
        # backfill), and id is only DEFAULTed so a row cannot land without the
        # one the writer minted.
        assert ch_client.query(
            "SELECT name, default_kind, default_expression FROM system.columns "
            f"WHERE database = '{target_db}' AND table = '{table_name}' "
            "AND name IN ('id', 'inserted_at') ORDER BY name"
        ).result_rows == [
            ("id", "DEFAULT", "generateUUIDv7()"),
            ("inserted_at", "DEFAULT", "now64(6)"),
        ]


def test_signature_tables_share_column_types():
    """A column in both tables must mean the same thing in both.

    Splitting intents from failures buys grain-correct schemas and costs schema
    drift. A type that diverges makes one query silently mean two things, so it
    is caught here against the pinned column lists, before ClickHouse is asked.
    """
    intent, failure = dict(_INTENT_COLUMNS), dict(_FAILURE_COLUMNS)
    shared = intent.keys() & failure.keys()

    assert len(shared) == _EXPECTED_SHARED_COLUMNS
    assert {name: intent[name] for name in shared} == {
        name: failure[name] for name in shared
    }


def test_signature_retry_collapses_on_read(ch_client):
    """A retry of the same row id replaces its predecessor under GROUP BY + argMax.

    Spelled the way the reader has to spell it: this path never uses FINAL, so the
    collapse must fall out of the sorting key.
    """
    target_db = _migrate_signatures_db(ch_client, "lifecycle")

    # Separate inserts, because now64() is evaluated once per block: two rows
    # sharing an id inside one block would tie on the version.
    _insert_intent(ch_client, target_db, "action_request", 0.21)
    _insert_intent(ch_client, target_db, "information_request", 0.34)

    # Distinct blocks form distinct parts, so both versions are still on disk
    # here and the single row below is this query's work, not a merge's.
    assert ch_client.query(
        "SELECT argMax(category, inserted_at), argMax(turn_cost_usd, inserted_at), "
        "argMax(turn_duration_ms, inserted_at), argMax(language, inserted_at), "
        "formatDateTime(argMax(expire_at, inserted_at), '%F %T'), "
        "length(argMax(vector, inserted_at)) "
        f"FROM {target_db}.intent_signatures WHERE project_id = 'project-1' "
        f"GROUP BY {_SIGNATURE_KEY}"
    ).result_rows == [
        ("information_request", 0.34, 9000, "es", "2100-01-01 00:00:00", 1024)
    ]

    # Source month, not extraction month, and one term: retention follows user
    # activity and no pipeline metadata is baked into the partition.
    assert ch_client.query(
        "SELECT DISTINCT partition FROM system.parts "
        f"WHERE database = '{target_db}' AND table = 'intent_signatures' AND active"
    ).result_rows == [("202605",)]

    _insert_failure(ch_client, target_db, _FAILURE_ID_1, "trace-4", "['trace-4']", 0.31)
    # The writer retrying the same id with a wider attributed span: affected_trace_ids is not
    # part of the identity, so the later attempt replaces rather than coexists.
    _insert_failure(
        ch_client, target_db, _FAILURE_ID_1, "trace-4", "['trace-4', 'trace-6']", 0.41
    )

    assert ch_client.query(
        "SELECT toString(id), argMax(current_trace_id, inserted_at), "
        "argMax(affected_trace_ids, inserted_at), argMax(turn_cost_usd, inserted_at) "
        f"FROM {target_db}.failure_signatures WHERE project_id = 'project-1' "
        f"GROUP BY {_SIGNATURE_KEY}"
    ).result_rows == [(_FAILURE_ID_1, "trace-4", ["trace-4", "trace-6"], 0.41)]


def test_failure_turn_attribution(ch_client):
    """A failure attributes many turns, and its per-row totals do not sum.

    Two distinct occurrences, so nothing collapses and these reads need no dedup;
    replacement is covered by test_signature_retry_collapses_on_read.
    """
    target_db = _migrate_signatures_db(ch_client, "attribution")

    _insert_failure(
        ch_client,
        target_db,
        _FAILURE_ID_1,
        "trace-4",
        "['trace-4', 'trace-6', 'trace-9']",
        0.41,
    )
    # A different causing turn is a different failure, sharing turn trace-6.
    _insert_failure(ch_client, target_db, _FAILURE_ID_2, "trace-6", "['trace-6']", 0.32)

    # The drilldown from a turn to the failures touching it. trace-6 is a member of
    # both, and of the first only through affected_trace_ids, not as its causing turn.
    assert ch_client.query(
        f"SELECT toString(id) FROM {target_db}.failure_signatures "
        "WHERE project_id = 'project-1' AND has(affected_trace_ids, 'trace-6') "
        "ORDER BY toString(id)"
    ).result_rows == [(_FAILURE_ID_1,), (_FAILURE_ID_2,)]

    # turn_cost_usd and turn_duration_ms are per-row, not additive: the two failures
    # overlap on trace-6, so summing them counts that turn twice. Three distinct
    # turns are attributed, and the naive sum is over four memberships.
    assert ch_client.query(
        "SELECT sum(turn_cost_usd), length(arrayDistinct(arrayFlatten(groupArray(affected_trace_ids)))) "
        f"FROM {target_db}.failure_signatures WHERE project_id = 'project-1'"
    ).result_rows == [(0.73, 3)]

    # The writer gate the database deliberately does not enforce. This assertion
    # query is the off-path mitigation, and it must find nothing.
    assert ch_client.query(
        f"SELECT count() FROM {target_db}.failure_signatures "
        "WHERE project_id = 'project-1' "
        "AND (empty(affected_trace_ids) OR NOT has(affected_trace_ids, current_trace_id))"
    ).result_rows == [(0,)]


def test_signature_cluster_tables_schema_and_retry(ch_client):
    """Cluster storage follows signature-row identity and collapses writer retries."""
    target_db = _migrate_signatures_db(ch_client, "signature_clusters")

    expected_tables = {
        "signature_cluster_assignments": (
            "project_id, cluster_run_id, toStartOfHour(trace_started_at), "
            "signature_record_id",
            "toYYYYMM(trace_started_at)",
            [
                ("project_id", "String"),
                ("cluster_run_id", "UUID"),
                ("signature_record_id", "UUID"),
                ("cluster_id", "UUID"),
                ("signature_type", "Enum8('intent' = 1, 'failure' = 2)"),
                ("category", "LowCardinality(String)"),
                ("cluster_distance", "Float32"),
                ("cluster_probability", "Float32"),
                ("umap_x", "Float32"),
                ("umap_y", "Float32"),
                ("trace_id", "String"),
                ("span_id", "String"),
                ("conversation_id", "String"),
                ("user_id", "String"),
                ("agent_name", "String"),
                ("trace_started_at", "DateTime64(6, 'UTC')"),
                ("trace_ended_at", "DateTime64(6, 'UTC')"),
                ("turn_duration_ms", "UInt32"),
                ("turn_cost_usd", "Float64"),
                ("turn_input_tokens", "UInt64"),
                ("turn_output_tokens", "UInt64"),
                ("turn_reasoning_tokens", "UInt64"),
                ("turn_cache_creation_input_tokens", "UInt64"),
                ("turn_cache_read_input_tokens", "UInt64"),
                ("turn_signature_count", "UInt16"),
                ("inserted_at", "DateTime64(6, 'UTC')"),
                ("expire_at", "DateTime"),
            ],
        ),
        "signature_cluster_assignments_by_conversation": (
            "project_id, conversation_id, cluster_run_id, signature_record_id",
            "toYYYYMM(trace_started_at)",
            [
                ("project_id", "String"),
                ("conversation_id", "String"),
                ("cluster_run_id", "UUID"),
                ("signature_record_id", "UUID"),
                ("cluster_id", "UUID"),
                ("signature_type", "Enum8('intent' = 1, 'failure' = 2)"),
                ("category", "LowCardinality(String)"),
                ("cluster_distance", "Float32"),
                ("cluster_probability", "Float32"),
                ("umap_x", "Float32"),
                ("umap_y", "Float32"),
                ("trace_id", "String"),
                ("span_id", "String"),
                ("user_id", "String"),
                ("agent_name", "String"),
                ("trace_started_at", "DateTime64(6, 'UTC')"),
                ("trace_ended_at", "DateTime64(6, 'UTC')"),
                ("turn_duration_ms", "UInt32"),
                ("turn_cost_usd", "Float64"),
                ("turn_input_tokens", "UInt64"),
                ("turn_output_tokens", "UInt64"),
                ("turn_reasoning_tokens", "UInt64"),
                ("turn_cache_creation_input_tokens", "UInt64"),
                ("turn_cache_read_input_tokens", "UInt64"),
                ("turn_signature_count", "UInt16"),
                ("inserted_at", "DateTime64(6, 'UTC')"),
                ("expire_at", "DateTime"),
            ],
        ),
        "signature_cluster_runs": (
            "project_id, signature_type, window_end, id",
            "",
            [
                ("project_id", "String"),
                ("id", "UUID"),
                ("signature_type", "Enum8('intent' = 1, 'failure' = 2)"),
                ("signature_config_sha", "LowCardinality(String)"),
                ("cluster_config_sha", "LowCardinality(String)"),
                ("naming_config_sha", "LowCardinality(String)"),
                ("window_start", "DateTime64(6, 'UTC')"),
                ("window_end", "DateTime64(6, 'UTC')"),
                (
                    "status",
                    "Enum8('pending' = 1, 'running' = 2, 'succeeded' = 3, "
                    "'failed' = 4, 'canceled' = 5)",
                ),
                ("started_at", "DateTime64(6, 'UTC')"),
                ("completed_at", "DateTime64(6, 'UTC')"),
                ("inserted_at", "DateTime64(6, 'UTC')"),
                ("expire_at", "DateTime"),
            ],
        ),
        "signature_clusters": (
            "project_id, cluster_run_id, id",
            "toYYYYMM(run_window_end)",
            [
                ("project_id", "String"),
                ("cluster_run_id", "UUID"),
                ("id", "UUID"),
                ("run_window_end", "DateTime64(6, 'UTC')"),
                ("signature_type", "Enum8('intent' = 1, 'failure' = 2)"),
                ("topic_id", "UUID"),
                ("category", "LowCardinality(String)"),
                ("centroid", "Array(Float32)"),
                ("label", "String"),
                ("description", "String"),
                ("occurrence_count", "UInt64"),
                ("inserted_at", "DateTime64(6, 'UTC')"),
                ("expire_at", "DateTime"),
            ],
        ),
    }
    assert ch_client.query(
        "SELECT name, engine, sorting_key, partition_key "
        "FROM system.tables "
        f"WHERE database = '{target_db}' AND name LIKE 'signature_cluster%' "
        "AND engine = 'ReplacingMergeTree' ORDER BY name"
    ).result_rows == [
        (name, "ReplacingMergeTree", sorting_key, partition_key)
        for name, (sorting_key, partition_key, _) in expected_tables.items()
    ]
    assert ch_client.query(
        "SELECT name, engine, create_table_query LIKE '%TO %.signature_cluster"
        "_assignments_by_conversation %' FROM system.tables "
        f"WHERE database = '{target_db}' AND name LIKE 'signature_cluster%' "
        "AND engine = 'MaterializedView'"
    ).result_rows == [
        ("signature_cluster_assignments_by_conversation_mv", "MaterializedView", 1)
    ]
    for table_name, (_, _, expected_columns) in expected_tables.items():
        assert (
            ch_client.query(
                "SELECT name, type FROM system.columns "
                f"WHERE database = '{target_db}' AND table = '{table_name}' "
                "ORDER BY position"
            ).result_rows
            == expected_columns
        )

    # No rollup or projection ships with the base storage contract. Three bloom filters
    # are the whole index surface, one per reverse lookup no sorting key already covers.
    assert (
        ch_client.query(
            "SELECT name FROM system.tables "
            f"WHERE database = '{target_db}' AND name = 'signature_cluster_daily'"
        ).result_rows
        == []
    )
    assert (
        ch_client.query(
            "SELECT name FROM system.projections "
            f"WHERE database = '{target_db}' AND table LIKE 'signature_cluster%'"
        ).result_rows
        == []
    )
    assert ch_client.query(
        "SELECT table, name, expr, type_full FROM system.data_skipping_indices "
        f"WHERE database = '{target_db}' AND table LIKE 'signature_cluster%' "
        "ORDER BY table, name"
    ).result_rows == [
        (
            "signature_cluster_assignments",
            "idx_signature_record_id",
            "signature_record_id",
            "bloom_filter(0.01)",
        ),
        (
            "signature_cluster_assignments",
            "idx_trace_id",
            "trace_id",
            "bloom_filter(0.01)",
        ),
        ("signature_clusters", "idx_topic_id", "topic_id", "bloom_filter(0.01)"),
    ]

    _insert_intent(ch_client, target_db, "action_request", 0.21)
    run_id = "019ff4bc-2ae1-744d-ae3a-285998a90519"
    for inserted_at, status, completed_at in [
        ("2026-06-20 15:00:00", "running", "toDateTime64(0, 6, 'UTC')"),
        (
            "2026-06-20 15:05:00",
            "succeeded",
            "toDateTime64('2026-06-20 15:04:00', 6, 'UTC')",
        ),
    ]:
        ch_client.command(
            f"INSERT INTO {target_db}.signature_cluster_runs "
            "(project_id, id, signature_type, signature_config_sha, "
            "cluster_config_sha, naming_config_sha, window_start, window_end, "
            "status, started_at, completed_at, inserted_at) VALUES "
            f"('project-1', '{run_id}', 'intent', 'signature-cfg-a', "
            "'cluster-cfg-a', 'naming-cfg-a', toDateTime64('2026-05-01', 6, 'UTC'), "
            "toDateTime64('2026-06-01', 6, 'UTC'), "
            f"'{status}', toDateTime64('2026-06-20 14:59:00', 6, 'UTC'), "
            f"{completed_at}, toDateTime64('{inserted_at}', 6, 'UTC'))"
        )

    # A run holds one assignment per signature, so a retry collapses onto it whatever
    # cluster the second attempt resolved.
    for inserted_at, label, count, distance, probability, umap in [
        ("2026-06-20 15:00:00", "draft", 1, 0.0, 0.0, (0.0, 0.0)),
        ("2026-06-20 15:05:00", "checkout", 2, 0.875, 0.91, (-1.5, 3.25)),
    ]:
        ch_client.command(
            f"INSERT INTO {target_db}.signature_clusters "
            "(project_id, cluster_run_id, id, run_window_end, signature_type, "
            "topic_id, category, centroid, label, description, occurrence_count, "
            "inserted_at) "
            f"VALUES ('project-1', '{run_id}', '{_CLUSTER_ID}', "
            f"toDateTime64('2026-06-01', 6, 'UTC'), 'intent', '{_TOPIC_ID}', "
            f"'action_request', [0.5, -0.25], '{label}', '{label} intents', {count}, "
            f"toDateTime64('{inserted_at}', 6, 'UTC'))"
        )
        ch_client.command(
            f"INSERT INTO {target_db}.signature_cluster_assignments "
            "(project_id, cluster_run_id, signature_record_id, cluster_id, "
            "signature_type, category, cluster_distance, cluster_probability, "
            "umap_x, umap_y, trace_id, span_id, conversation_id, user_id, agent_name, "
            f"trace_started_at, trace_ended_at, turn_duration_ms, turn_cost_usd, "
            f"{_TOKEN_COLUMNS}, inserted_at) "
            f"VALUES ('project-1', '{run_id}', '{_INTENT_ID}', '{_CLUSTER_ID}', "
            "'intent', 'action_request', "
            f"toFloat32({distance}), toFloat32({probability}), "
            f"toFloat32({umap[0]}), toFloat32({umap[1]}), "
            f"'trace-4', '{_SPAN_ID}', 'conversation-1', 'user-1', 'checkout-agent', "
            f"{_TRACE_STARTED_AT}, {_TRACE_ENDED_AT}, 9000, 0.21, "
            f"{_TOKEN_VALUES}, toDateTime64('{inserted_at}', 6, 'UTC'))"
        )

    assert ch_client.query(
        "SELECT argMax(status, inserted_at), argMax(signature_type, inserted_at), "
        "argMax(signature_config_sha, inserted_at), "
        "argMax(cluster_config_sha, inserted_at), "
        "argMax(naming_config_sha, inserted_at), "
        "toString(argMax(completed_at, inserted_at)), toString(min(completed_at)) "
        f"FROM {target_db}.signature_cluster_runs "
        "WHERE project_id = 'project-1' GROUP BY project_id, id"
    ).result_rows == [
        (
            "succeeded",
            "intent",
            "signature-cfg-a",
            "cluster-cfg-a",
            "naming-cfg-a",
            "2026-06-20 15:04:00.000000",
            "1970-01-01 00:00:00.000000",
        )
    ]
    assert ch_client.query(
        "SELECT argMax(label, inserted_at), argMax(occurrence_count, inserted_at), "
        "argMax(category, inserted_at), argMax(signature_type, inserted_at) "
        f"FROM {target_db}.signature_clusters "
        "WHERE project_id = 'project-1' GROUP BY project_id, cluster_run_id, id"
    ).result_rows == [("checkout", 2, "action_request", "intent")]
    assert ch_client.query(
        "SELECT toString(argMax(cluster_id, inserted_at)), "
        "argMax(category, inserted_at), "
        "round(toFloat64(argMax(cluster_distance, inserted_at)), 3), "
        "round(toFloat64(argMax(cluster_probability, inserted_at)), 2), "
        "toFloat64(argMax(umap_x, inserted_at)), "
        "toFloat64(argMax(umap_y, inserted_at)), "
        "argMax(trace_id, inserted_at), argMax(span_id, inserted_at), "
        "argMax(conversation_id, inserted_at), "
        "argMax(user_id, inserted_at), argMax(agent_name, inserted_at), "
        "toString(argMax(trace_started_at, inserted_at)), "
        "toString(argMax(trace_ended_at, inserted_at)), "
        "argMax(turn_duration_ms, inserted_at), "
        "round(argMax(turn_cost_usd, inserted_at), 3), "
        + ", ".join(f"argMax({column}, inserted_at)" for column in _TURN_TOKENS)
        + f" FROM {target_db}.signature_cluster_assignments "
        "WHERE project_id = 'project-1' "
        "GROUP BY project_id, cluster_run_id, signature_record_id"
    ).result_rows == [
        (
            _CLUSTER_ID,
            "action_request",
            0.875,
            0.91,
            -1.5,
            3.25,
            "trace-4",
            _SPAN_ID,
            "conversation-1",
            "user-1",
            "checkout-agent",
            "2026-05-30 09:15:00.000000",
            "2026-05-30 09:16:00.000000",
            9000,
            0.21,
            *_TURN_TOKENS.values(),
        )
    ]

    # The assignment references the upstream signature row UUID directly, and the
    # denormalized turn columns carry the same values that join would have hydrated.
    assert ch_client.query(
        "SELECT count(), countIf(a.trace_id = s.trace_id AND a.span_id = s.span_id "
        "AND a.conversation_id = s.conversation_id AND a.user_id = s.user_id "
        "AND a.agent_name = s.agent_name AND a.category = s.category "
        "AND a.trace_started_at = s.trace_started_at "
        "AND a.trace_ended_at = s.trace_ended_at "
        "AND a.turn_duration_ms = s.turn_duration_ms "
        "AND round(a.turn_cost_usd, 3) = round(s.turn_cost_usd, 3) "
        + "".join(f"AND a.{column} = s.{column} " for column in _TURN_TOKENS)
        + ") "
        f"FROM {target_db}.signature_cluster_assignments AS a "
        f"INNER JOIN {target_db}.intent_signatures AS s "
        "ON a.project_id = s.project_id "
        "AND toDate(a.trace_started_at) = toDate(s.trace_started_at) "
        "AND a.signature_record_id = s.id "
        f"WHERE a.cluster_run_id = toUUID('{run_id}')"
    ).result_rows == [(2, 2)]
    assert ch_client.query(
        "SELECT uniqExact(conversation_id), uniqExact(user_id) "
        f"FROM {target_db}.signature_cluster_assignments "
        f"WHERE project_id = 'project-1' AND cluster_run_id = toUUID('{run_id}') "
        f"AND cluster_id = '{_CLUSTER_ID}' AND trace_ended_at >= "
        "toDateTime64('2026-05-30', 6, 'UTC')"
    ).result_rows == [(1, 1)]
    assert ch_client.query(
        "SELECT toString(argMax(cluster_id, inserted_at)), "
        "argMax(category, inserted_at), argMax(agent_name, inserted_at) "
        f"FROM {target_db}.signature_cluster_assignments_by_conversation "
        "WHERE project_id = 'project-1' AND conversation_id = 'conversation-1' "
        "GROUP BY project_id, conversation_id, cluster_run_id, signature_record_id"
    ).result_rows == [(_CLUSTER_ID, "action_request", "checkout-agent")]

    for table_name in expected_tables:
        ch_client.command(f"OPTIMIZE TABLE {target_db}.{table_name} FINAL")
    assert ch_client.query(
        "SELECT sum(rows) FROM system.parts "
        f"WHERE database = '{target_db}' AND active "
        "AND table LIKE 'signature_cluster%'"
    ).result_rows == [(4,)]

    # Assignments partition on the turn they describe, matching the signature tables
    # they fan out from. A cluster has no turn, so it partitions on the run window.
    assert ch_client.query(
        "SELECT table, partition FROM system.parts "
        f"WHERE database = '{target_db}' AND active "
        "AND table LIKE 'signature_cluster%' AND table != 'signature_cluster_runs' "
        "ORDER BY table"
    ).result_rows == [
        ("signature_cluster_assignments", "202605"),
        ("signature_cluster_assignments_by_conversation", "202605"),
        ("signature_clusters", "202606"),
    ]

    # Moving the signature to another cluster inside the same run rewrites the one
    # assignment, on the conversation copy as well, because neither key holds cluster_id.
    ch_client.command(
        f"INSERT INTO {target_db}.signature_cluster_assignments "
        "(project_id, cluster_run_id, signature_record_id, cluster_id, signature_type, "
        "category, trace_id, span_id, conversation_id, user_id, agent_name, "
        "trace_started_at, trace_ended_at, inserted_at) "
        f"VALUES ('project-1', '{run_id}', '{_INTENT_ID}', '{_NIL_UUID}', 'intent', "
        f"'action_request', 'trace-4', '{_SPAN_ID}', 'conversation-1', 'user-1', "
        f"'checkout-agent', {_TRACE_STARTED_AT}, {_TRACE_ENDED_AT}, "
        "toDateTime64('2026-06-20 15:10:00', 6, 'UTC'))"
    )
    for table_name in (
        "signature_cluster_assignments",
        "signature_cluster_assignments_by_conversation",
    ):
        ch_client.command(f"OPTIMIZE TABLE {target_db}.{table_name} FINAL")
        assert ch_client.query(
            f"SELECT count(), toString(any(cluster_id)) FROM {target_db}.{table_name} "
            f"WHERE project_id = 'project-1' AND signature_record_id = '{_INTENT_ID}'"
        ).result_rows == [(1, _NIL_UUID)]

    # Two signatures off one turn each carry that turn's whole cost, so the naive sum
    # doubles it and dividing by the fan-out recovers it exactly.
    for suffix in ("a", "b"):
        ch_client.command(
            f"INSERT INTO {target_db}.signature_cluster_assignments "
            "(project_id, cluster_run_id, signature_record_id, cluster_id, "
            "signature_type, trace_id, span_id, conversation_id, trace_started_at, "
            "trace_ended_at, turn_cost_usd, turn_signature_count) "
            f"VALUES ('project-1', '{run_id}', generateUUIDv7(), '{_CLUSTER_ID}', "
            f"'intent', 'trace-fanout', 'span-{suffix}', 'conversation-2', "
            f"{_TRACE_STARTED_AT}, {_TRACE_ENDED_AT}, 0.6, 2)"
        )
    assert ch_client.query(
        "SELECT round(sum(turn_cost_usd), 4), "
        "round(sum(turn_cost_usd / turn_signature_count), 4) "
        f"FROM {target_db}.signature_cluster_assignments "
        "WHERE project_id = 'project-1' AND trace_id = 'trace-fanout'"
    ).result_rows == [(1.2, 0.6)]


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


def _system_cost_row_count(ch_client, target_db: str, llm_id: str) -> int:
    result = ch_client.query(
        f"SELECT count() FROM {target_db}.llm_token_prices "
        f"WHERE llm_id = %(llm_id)s AND created_by = 'system'",
        parameters={"llm_id": llm_id},
    )
    return int(result.result_rows[0][0])


def test_apply_migrations_backfills_costs_on_an_already_current_schema(ch_client):
    """Regression: a checkpoint-only cost change lands without a schema migration.

    `apply_migrations` used to lock-free pre-check purely on schema version and
    return before the post-migration hook ever ran, so once a database reached
    the latest migration, new/changed rows in `cost_checkpoint.json` were never
    inserted again. This reproduces that by migrating to latest (inserting
    costs once), deleting one model's seeded rows to simulate a checkpoint
    addition made after the schema was already current, then calling
    `apply_migrations` again with no version bump and asserting the row comes
    back.
    """
    mgmt_db = _unique_name("db_mgmt_cost_backfill")
    target_db = _unique_name("cost_backfill")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)
    llm_id = "gpt-4"

    # Uses the factory's real default hook + work-check (not disabled), since
    # this test is exercising exactly that wiring.
    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=False,
        use_distributed=False,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
    )
    migrator.apply_migrations(target_db)
    latest = _get_latest_migration_version(_PROD_MIGRATION_DIR)
    assert _get_migration_version(ch_client, mgmt_db, target_db) == latest
    # Migration 006 also seeds a `gpt-4` row with a different effective_date,
    # so a fresh migrate can leave more than one `system` row for this llm_id.
    assert _system_cost_row_count(ch_client, target_db, llm_id) >= 1

    # Simulate the checkpoint gaining this model's price after the schema was
    # already at `latest`: no migration to apply, only a pending cost row.
    ch_client.command(
        f"DELETE FROM {target_db}.llm_token_prices "
        f"WHERE llm_id = '{llm_id}' AND created_by = 'system'",
        settings={"mutations_sync": 2},
    )
    assert _system_cost_row_count(ch_client, target_db, llm_id) == 0

    migrator.apply_migrations(target_db)

    assert _system_cost_row_count(ch_client, target_db, llm_id) >= 1
    assert _get_migration_version(ch_client, mgmt_db, target_db) == latest


@pytest.mark.parametrize(
    ("target_version", "expect_table", "expect_ready"),
    [(4, False, False), (26, True, False), (None, True, True)],
)
def test_costs_schema_gate_tracks_the_columns_the_cost_code_reads(
    ch_client, target_version, expect_table, expect_ready
):
    """The costs gate approves a database exactly when the cost read works there.

    Migration 5 creates `llm_token_prices`, but 27 adds the two cache cost
    columns that `get_current_costs` selects, so a gate hardcoded to version 5
    approved versions 5 through 26, where that read fails. Version 4 has no
    table at all, 26 has the table without the cache columns, and latest has
    every column.
    """
    mgmt_db = _unique_name("db_mgmt_cost_gate")
    target_db = _unique_name(f"cost_gate_{target_version or 'latest'}")
    ch_client.track_db(mgmt_db)
    ch_client.track_db(target_db)

    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        replicated=False,
        use_distributed=False,
        management_db=mgmt_db,
        migration_dir=_PROD_MIGRATION_DIR,
    )
    migrator.apply_migrations(target_db, target_version=target_version)

    # `expect_table and not expect_ready` is the case a version-5 gate got wrong:
    # the table is there, so it approved a database the cost read cannot use.
    table_rows = ch_client.query(
        "SELECT count() FROM system.tables "
        "WHERE database = %(database)s AND name = %(table)s",
        parameters={"database": target_db, "table": COSTS_TABLE},
    ).result_rows[0][0]
    assert bool(table_rows) is expect_table
    assert costs_schema_is_ready(ch_client, target_db) is expect_ready

    prev_database = ch_client.database
    ch_client.database = target_db
    try:
        if expect_ready:
            get_current_costs(ch_client)
        else:
            with pytest.raises(DatabaseError):
                get_current_costs(ch_client)
    finally:
        ch_client.database = prev_database
