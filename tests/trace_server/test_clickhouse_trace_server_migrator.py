import os
import types
from unittest.mock import Mock, call, patch

import pytest

from weave.trace_server import clickhouse_trace_server_migrator as trace_server_migrator
from weave.trace_server.clickhouse_trace_server_migrator import (
    MigrationError,
    MigrationInfo,
    MigrationStatus,
)


@pytest.fixture
def mock_costs():
    with patch(
        "weave.trace_server.costs.insert_costs.should_insert_costs", return_value=False
    ) as mock_should_insert:
        with patch(
            "weave.trace_server.costs.insert_costs.get_current_costs", return_value=[]
        ) as mock_get_costs:
            yield


@pytest.fixture
def migrator():
    ch_client = Mock()
    migrator = trace_server_migrator.ClickHouseTraceServerMigrator(ch_client)
    migrator._get_migration_status = Mock()
    migrator._get_migrations = Mock()
    migrator._determine_migrations_to_apply = Mock()
    migrator._update_migration_status = Mock()
    ch_client.command.reset_mock()
    return migrator


def test_apply_migrations_with_target_version(mock_costs, migrator, tmp_path):
    # Setup
    migrator._get_migration_status.return_value = trace_server_migrator.MigrationStatus(
        db_name="test_db",
        curr_version=1,
        partially_applied_version=None,
    )
    migrator._get_migrations.return_value = {
        1: trace_server_migrator.MigrationInfo(up="1.up.sql", down="1.down.sql"),
        2: trace_server_migrator.MigrationInfo(up="2.up.sql", down="2.down.sql"),
    }
    migrator._determine_migrations_to_apply.return_value = [(2, "2.up.sql")]

    # Create a temporary migration file
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    migration_file = migration_dir / "2.up.sql"
    migration_file.write_text(
        "CREATE TABLE test1 (id Int32);\nCREATE TABLE test2 (id Int32);"
    )

    # Mock the migration directory path
    with patch("os.path.dirname") as mock_dirname:
        mock_dirname.return_value = str(tmp_path)

        # Execute
        migrator.apply_migrations("test_db", target_version=2)

    # Verify
    migrator._get_migration_status.assert_called_once_with("test_db")
    migrator._get_migrations.assert_called_once()
    migrator._determine_migrations_to_apply.assert_called_once_with(
        1, migrator._get_migrations.return_value, 2
    )

    # Verify migration execution
    assert migrator._update_migration_status.call_count == 2
    migrator._update_migration_status.assert_has_calls(
        [call("test_db", 2, is_start=True), call("test_db", 2, is_start=False)]
    )

    # Verify the actual SQL commands were executed
    ch_client = migrator.ch_client
    assert ch_client.command.call_count == 2
    ch_client.command.assert_has_calls(
        [call("CREATE TABLE test1 (id Int32)"), call("CREATE TABLE test2 (id Int32)")]
    )


def test_execute_migration_command(mock_costs, migrator):
    # Setup
    ch_client = migrator.ch_client
    ch_client.database = "original_db"

    # Execute
    migrator._execute_migration_command("test_db", "CREATE TABLE test (id Int32)")

    # Verify
    assert ch_client.database == "original_db"  # Should restore original database
    ch_client.command.assert_called_once_with("CREATE TABLE test (id Int32)")


def test_migration_replicated(mock_costs, migrator):
    ch_client = migrator.ch_client
    orig = "CREATE TABLE test (id String, project_id String) ENGINE = MergeTree ORDER BY (project_id, id);"
    migrator._execute_migration_command("test_db", orig)
    ch_client.command.assert_called_once_with(orig)


def test_update_migration_status(mock_costs, migrator):
    # Don't mock _update_migration_status for this test
    migrator._update_migration_status = types.MethodType(
        trace_server_migrator.ClickHouseTraceServerMigrator._update_migration_status,
        migrator,
    )

    # Test start of migration
    migrator._update_migration_status("test_db", 2, is_start=True)
    migrator.ch_client.command.assert_called_with(
        "ALTER TABLE db_management.migrations UPDATE partially_applied_version = 2 WHERE db_name = 'test_db'"
    )

    # Test end of migration
    migrator._update_migration_status("test_db", 2, is_start=False)
    migrator.ch_client.command.assert_called_with(
        "ALTER TABLE db_management.migrations UPDATE curr_version = 2, partially_applied_version = NULL WHERE db_name = 'test_db'"
    )


def test_is_safe_identifier(mock_costs, migrator):
    # Valid identifiers
    assert migrator._is_safe_identifier("test_db")
    assert migrator._is_safe_identifier("my_db123")
    assert migrator._is_safe_identifier("db.table")

    # Invalid identifiers
    assert not migrator._is_safe_identifier("test-db")
    assert not migrator._is_safe_identifier("db;")
    assert not migrator._is_safe_identifier("db'name")
    assert not migrator._is_safe_identifier("db/*")


