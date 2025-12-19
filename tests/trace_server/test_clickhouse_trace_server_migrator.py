import types
from unittest.mock import Mock, call, patch

import pytest

from weave.trace_server import clickhouse_trace_server_migrator as trace_server_migrator
from weave.trace_server.clickhouse_trace_server_migrator import (
    MigrationError,
    _add_local_suffix,
    _create_db_sql,
    _create_distributed_table_sql,
    _extract_alter_table_name,
    _extract_table_name,
    _format_distributed_sql,
    _format_replicated_sql,
    _format_with_on_cluster_sql,
    _is_safe_identifier,
    _rename_alter_table_to_local,
    _rename_from_tables_to_local,
    _rename_table_to_local,
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


@pytest.fixture
def replicated_migrator():
    """Migrator configured for replicated mode with standard test settings."""
    ch_client = Mock()
    ch_client.database = "original_db"
    migrator = trace_server_migrator.ClickHouseTraceServerMigrator(
        ch_client,
        replicated=True,
        replicated_cluster="test_cluster",
        replicated_path="/clickhouse/tables/{db}",
    )
    migrator._get_migration_status = Mock()
    migrator._get_migrations = Mock()
    migrator._determine_migrations_to_apply = Mock()
    migrator._update_migration_status = Mock()
    ch_client.command.reset_mock()
    return migrator


@pytest.fixture
def distributed_migrator():
    """Migrator configured for distributed mode with standard test settings."""
    ch_client = Mock()
    ch_client.database = "original_db"
    migrator = trace_server_migrator.ClickHouseTraceServerMigrator(
        ch_client,
        replicated=True,
        use_distributed=True,
        replicated_cluster="test_cluster",
        replicated_path="/clickhouse/tables/{db}",
    )
    migrator._get_migration_status = Mock()
    migrator._get_migrations = Mock()
    migrator._determine_migrations_to_apply = Mock()
    migrator._update_migration_status = Mock()
    ch_client.command.reset_mock()
    return migrator


def test_apply_migrations_with_target_version(mock_costs, migrator, tmp_path):
    # Setup
    migrator._get_migration_status.return_value = {
        "curr_version": 1,
        "partially_applied_version": None,
    }
    migrator._get_migrations.return_value = {
        "1": {"up": "1.up.sql", "down": "1.down.sql"},
        "2": {"up": "2.up.sql", "down": "2.down.sql"},
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
    assert migrator.ch_client.command.call_count == 2
    migrator.ch_client.command.assert_has_calls(
        [call("CREATE TABLE test1 (id Int32)"), call("CREATE TABLE test2 (id Int32)")]
    )


def test_execute_migration_command(migrator):
    # Setup
    migrator.ch_client.database = "original_db"

    # Execute
    migrator._execute_migration_command("test_db", "CREATE TABLE test (id Int32)")

    # Verify
    assert (
        migrator.ch_client.database == "original_db"
    )  # Should restore original database
    migrator.ch_client.command.assert_called_once_with("CREATE TABLE test (id Int32)")


def test_migration_non_replicated(migrator):
    # Test that non-replicated mode doesn't transform the SQL
    orig = "CREATE TABLE test (id String, project_id String) ENGINE = MergeTree ORDER BY (project_id, id);"
    migrator._execute_migration_command("test_db", orig)
    migrator.ch_client.command.assert_called_once_with(orig)


def test_update_migration_status(migrator):
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


def test_add_local_suffix():
    """Test that _add_local_suffix adds _local suffix correctly."""
    assert _add_local_suffix("my_table") == "my_table_local"
    # Test idempotency - don't add twice
    assert _add_local_suffix("already_local") == "already_local"


def test_is_safe_identifier(migrator):
    # Valid identifiers
    assert _is_safe_identifier("test_db")
    assert _is_safe_identifier("my_db123")
    assert _is_safe_identifier("db.table")

    # Invalid identifiers
    assert not _is_safe_identifier("test-db")
    assert not _is_safe_identifier("db;")
    assert not _is_safe_identifier("db'name")
    assert not _is_safe_identifier("db/*")


def test_create_db_sql(migrator):
    with pytest.raises(MigrationError, match="Invalid database name"):
        _create_db_sql("test;db", False, "test_cluster", "/clickhouse/tables/{db}")

    with pytest.raises(MigrationError, match="Invalid cluster name"):
        _create_db_sql("test_db", True, "test;cluster", "/clickhouse/tables/{db}")

    sql = _create_db_sql("test_db", False, "test_cluster", "/clickhouse/tables/{db}")
    assert sql.strip() == "CREATE DATABASE IF NOT EXISTS test_db"

    sql = _create_db_sql("test_db", True, "test_cluster", "/clickhouse/tables/{db}")
    assert (
        sql.strip() == "CREATE DATABASE IF NOT EXISTS test_db ON CLUSTER test_cluster"
    )


def test_format_replicated_sql(migrator):
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
        (
            "CREATE TABLE test (id Int32) ENGINE  =   MergeTree",
            "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree",
        ),
        (
            "CREATE TABLE test (id Int32) ENGINE = MergeTree()",
            "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree",
        ),
    ]

    for input_sql, expected_sql in test_cases:
        assert _format_replicated_sql(input_sql) == expected_sql

    result = _format_replicated_sql(
        "CREATE TABLE test (id Int32) ENGINE = MergeTree",
        use_distributed=True,
        target_db="test_db",
    )
    assert (
        "ReplicatedMergeTree('/clickhouse/tables/{shard}/test_db/test_local', '{replica}')"
        in result
    )

    non_mergetree_cases = [
        "CREATE TABLE test (id Int32) ENGINE = Memory",
        "CREATE TABLE test (id Int32) ENGINE = Log",
        "CREATE TABLE test (id Int32) ENGINE = TinyLog",
    ]

    for sql in non_mergetree_cases:
        assert _format_replicated_sql(sql) == sql


def test_table_name_operations(migrator):
    assert _extract_table_name("CREATE TABLE test (id Int32)") == "test"
    assert (
        _extract_table_name("CREATE TABLE IF NOT EXISTS my_table (id Int32)")
        == "my_table"
    )
    assert _extract_table_name("ALTER TABLE test ADD COLUMN x Int32") is None

    assert (
        _rename_table_to_local("CREATE TABLE test (id Int32)", "test")
        == "CREATE TABLE test_local (id Int32)"
    )
    assert (
        _rename_table_to_local(
            "CREATE TABLE IF NOT EXISTS my_table (id Int32)", "my_table"
        )
        == "CREATE TABLE IF NOT EXISTS my_table_local (id Int32)"
    )


def test_create_distributed_table_sql(migrator):
    cluster_name = "test_cluster"
    sql = _create_distributed_table_sql("test", "test", cluster_name)
    expected = "CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster\n        AS test_local\n        ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())"
    assert sql.strip() == expected.strip()


def test_format_distributed_sql(migrator):
    cluster_name = "test_cluster"
    alter_sql = "ALTER TABLE test ADD COLUMN x Int32"

    result = _format_distributed_sql(alter_sql, cluster_name)
    assert result.local_command == alter_sql
    assert result.distributed_command is None

    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    result = _format_distributed_sql(sql, cluster_name)
    assert (
        "CREATE TABLE test_local (id Int32) ENGINE = MergeTree" == result.local_command
    )
    assert result.distributed_command is not None
    assert (
        "CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster"
        in result.distributed_command
    )
    assert (
        "ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())"
        in result.distributed_command
    )


def test_execute_migration_command_with_distributed(distributed_migrator):
    distributed_migrator._execute_migration_command(
        "test_db", "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    )

    assert distributed_migrator.ch_client.command.call_count == 2
    assert distributed_migrator.ch_client.database == "original_db"

    first_call = distributed_migrator.ch_client.command.call_args_list[0][0][0]
    assert "CREATE TABLE test_local ON CLUSTER test_cluster" in first_call
    assert (
        "ReplicatedMergeTree('/clickhouse/tables/{shard}/test_db/test_local', '{replica}')"
        in first_call
    )

    second_call = distributed_migrator.ch_client.command.call_args_list[1][0][0]
    assert "CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster" in second_call
    assert "AS test_local" in second_call
    assert (
        "ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())"
        in second_call
    )


def test_execute_migration_command_with_alter(replicated_migrator):
    replicated_migrator._execute_migration_command(
        "test_db", "ALTER TABLE test ADD COLUMN x Int32"
    )

    assert replicated_migrator.ch_client.command.call_count == 1
    assert replicated_migrator.ch_client.database == "original_db"

    call_sql = replicated_migrator.ch_client.command.call_args_list[0][0][0]
    assert call_sql == "ALTER TABLE test ON CLUSTER test_cluster ADD COLUMN x Int32"


def test_execute_migration_command_with_alter_distributed(distributed_migrator):
    distributed_migrator._execute_migration_command(
        "test_db", "ALTER TABLE test ADD COLUMN x Int32"
    )

    # Should execute ALTER on both local and distributed tables
    assert distributed_migrator.ch_client.command.call_count == 2
    assert distributed_migrator.ch_client.database == "original_db"

    # First call: ALTER local table
    local_alter_sql = distributed_migrator.ch_client.command.call_args_list[0][0][0]
    assert (
        local_alter_sql
        == "ALTER TABLE test_local ON CLUSTER test_cluster ADD COLUMN x Int32"
    )

    # Second call: ALTER distributed table
    distributed_alter_sql = distributed_migrator.ch_client.command.call_args_list[1][0][
        0
    ]
    assert (
        distributed_alter_sql
        == "ALTER TABLE test ON CLUSTER test_cluster ADD COLUMN x Int32"
    )


def test_rename_alter_table_to_local(migrator):
    assert (
        _rename_alter_table_to_local("ALTER TABLE test ADD COLUMN x Int32")
        == "ALTER TABLE test_local ADD COLUMN x Int32"
    )
    assert (
        _rename_alter_table_to_local("ALTER TABLE my_table DROP COLUMN old_col")
        == "ALTER TABLE my_table_local DROP COLUMN old_col"
    )
    assert (
        _rename_alter_table_to_local("alter table users modify column name String")
        == "alter table users_local modify column name String"
    )
    assert (
        _rename_alter_table_to_local("ALTER TABLE test_local ADD COLUMN x Int32")
        == "ALTER TABLE test_local ADD COLUMN x Int32"
    )


def test_distributed_requires_replicated():
    # Test that creating a migrator with use_distributed=True and replicated=False raises an error
    ch_client = Mock()

    with pytest.raises(
        MigrationError,
        match="Distributed tables can only be used with replicated tables",
    ):
        trace_server_migrator.ClickHouseTraceServerMigrator(
            ch_client, replicated=False, use_distributed=True
        )


def test_format_replicated_sql_idempotent(migrator):
    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    formatted_once = _format_replicated_sql(sql)
    expected = "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree"
    assert formatted_once == expected

    formatted_twice = _format_replicated_sql(formatted_once)
    assert formatted_twice == expected


def test_non_replicated_preserves_table_names(migrator):
    migrator.ch_client.database = "original_db"

    migrator._execute_migration_command(
        "test_db", "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    )

    assert migrator.ch_client.command.call_count == 1
    call_sql = migrator.ch_client.command.call_args_list[0][0][0]
    assert call_sql == "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    assert "test_local" not in call_sql
    assert "Distributed" not in call_sql


def test_format_views_with_on_cluster_sql(migrator):
    """Test CREATE VIEW and DROP VIEW get ON CLUSTER clause added."""
    cluster_name = "test_cluster"

    # Test cases for various DDL types
    test_cases = [
        # DROP VIEW cases
        ("DROP VIEW my_view", "DROP VIEW my_view ON CLUSTER test_cluster"),
        (
            "DROP VIEW IF EXISTS my_view",
            "DROP VIEW IF EXISTS my_view ON CLUSTER test_cluster",
        ),
        (
            "drop view if exists default.object_versions_deduped",
            "drop view if exists default.object_versions_deduped ON CLUSTER test_cluster",
        ),
        # CREATE VIEW cases
        (
            "CREATE VIEW my_view AS SELECT * FROM test",
            "CREATE VIEW my_view ON CLUSTER test_cluster AS SELECT * FROM test",
        ),
        (
            "CREATE VIEW IF NOT EXISTS my_view AS SELECT id FROM test",
            "CREATE VIEW IF NOT EXISTS my_view ON CLUSTER test_cluster AS SELECT id FROM test",
        ),
        # ALTER TABLE cases
        (
            "ALTER TABLE test ADD COLUMN x Int32",
            "ALTER TABLE test ON CLUSTER test_cluster ADD COLUMN x Int32",
        ),
    ]

    for input_sql, expected_sql in test_cases:
        result = _format_with_on_cluster_sql(input_sql, cluster_name)
        assert result == expected_sql

    # Test CREATE TABLE (has special pattern)
    create_table_sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    result = _format_with_on_cluster_sql(create_table_sql, cluster_name)
    assert "CREATE TABLE test ON CLUSTER test_cluster" in result

    # Test idempotency - don't add if already present
    already_formatted = (
        "ALTER TABLE test ON CLUSTER existing_cluster ADD COLUMN x Int32"
    )
    result = _format_with_on_cluster_sql(already_formatted, cluster_name)
    assert result == already_formatted

    # Test non-DDL statements are not modified
    for sql in ["INSERT INTO test VALUES (1)", "SELECT * FROM test"]:
        assert _format_with_on_cluster_sql(sql, cluster_name) == sql


def test_execute_views_in_replicated_and_distributed_modes(
    replicated_migrator, distributed_migrator
):
    """Test that CREATE/DROP VIEW work correctly in both replicated and distributed modes."""
    # Test in replicated mode
    replicated_migrator._execute_migration_command(
        "test_db", "DROP VIEW IF EXISTS my_view"
    )
    assert replicated_migrator.ch_client.command.call_count == 1
    assert replicated_migrator.ch_client.database == "original_db"
    call_sql = replicated_migrator.ch_client.command.call_args_list[0][0][0]
    assert call_sql == "DROP VIEW IF EXISTS my_view ON CLUSTER test_cluster"

    replicated_migrator.ch_client.command.reset_mock()

    replicated_migrator._execute_migration_command(
        "test_db", "CREATE VIEW my_view AS SELECT * FROM test"
    )
    assert replicated_migrator.ch_client.command.call_count == 1
    call_sql = replicated_migrator.ch_client.command.call_args_list[0][0][0]
    assert (
        call_sql == "CREATE VIEW my_view ON CLUSTER test_cluster AS SELECT * FROM test"
    )

    # Test in distributed mode (should be identical)
    distributed_migrator._execute_migration_command(
        "test_db", "DROP VIEW IF EXISTS my_view"
    )
    assert distributed_migrator.ch_client.command.call_count == 1
    call_sql = distributed_migrator.ch_client.command.call_args_list[0][0][0]
    assert call_sql == "DROP VIEW IF EXISTS my_view ON CLUSTER test_cluster"

    distributed_migrator.ch_client.command.reset_mock()

    distributed_migrator._execute_migration_command(
        "test_db", "CREATE VIEW my_view AS SELECT * FROM test"
    )
    assert distributed_migrator.ch_client.command.call_count == 1
    call_sql = distributed_migrator.ch_client.command.call_args_list[0][0][0]
    assert (
        call_sql == "CREATE VIEW my_view ON CLUSTER test_cluster AS SELECT * FROM test"
    )


def test_extract_alter_table_name(migrator):
    assert _extract_alter_table_name("ALTER TABLE test ADD COLUMN x Int32") == "test"
    assert (
        _extract_alter_table_name("ALTER TABLE my_table DROP COLUMN old_col")
        == "my_table"
    )
    assert (
        _extract_alter_table_name("alter table users modify column name String")
        == "users"
    )
    assert (
        _extract_alter_table_name("ALTER TABLE default.test_table ADD COLUMN x Int32")
        == "default.test_table"
    )
    assert _extract_alter_table_name("CREATE TABLE test (id Int32)") is None


def test_alter_distributed_with_multiple_columns(distributed_migrator):
    """Test that ALTER TABLE with multiple operations works correctly in distributed mode."""
    distributed_migrator._execute_migration_command(
        "test_db",
        "ALTER TABLE object_versions ADD COLUMN deleted_at Nullable(DateTime64(3)) DEFAULT NULL",
    )

    # Should execute ALTER on both local and distributed tables
    assert distributed_migrator.ch_client.command.call_count == 2
    assert distributed_migrator.ch_client.database == "original_db"

    # First call: ALTER local table
    local_alter_sql = distributed_migrator.ch_client.command.call_args_list[0][0][0]
    assert (
        local_alter_sql
        == "ALTER TABLE object_versions_local ON CLUSTER test_cluster ADD COLUMN deleted_at Nullable(DateTime64(3)) DEFAULT NULL"
    )

    # Second call: ALTER distributed table
    distributed_alter_sql = distributed_migrator.ch_client.command.call_args_list[1][0][
        0
    ]
    assert (
        distributed_alter_sql
        == "ALTER TABLE object_versions ON CLUSTER test_cluster ADD COLUMN deleted_at Nullable(DateTime64(3)) DEFAULT NULL"
    )


def test_rename_from_tables_to_local(migrator):
    """Test that FROM clauses and qualified column references get renamed to use _local suffix."""
    # Basic FROM clause
    assert (
        _rename_from_tables_to_local("SELECT * FROM test WHERE id = 1")
        == "SELECT * FROM test_local WHERE id = 1"
    )

    # FROM with qualified column references
    assert (
        _rename_from_tables_to_local(
            "SELECT * FROM call_parts WHERE call_parts.started_at IS NOT NULL"
        )
        == "SELECT * FROM call_parts_local WHERE call_parts_local.started_at IS NOT NULL"
    )

    # Multiple qualified column references from same table
    assert (
        _rename_from_tables_to_local(
            "SELECT call_parts.id, call_parts.name FROM call_parts"
        )
        == "SELECT call_parts_local.id, call_parts_local.name FROM call_parts_local"
    )

    # Test with qualified table names (database.table)
    assert (
        _rename_from_tables_to_local("SELECT * FROM default.test WHERE id = 1")
        == "SELECT * FROM default.test_local WHERE id = 1"
    )

    # Test idempotency - don't add _local if already present
    assert (
        _rename_from_tables_to_local("SELECT * FROM test_local WHERE id = 1")
        == "SELECT * FROM test_local WHERE id = 1"
    )

    # Test with function calls on qualified columns
    assert (
        _rename_from_tables_to_local(
            "SELECT isNotNull(call_parts.started_at) FROM call_parts"
        )
        == "SELECT isNotNull(call_parts_local.started_at) FROM call_parts_local"
    )


def test_alter_materialized_view_distributed(distributed_migrator):
    """Test that ALTER TABLE MODIFY QUERY for materialized views works correctly in distributed mode.

    In distributed mode, we DROP and CREATE the materialized view with:
    1. View name gets _local suffix
    2. TO clause points to the target table (_local)
    3. SELECT query references _local tables
    """
    # Full real-world SQL from migration
    alter_view_sql = """ALTER TABLE calls_merged_view MODIFY QUERY
    SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        -- *** Ensure wb_user_id is grabbed from valid call rather than deleted row ***
        anySimpleStateIf(wb_user_id, isNotNull(call_parts.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        array_concat_aggSimpleState(output_refs) as output_refs,
        -- **** comment comment ****
        anySimpleState(deleted_at) as deleted_at
    FROM call_parts
    GROUP BY project_id,
        id"""

    distributed_migrator._execute_migration_command("test_db", alter_view_sql)

    # Should execute DROP and CREATE (2 commands)
    assert distributed_migrator.ch_client.command.call_count == 2
    assert distributed_migrator.ch_client.database == "original_db"

    # First command: DROP the existing view
    drop_sql = distributed_migrator.ch_client.command.call_args_list[0][0][0]
    expected_drop_sql = (
        "DROP TABLE IF EXISTS calls_merged_view_local ON CLUSTER test_cluster"
    )
    assert drop_sql == expected_drop_sql

    # Second command: CREATE the view with _local suffix and TO clause
    create_sql = distributed_migrator.ch_client.command.call_args_list[1][0][0]
    expected_create_sql = """CREATE MATERIALIZED VIEW calls_merged_view_local
ON CLUSTER test_cluster
TO calls_merged_local
AS
SELECT project_id,
        id,
        anySimpleState(wb_run_id) as wb_run_id,
        -- *** Ensure wb_user_id is grabbed from valid call rather than deleted row ***
        anySimpleStateIf(wb_user_id, isNotNull(call_parts_local.started_at)) as wb_user_id,
        anySimpleState(trace_id) as trace_id,
        array_concat_aggSimpleState(output_refs) as output_refs,
        -- **** comment comment ****
        anySimpleState(deleted_at) as deleted_at
    FROM call_parts_local
    GROUP BY project_id,
        id"""
    assert create_sql == expected_create_sql


def test_skip_materialize_command_distributed(distributed_migrator):
    """Test that commands with MATERIALIZE keyword are skipped in distributed mode."""
    # Command with MATERIALIZE keyword (e.g., ALTER TABLE ... MATERIALIZE COLUMN)
    materialize_command = "ALTER TABLE test_table MATERIALIZE COLUMN some_column"

    distributed_migrator._execute_migration_command("test_db", materialize_command)

    # Should not execute any commands (skipped)
    assert distributed_migrator.ch_client.command.call_count == 0
    assert distributed_migrator.ch_client.database == "original_db"


def test_index_operations_only_on_local_tables_distributed(distributed_migrator):
    """Test that ADD/DROP INDEX operations are only applied to local tables in distributed mode."""
    test_cases = [
        (
            "ALTER TABLE calls_merged ADD INDEX idx_sortable_datetime (sortable_datetime) TYPE minmax GRANULARITY 1",
            "ALTER TABLE calls_merged_local ON CLUSTER test_cluster ADD INDEX idx_sortable_datetime (sortable_datetime) TYPE minmax GRANULARITY 1",
        ),
        (
            "ALTER TABLE calls_merged DROP INDEX IF EXISTS idx_sortable_datetime",
            "ALTER TABLE calls_merged_local ON CLUSTER test_cluster DROP INDEX IF EXISTS idx_sortable_datetime",
        ),
    ]

    for command, expected_local_sql in test_cases:
        distributed_migrator._execute_migration_command("test_db", command)

        # Should only execute ALTER on local table (1 command, not 2)
        assert distributed_migrator.ch_client.command.call_count == 1
        assert distributed_migrator.ch_client.database == "original_db"

        # Verify it was applied to the local table
        local_alter_sql = distributed_migrator.ch_client.command.call_args_list[0][0][0]
        assert local_alter_sql == expected_local_sql

        # Reset for next test case
        distributed_migrator.ch_client.command.reset_mock()
