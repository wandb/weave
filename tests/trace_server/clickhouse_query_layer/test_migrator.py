import os
import types
from unittest.mock import Mock, call, patch

import pytest

from weave.trace_server.clickhouse_query_layer import migrator as trace_server_migrator
from weave.trace_server.clickhouse_query_layer.migrator import (
    BaseClickHouseTraceServerMigrator,
    CloudClickHouseTraceServerMigrator,
    DistributedClickHouseTraceServerMigrator,
    MigrationError,
    ReplicatedClickHouseTraceServerMigrator,
)

# Migrations are in weave/trace_server/migrations/, not in clickhouse_query_layer/migrations/
DEFAULT_MIGRATION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(trace_server_migrator.__file__), "..", "migrations")
)


@pytest.fixture
def mock_costs():
    with (
        patch(
            "weave.trace_server.clickhouse_query_layer.migrator.should_insert_costs",
            return_value=False,
        ),
        patch("weave.trace_server.clickhouse_query_layer.migrator.insert_costs"),
    ):
        yield


@pytest.fixture
def migrator():
    ch_client = Mock()
    migrator = trace_server_migrator.get_clickhouse_trace_server_migrator(ch_client)
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
    migrator = trace_server_migrator.get_clickhouse_trace_server_migrator(
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
    migrator = trace_server_migrator.get_clickhouse_trace_server_migrator(
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


def test_apply_migrations_with_target_version(mock_costs, tmp_path):
    # Create a temporary migration file
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    migration_file = migration_dir / "2.up.sql"
    migration_file.write_text(
        "CREATE TABLE test1 (id Int32);\nCREATE TABLE test2 (id Int32);"
    )

    ch_client = Mock()
    migrator = trace_server_migrator.get_clickhouse_trace_server_migrator(
        ch_client, migration_dir=str(migration_dir)
    )
    migrator._get_migration_status = Mock()
    migrator._get_migrations = Mock()
    migrator._determine_migrations_to_apply = Mock()
    migrator._update_migration_status = Mock()
    ch_client.command.reset_mock()

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


def test_migration_dir_must_be_absolute():
    ch_client = Mock()
    with pytest.raises(MigrationError, match="absolute path"):
        trace_server_migrator.get_clickhouse_trace_server_migrator(
            ch_client, migration_dir="relative/path"
        )


def test_apply_migrations_costs_disabled_does_not_call_costs():
    ch_client = Mock()
    migrator = trace_server_migrator.get_clickhouse_trace_server_migrator(
        ch_client, post_migration_hook=None
    )
    migrator._get_migration_status = Mock()
    migrator._get_migrations = Mock()
    migrator._determine_migrations_to_apply = Mock()

    migrator._get_migration_status.return_value = {
        "curr_version": 0,
        "partially_applied_version": None,
    }
    migrator._get_migrations.return_value = {
        "1": {"up": "1.up.sql", "down": "1.down.sql"},
    }
    migrator._determine_migrations_to_apply.return_value = []

    with (
        patch(
            "weave.trace_server.clickhouse_query_layer.migrator.should_insert_costs"
        ) as mock_should_insert_costs,
        patch(
            "weave.trace_server.clickhouse_query_layer.migrator.insert_costs"
        ) as mock_insert_costs,
    ):
        migrator.apply_migrations("test_db")

    mock_should_insert_costs.assert_not_called()
    mock_insert_costs.assert_not_called()


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
        trace_server_migrator.BaseClickHouseTraceServerMigrator._update_migration_status,
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


@pytest.mark.parametrize(
    ("input_name", "expected_output"),
    [
        ("my_table", "my_table_local"),
        ("already_local", "already_local"),  # Idempotency test
        ("test", "test_local"),
    ],
)
def test_add_local_suffix(input_name, expected_output):
    """Test that _add_local_suffix adds _local suffix correctly."""
    assert (
        DistributedClickHouseTraceServerMigrator._add_local_suffix(input_name)
        == expected_output
    )


@pytest.mark.parametrize(
    ("identifier", "is_valid"),
    [
        # Valid identifiers
        ("test_db", True),
        ("my_db123", True),
        ("db.table", True),
        # Invalid identifiers
        ("test-db", False),
        ("db;", False),
        ("db'name", False),
        ("db/*", False),
    ],
)
def test_is_safe_identifier(identifier, is_valid):
    """Test identifier validation."""
    assert BaseClickHouseTraceServerMigrator._is_safe_identifier(identifier) == is_valid


def test_create_db_sql(mock_costs):
    """Test database creation SQL generation in different modes."""
    # Test cloud mode
    cloud_migrator = CloudClickHouseTraceServerMigrator(
        Mock(), migration_dir=DEFAULT_MIGRATION_DIR
    )
    sql = cloud_migrator._create_db_sql("test_db")
    assert sql.strip() == "CREATE DATABASE IF NOT EXISTS test_db"

    # Test invalid database name
    with pytest.raises(MigrationError, match="Invalid database name"):
        cloud_migrator._create_db_sql("test;db")

    # Test replicated mode
    replicated_migrator = ReplicatedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    sql = replicated_migrator._create_db_sql("test_db")
    assert (
        sql.strip() == "CREATE DATABASE IF NOT EXISTS test_db ON CLUSTER test_cluster"
    )

    # Test invalid cluster name
    with pytest.raises(MigrationError, match="Invalid cluster name"):
        ReplicatedClickHouseTraceServerMigrator(
            Mock(),
            replicated_cluster="test;cluster",
            migration_dir=DEFAULT_MIGRATION_DIR,
        )


@pytest.mark.parametrize(
    ("input_sql", "expected_sql"),
    [
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
        # Non-MergeTree engines should be unchanged
        (
            "CREATE TABLE test (id Int32) ENGINE = Memory",
            "CREATE TABLE test (id Int32) ENGINE = Memory",
        ),
        (
            "CREATE TABLE test (id Int32) ENGINE = Log",
            "CREATE TABLE test (id Int32) ENGINE = Log",
        ),
    ],
)
def test_format_replicated_sql(input_sql, expected_sql):
    """Test MergeTree engine replacement with ReplicatedMergeTree."""
    replicated_migrator = ReplicatedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    assert replicated_migrator._format_replicated_sql(input_sql) == expected_sql


def test_format_replicated_sql_distributed():
    """Test replicated SQL formatting in distributed mode with explicit paths."""
    distributed_migrator = DistributedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    result = distributed_migrator._format_replicated_sql_distributed(
        "CREATE TABLE test (id Int32) ENGINE = MergeTree", "test_db"
    )
    assert (
        "ReplicatedMergeTree('/clickhouse/tables/{shard}/test_db/test_local', '{replica}')"
        in result
    )


@pytest.mark.parametrize(
    ("sql", "expected_table"),
    [
        ("CREATE TABLE test (id Int32)", "test"),
        ("CREATE TABLE IF NOT EXISTS my_table (id Int32)", "my_table"),
        ("ALTER TABLE test ADD COLUMN x Int32", None),  # Not a CREATE TABLE
    ],
)
def test_extract_table_name(sql, expected_table):
    """Test extracting table name from SQL."""
    from weave.trace_server.clickhouse_query_layer.migrator import SQLPatterns

    match = SQLPatterns.CREATE_TABLE.search(sql)
    result = match.group(1) if match else None
    assert result == expected_table


@pytest.mark.parametrize(
    ("sql", "table_name", "expected_sql"),
    [
        (
            "CREATE TABLE test (id Int32)",
            "test",
            "CREATE TABLE test_local (id Int32)",
        ),
        (
            "CREATE TABLE IF NOT EXISTS my_table (id Int32)",
            "my_table",
            "CREATE TABLE IF NOT EXISTS my_table_local (id Int32)",
        ),
    ],
)
def test_rename_table_to_local(sql, table_name, expected_sql):
    """Test renaming table to local in CREATE TABLE statement."""
    result = DistributedClickHouseTraceServerMigrator._rename_table_to_local(
        sql, table_name
    )
    assert result == expected_sql


def test_create_distributed_table_sql():
    """Test distributed table creation SQL."""
    distributed_migrator = DistributedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    sql = distributed_migrator._create_distributed_table_sql("test")
    expected = "CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster\n        AS test_local\n        ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())"
    assert sql.strip() == expected.strip()


def test_format_distributed_sql():
    """Test distributed SQL formatting for CREATE TABLE and other DDL."""
    distributed_migrator = DistributedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )

    # CREATE TABLE should create both local and distributed
    sql = "CREATE TABLE test ON CLUSTER test_cluster (id Int32) ENGINE = MergeTree"
    result = distributed_migrator._format_distributed_sql(sql)
    assert "test_local" in result.local_command
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


@pytest.mark.parametrize(
    ("input_sql", "expected_sql"),
    [
        (
            "ALTER TABLE test ADD COLUMN x Int32",
            "ALTER TABLE test_local ADD COLUMN x Int32",
        ),
        (
            "ALTER TABLE my_table DROP COLUMN old_col",
            "ALTER TABLE my_table_local DROP COLUMN old_col",
        ),
        (
            "alter table users modify column name String",
            "alter table users_local modify column name String",
        ),
        (
            "ALTER TABLE test_local ADD COLUMN x Int32",
            "ALTER TABLE test_local ADD COLUMN x Int32",  # Idempotent
        ),
    ],
)
def test_rename_alter_table_to_local(input_sql, expected_sql):
    """Test renaming ALTER TABLE to use _local suffix."""
    result = DistributedClickHouseTraceServerMigrator._rename_alter_table_to_local(
        input_sql
    )
    assert result == expected_sql


def test_distributed_requires_replicated():
    # Test that creating a migrator with use_distributed=True and replicated=False raises an error
    ch_client = Mock()

    with pytest.raises(
        MigrationError,
        match="Distributed tables can only be used with replicated tables",
    ):
        trace_server_migrator.get_clickhouse_trace_server_migrator(
            ch_client, replicated=False, use_distributed=True
        )


def test_format_replicated_sql_idempotent():
    """Test that formatting is idempotent (doesn't double-transform)."""
    replicated_migrator = ReplicatedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    formatted_once = replicated_migrator._format_replicated_sql(sql)
    expected = "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree"
    assert formatted_once == expected

    formatted_twice = replicated_migrator._format_replicated_sql(formatted_once)
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


@pytest.mark.parametrize(
    ("input_sql", "expected_sql"),
    [
        # DROP VIEW cases
        ("DROP VIEW my_view", "DROP VIEW my_view ON CLUSTER test_cluster"),
        (
            "DROP VIEW IF EXISTS my_view",
            "DROP VIEW IF EXISTS my_view ON CLUSTER test_cluster",
        ),
        # CREATE VIEW cases
        (
            "CREATE VIEW my_view AS SELECT * FROM test",
            "CREATE VIEW my_view ON CLUSTER test_cluster AS SELECT * FROM test",
        ),
        # CREATE MATERIALIZED VIEW cases
        (
            "CREATE MATERIALIZED VIEW calls_merged_view TO calls_merged AS SELECT * FROM call_parts",
            "CREATE MATERIALIZED VIEW calls_merged_view ON CLUSTER test_cluster TO calls_merged AS SELECT * FROM call_parts",
        ),
        # ALTER TABLE cases
        (
            "ALTER TABLE test ADD COLUMN x Int32",
            "ALTER TABLE test ON CLUSTER test_cluster ADD COLUMN x Int32",
        ),
    ],
)
def test_add_on_cluster_clause(input_sql, expected_sql):
    """Test that ON CLUSTER clause is added correctly to various DDL statements."""
    replicated_migrator = ReplicatedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    result = replicated_migrator._add_on_cluster_clause(input_sql)
    assert result == expected_sql


def test_add_on_cluster_clause_idempotent():
    """Test that ON CLUSTER clause addition is idempotent."""
    replicated_migrator = ReplicatedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    already_formatted = (
        "ALTER TABLE test ON CLUSTER existing_cluster ADD COLUMN x Int32"
    )
    result = replicated_migrator._add_on_cluster_clause(already_formatted)
    # Should not modify if already has ON CLUSTER
    assert result == already_formatted


def test_add_on_cluster_clause_non_ddl():
    """Test that non-DDL statements are not modified."""
    replicated_migrator = ReplicatedClickHouseTraceServerMigrator(
        Mock(), replicated_cluster="test_cluster", migration_dir=DEFAULT_MIGRATION_DIR
    )
    for sql in ["INSERT INTO test VALUES (1)", "SELECT * FROM test"]:
        assert replicated_migrator._add_on_cluster_clause(sql) == sql


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
    distributed_migrator.ch_client.command.reset_mock()
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


def test_execute_materialized_view_in_replicated_mode(replicated_migrator):
    """Test that CREATE MATERIALIZED VIEW gets ON CLUSTER in replicated mode."""
    command = "CREATE MATERIALIZED VIEW calls_merged_view TO calls_merged AS SELECT project_id, id FROM call_parts GROUP BY project_id, id"

    replicated_migrator._execute_migration_command("test_db", command)

    assert replicated_migrator.ch_client.command.call_count == 1
    assert replicated_migrator.ch_client.database == "original_db"

    call_sql = replicated_migrator.ch_client.command.call_args_list[0][0][0]
    expected_sql = "CREATE MATERIALIZED VIEW calls_merged_view ON CLUSTER test_cluster TO calls_merged AS SELECT project_id, id FROM call_parts GROUP BY project_id, id"
    assert call_sql == expected_sql


@pytest.mark.parametrize(
    ("sql", "expected_table"),
    [
        ("ALTER TABLE test ADD COLUMN x Int32", "test"),
        ("ALTER TABLE my_table DROP COLUMN old_col", "my_table"),
        ("alter table users modify column name String", "users"),
        ("ALTER TABLE default.test_table ADD COLUMN x Int32", "default.test_table"),
        ("CREATE TABLE test (id Int32)", None),  # Not an ALTER TABLE
    ],
)
def test_extract_alter_table_name(sql, expected_table):
    """Test extracting table name from ALTER TABLE statements."""
    result = DistributedClickHouseTraceServerMigrator._extract_alter_table_name(sql)
    assert result == expected_table


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


@pytest.mark.parametrize(
    ("input_sql", "expected_sql"),
    [
        # Basic FROM clause
        (
            "SELECT * FROM test WHERE id = 1",
            "SELECT * FROM test_local WHERE id = 1",
        ),
        # FROM with qualified column references
        (
            "SELECT * FROM call_parts WHERE call_parts.started_at IS NOT NULL",
            "SELECT * FROM call_parts_local WHERE call_parts_local.started_at IS NOT NULL",
        ),
        # Multiple qualified column references
        (
            "SELECT call_parts.id, call_parts.name FROM call_parts",
            "SELECT call_parts_local.id, call_parts_local.name FROM call_parts_local",
        ),
        # Qualified table names (database.table)
        (
            "SELECT * FROM default.test WHERE id = 1",
            "SELECT * FROM default.test_local WHERE id = 1",
        ),
        # Idempotency test
        (
            "SELECT * FROM test_local WHERE id = 1",
            "SELECT * FROM test_local WHERE id = 1",
        ),
        # Function calls on qualified columns
        (
            "SELECT isNotNull(call_parts.started_at) FROM call_parts",
            "SELECT isNotNull(call_parts_local.started_at) FROM call_parts_local",
        ),
    ],
)
def test_rename_from_tables_to_local(input_sql, expected_sql):
    """Test that FROM clauses and qualified column references get renamed to use _local suffix."""
    result = DistributedClickHouseTraceServerMigrator._rename_from_tables_to_local(
        input_sql
    )
    assert result == expected_sql


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