def test_create_db_sql_validation(mock_costs, migrator):
    # Test invalid database name
    with pytest.raises(MigrationError, match="Invalid database name"):
        migrator._create_db_sql("test;db")

    # Test replicated mode with invalid values
    migrator.replicated = True
    migrator.replicated_cluster = "test;cluster"
    with pytest.raises(MigrationError, match="Invalid cluster name"):
        migrator._create_db_sql("test_db")

    migrator.replicated_cluster = "test_cluster"
    migrator.replicated_path = "/clickhouse/bad;path/{db}"
    with pytest.raises(MigrationError, match="Invalid replicated path"):
        migrator._create_db_sql("test_db")


def test_create_db_sql_non_replicated(mock_costs, migrator):
    # Test non-replicated mode
    migrator.replicated = False
    sql = migrator._create_db_sql("test_db")
    assert sql.strip() == "CREATE DATABASE IF NOT EXISTS test_db"


def test_create_db_sql_replicated(mock_costs, migrator):
    # Test replicated mode
    migrator.replicated = True
    migrator.replicated_path = "/clickhouse/tables/{db}"
    migrator.replicated_cluster = "test_cluster"

    sql = migrator._create_db_sql("test_db")
    expected = """
        CREATE DATABASE IF NOT EXISTS test_db ON CLUSTER test_cluster ENGINE=Replicated('/clickhouse/tables/test_db', '{shard}', '{replica}')
    """.strip()
    assert sql.strip() == expected


def test_format_replicated_sql_non_replicated(mock_costs, migrator):
    # Test that SQL is unchanged when replicated=False
    migrator.replicated = False
    test_cases = [
        "CREATE TABLE test (id Int32) ENGINE = MergeTree",
        "CREATE TABLE test (id Int32) ENGINE = SummingMergeTree",
        "CREATE TABLE test (id Int32) ENGINE=ReplacingMergeTree",
    ]

    for sql in test_cases:
        assert migrator._format_replicated_sql(sql) == sql


def test_format_replicated_sql_replicated(mock_costs, migrator):
    # Test that MergeTree engines are converted to Replicated variants
    migrator.replicated = True

    test_cases = [
        (
            "CREATE TABLE test (id Int32) ENGINE = MergeTree",
            "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree",
        ),
        (
            "CREATE TABLE test (id Int32) ENGINE = SummingMergeTree",
            "CREATE TABLE test (id Int32) ENGINE = ReplicatedSummingMergeTree",
        ),
        (
            "CREATE TABLE test (id Int32) ENGINE=ReplacingMergeTree",
            "CREATE TABLE test (id Int32) ENGINE = ReplicatedReplacingMergeTree",
        ),
        # Test with extra whitespace
        (
            "CREATE TABLE test (id Int32) ENGINE  =   MergeTree",
            "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree",
        ),
        # Test with parameters
        (
            "CREATE TABLE test (id Int32) ENGINE = MergeTree()",
            "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree()",
        ),
    ]

    for input_sql, expected_sql in test_cases:
        assert migrator._format_replicated_sql(input_sql) == expected_sql


def test_format_replicated_sql_non_mergetree(mock_costs, migrator):
    # Test that non-MergeTree engines are left unchanged
    migrator.replicated = True

    test_cases = [
        "CREATE TABLE test (id Int32) ENGINE = Memory",
        "CREATE TABLE test (id Int32) ENGINE = Log",
        "CREATE TABLE test (id Int32) ENGINE = TinyLog",
        # This should not be changed as it's not a complete word match
        "CREATE TABLE test (id Int32) ENGINE = MyMergeTreeCustom",
    ]

    for sql in test_cases:
        assert migrator._format_replicated_sql(sql) == sql


def test_get_migrations_parsing(tmp_path):
    # Setup migration files
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()

    files = [
        "1_init.up.sql",
        "1_init.down.sql",
        "2_feature.experimental.up.sql",
        "2_feature.experimental.down.sql",
        "3_complex.alpha_beta.up.sql",
        "3_complex.alpha_beta.down.sql",
        "4_legacy.up.sql",
        "4_legacy.down.sql",
    ]
    for f in files:
        (migration_dir / f).write_text("")

    ch_client = Mock()
    migrator = trace_server_migrator.ClickHouseTraceServerMigrator(ch_client)

    # Mock where the migrator looks for files
    with (
        patch("os.path.dirname", return_value=str(tmp_path)),
        patch("os.path.join", side_effect=os.path.join),
        patch("os.listdir", return_value=files),
    ):
        migration_map = migrator._get_migrations()

        assert len(migration_map) == 4

        # Check standard migration
        assert migration_map[1].up == "1_init.up.sql"
        assert migration_map[1].keys == []

        # Check single key
        assert migration_map[2].up == "2_feature.experimental.up.sql"
        assert set(migration_map[2].keys) == {"experimental"}

        # Check multiple keys
        assert migration_map[3].up == "3_complex.alpha_beta.up.sql"
        assert set(migration_map[3].keys) == {"alpha", "beta"}

        # Check legacy style (implied no keys)
        assert migration_map[4].up == "4_legacy.up.sql"
        assert migration_map[4].keys == []


def test_apply_migrations_skips_mismatch_keys(mock_costs, migrator, tmp_path):
    # Setup
    migrator._get_migration_status = Mock(
        return_value=MigrationStatus(
            db_name="test_db",
            curr_version=0,
            partially_applied_version=None,
        )
    )

    # Mock migration map with keys
    migrator._get_migrations = Mock(
        return_value={
            1: MigrationInfo(up="1_init.up.sql", down="1_init.down.sql", keys=[]),
            2: MigrationInfo(
                up="2_exp.experimental.up.sql",
                down="2_exp.experimental.down.sql",
                keys=["experimental"],
            ),
            3: MigrationInfo(
                up="3_beta.beta.up.sql",
                down="3_beta.beta.down.sql",
                keys=["beta"],
            ),
        }
    )

    migrator._determine_migrations_to_apply = Mock(
        return_value=[
            (1, "1_init.up.sql"),
            (2, "2_exp.experimental.up.sql"),
            (3, "3_beta.beta.up.sql"),
        ]
    )

    migrator._update_migration_status = Mock()

    # Make _apply_migration simulate the status update side effect
    def apply_side_effect(target_db, target_version, migration_file):
        migrator._update_migration_status(target_db, target_version, is_start=True)
        migrator._update_migration_status(target_db, target_version, is_start=False)

    migrator._apply_migration = Mock(side_effect=apply_side_effect)

    # CASE 1: No keys in env var
    migrator.migration_keys = []
    migrator.apply_migrations("test_db", target_version=3)

    # Check 1 ran
    migrator._apply_migration.assert_any_call("test_db", 1, "1_init.up.sql")

    # Check 2 skipped (not called)
    with pytest.raises(AssertionError):
        migrator._apply_migration.assert_any_call(
            "test_db", 2, "2_exp.experimental.up.sql"
        )

    # Check 3 skipped
    with pytest.raises(AssertionError):
        migrator._apply_migration.assert_any_call("test_db", 3, "3_beta.beta.up.sql")

    # Check version updates happen for ALL (skipped ones too)
    calls = migrator._update_migration_status.call_args_list
    versions_updated = []
    for c in calls:
        args, kwargs = c
        if args[0] != "test_db":
            continue

        is_start = kwargs.get("is_start")
        if is_start is None and len(args) > 2:
            is_start = args[2]

        if is_start is False:
            versions_updated.append(args[1])

    assert 1 in versions_updated
    assert 2 in versions_updated
    assert 3 in versions_updated


def test_apply_migrations_matches_keys(mock_costs, migrator):
    # Setup
    migrator._get_migration_status = Mock(
        return_value=MigrationStatus(
            db_name="test_db",
            curr_version=0,
            partially_applied_version=None,
        )
    )
    migrator._get_migrations = Mock(
        return_value={
            1: MigrationInfo(up="1.up.sql", keys=[]),
            2: MigrationInfo(up="2.exp.up.sql", keys=["experimental"]),
        }
    )
    migrator._determine_migrations_to_apply = Mock(
        return_value=[(1, "1.up.sql"), (2, "2.exp.up.sql")]
    )
    migrator._apply_migration = Mock()
    migrator._update_migration_status = Mock()

    # CASE 2: Env var has 'experimental'
    migrator.migration_keys = ["experimental"]
    migrator.apply_migrations("test_db", target_version=2)

    # Should run both
    migrator._apply_migration.assert_any_call("test_db", 1, "1.up.sql")
    migrator._apply_migration.assert_any_call("test_db", 2, "2.exp.up.sql")


def test_apply_migrations_partial_keys(mock_costs, migrator):
    # Setup
    migrator._get_migration_status = Mock(
        return_value=MigrationStatus(
            db_name="test_db",
            curr_version=0,
            partially_applied_version=None,
        )
    )
    migrator._get_migrations = Mock(
        return_value={
            1: MigrationInfo(up="1.up.sql", keys=["alpha", "beta"]),
        }
    )
    migrator._determine_migrations_to_apply = Mock(return_value=[(1, "1.up.sql")])
    migrator._apply_migration = Mock()
    migrator._update_migration_status = Mock()

    # CASE 3: Env var has 'alpha' (one of the keys)
    migrator.migration_keys = ["alpha"]
    migrator.apply_migrations("test_db", target_version=1)

    # Should run because alpha matches
    migrator._apply_migration.assert_called_with("test_db", 1, "1.up.sql")

    # CASE 4: Env var has 'gamma' (no match)
    migrator._apply_migration.reset_mock()
    migrator.migration_keys = ["gamma"]
    migrator.apply_migrations("test_db", target_version=1)

    # Should skip
    migrator._apply_migration.assert_not_called()
    # But should update version
    assert migrator._update_migration_status.call_count > 0
