import types
from unittest.mock import Mock, call, patch

import pytest

from weave.trace_server import clickhouse_trace_server_migrator as trace_server_migrator
from weave.trace_server.clickhouse_trace_server_migrator import MigrationError


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
    ch_client = migrator.ch_client
    assert ch_client.command.call_count == 2
    ch_client.command.assert_has_calls(
        [call("CREATE TABLE test1 (id Int32)"), call("CREATE TABLE test2 (id Int32)")]
    )


def test_execute_migration_command(migrator):
    # Setup
    ch_client = migrator.ch_client
    ch_client.database = "original_db"

    # Execute
    migrator._execute_migration_command("test_db", "CREATE TABLE test (id Int32)")

    # Verify
    assert ch_client.database == "original_db"  # Should restore original database
    ch_client.command.assert_called_once_with("CREATE TABLE test (id Int32)")


def test_migration_replicated(migrator):
    ch_client = migrator.ch_client
    orig = "CREATE TABLE test (id String, project_id String) ENGINE = MergeTree ORDER BY (project_id, id);"
    migrator._execute_migration_command("test_db", orig)
    ch_client.command.assert_called_once_with(orig)


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


def test_is_safe_identifier(migrator):
    # Valid identifiers
    assert migrator._is_safe_identifier("test_db")
    assert migrator._is_safe_identifier("my_db123")
    assert migrator._is_safe_identifier("db.table")

    # Invalid identifiers
    assert not migrator._is_safe_identifier("test-db")
    assert not migrator._is_safe_identifier("db;")
    assert not migrator._is_safe_identifier("db'name")
    assert not migrator._is_safe_identifier("db/*")


def test_create_db_sql_validation(migrator):
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


def test_create_db_sql_non_replicated(migrator):
    # Test non-replicated mode
    migrator.replicated = False
    sql = migrator._create_db_sql("test_db")
    assert sql.strip() == "CREATE DATABASE IF NOT EXISTS test_db"


def test_create_db_sql_replicated(migrator):
    # Test replicated mode
    migrator.replicated = True
    migrator.replicated_path = "/clickhouse/tables/{db}"
    migrator.replicated_cluster = "test_cluster"

    sql = migrator._create_db_sql("test_db")
    expected = """
        CREATE DATABASE IF NOT EXISTS test_db ON CLUSTER test_cluster ENGINE=Replicated('/clickhouse/tables/test_db', '{shard}', '{replica}')
    """.strip()
    assert sql.strip() == expected


def test_format_replicated_sql_non_replicated(migrator):
    # Test that SQL is unchanged when replicated=False
    migrator.replicated = False
    test_cases = [
        "CREATE TABLE test (id Int32) ENGINE = MergeTree",
        "CREATE TABLE test (id Int32) ENGINE = SummingMergeTree",
        "CREATE TABLE test (id Int32) ENGINE=ReplacingMergeTree",
    ]

    for sql in test_cases:
        assert migrator._format_replicated_sql(sql) == sql


def test_format_replicated_sql_replicated(migrator):
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


def test_format_replicated_sql_non_mergetree(migrator):
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


def test_add_on_cluster_to_alter_non_replicated(migrator):
    # Test that ALTER TABLE is unchanged when replicated=False
    migrator.replicated = False
    sql = "ALTER TABLE test ADD COLUMN x Int32"
    assert migrator._add_on_cluster_to_alter(sql) == sql


def test_add_on_cluster_to_alter_replicated(migrator):
    # Test that ALTER TABLE gets ON CLUSTER added when replicated=True
    migrator.replicated = True
    migrator.replicated_cluster = "test_cluster"

    test_cases = [
        (
            "ALTER TABLE test ADD COLUMN x Int32",
            "ALTER TABLE test ON CLUSTER test_cluster ADD COLUMN x Int32",
        ),
        (
            "ALTER TABLE my_table DROP COLUMN old_col",
            "ALTER TABLE my_table ON CLUSTER test_cluster DROP COLUMN old_col",
        ),
        (
            "alter table users modify column name String",
            "alter table users ON CLUSTER test_cluster modify column name String",
        ),
    ]

    for input_sql, expected_sql in test_cases:
        result = migrator._add_on_cluster_to_alter(input_sql)
        assert result == expected_sql, f"Failed for: {input_sql}"


def test_add_on_cluster_to_alter_idempotent(migrator):
    # Test that ON CLUSTER is not added if already present
    migrator.replicated = True
    migrator.replicated_cluster = "test_cluster"

    sql = "ALTER TABLE test ON CLUSTER existing_cluster ADD COLUMN x Int32"
    result = migrator._add_on_cluster_to_alter(sql)
    # Should not modify if ON CLUSTER already present
    assert result == sql


def test_add_on_cluster_to_alter_non_alter_statements(migrator):
    # Test that non-ALTER statements are left unchanged
    migrator.replicated = True
    migrator.replicated_cluster = "test_cluster"

    test_cases = [
        "CREATE TABLE test (id Int32) ENGINE = MergeTree",
        "INSERT INTO test VALUES (1)",
        "SELECT * FROM test",
        "DROP TABLE test",
    ]

    for sql in test_cases:
        assert migrator._add_on_cluster_to_alter(sql) == sql


def test_extract_table_name(migrator):
    # Test extracting table names from CREATE TABLE statements
    test_cases = [
        ("CREATE TABLE test (id Int32)", "test"),
        ("CREATE TABLE IF NOT EXISTS my_table (id Int32)", "my_table"),
        ("create table users (name String)", "users"),
        ("CREATE TABLE test123 (id Int32) ENGINE = MergeTree", "test123"),
        (
            "CREATE TABLE my_db.my_table (id Int32)",
            "my_db",
        ),  # Gets the first identifier
        ("ALTER TABLE test ADD COLUMN x Int32", None),  # Not a CREATE TABLE
        ("INSERT INTO test VALUES (1)", None),  # Not a CREATE TABLE
    ]

    for sql, expected in test_cases:
        result = migrator._extract_table_name(sql)
        assert result == expected, f"Failed for: {sql}"


def test_rename_table_to_local(migrator):
    # Test renaming tables to _local suffix
    test_cases = [
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
        (
            "CREATE TABLE users (name String) ENGINE = MergeTree",
            "users",
            "CREATE TABLE users_local (name String) ENGINE = MergeTree",
        ),
    ]

    for sql, table_name, expected in test_cases:
        result = migrator._rename_table_to_local(sql, table_name)
        assert result == expected, f"Failed for: {sql}"


def test_create_distributed_table_sql(migrator):
    # Setup
    migrator.replicated = True
    migrator.replicated_cluster = "test_cluster"

    # Test creating distributed table SQL
    sql = migrator._create_distributed_table_sql("test", "test")
    assert "CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster" in sql
    assert (
        "ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())"
        in sql
    )

    # Test with invalid identifiers
    with pytest.raises(MigrationError, match="Invalid table name"):
        migrator._create_distributed_table_sql("test;table", "test")

    with pytest.raises(MigrationError, match="Invalid local table name"):
        migrator._create_distributed_table_sql("test", "test;local")

    migrator.replicated_cluster = "bad;cluster"
    with pytest.raises(MigrationError, match="Invalid cluster name"):
        migrator._create_distributed_table_sql("test", "test")


def test_transform_for_distributed_disabled(migrator):
    # Test that transformation is skipped when use_distributed=False
    migrator.use_distributed = False
    migrator.replicated = True
    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"

    local_cmd, dist_cmd = migrator._transform_for_distributed(sql)
    assert local_cmd == sql
    assert dist_cmd is None


def test_transform_for_distributed_non_replicated(migrator):
    # Test that transformation is skipped when replicated=False
    migrator.use_distributed = True
    migrator.replicated = False
    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"

    local_cmd, dist_cmd = migrator._transform_for_distributed(sql)
    assert local_cmd == sql
    assert dist_cmd is None


def test_transform_for_distributed_non_create_table(migrator):
    # Test that non-CREATE TABLE statements are left unchanged
    migrator.use_distributed = True
    migrator.replicated = True
    sql = "ALTER TABLE test ADD COLUMN x Int32"

    local_cmd, dist_cmd = migrator._transform_for_distributed(sql)
    assert local_cmd == sql
    assert dist_cmd is None


def test_transform_for_distributed_enabled(migrator):
    # Test full transformation when distributed tables are enabled
    migrator.use_distributed = True
    migrator.replicated = True
    migrator.replicated_cluster = "test_cluster"

    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    local_cmd, dist_cmd = migrator._transform_for_distributed(sql)

    assert "CREATE TABLE test_local (id Int32) ENGINE = MergeTree" == local_cmd
    assert dist_cmd is not None
    assert "CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster" in dist_cmd
    assert (
        "ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())"
        in dist_cmd
    )


def test_execute_migration_command_with_distributed(migrator):
    # Setup
    migrator.use_distributed = True
    migrator.replicated = True
    migrator.replicated_cluster = "test_cluster"
    ch_client = migrator.ch_client
    ch_client.database = "original_db"

    # Execute with non-replicated engine (as it appears in migration files)
    migrator._execute_migration_command(
        "test_db", "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    )

    # Verify - should have called command twice: once for local table, once for distributed
    assert ch_client.command.call_count == 2
    assert ch_client.database == "original_db"  # Should restore original database

    # Check that local table was created with replicated engine and _local suffix
    first_call = ch_client.command.call_args_list[0][0][0]
    assert "test_local" in first_call
    assert "ENGINE = ReplicatedMergeTree" in first_call

    # Check that distributed table was created
    second_call = ch_client.command.call_args_list[1][0][0]
    assert "CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster" in second_call
    assert "ENGINE = Distributed" in second_call


def test_execute_migration_command_with_alter(migrator):
    # Setup
    migrator.replicated = True
    migrator.replicated_cluster = "test_cluster"
    ch_client = migrator.ch_client
    ch_client.database = "original_db"

    # Execute ALTER TABLE command
    migrator._execute_migration_command(
        "test_db", "ALTER TABLE test ADD COLUMN x Int32"
    )

    # Verify - should have called command once with ON CLUSTER added
    assert ch_client.command.call_count == 1
    assert ch_client.database == "original_db"  # Should restore original database

    # Check that ON CLUSTER was added to ALTER TABLE
    call_sql = ch_client.command.call_args_list[0][0][0]
    assert "ALTER TABLE test ON CLUSTER test_cluster ADD COLUMN x Int32" == call_sql


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
    # Test that applying _format_replicated_sql twice doesn't double-apply the Replicated prefix
    migrator.replicated = True

    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    formatted_once = migrator._format_replicated_sql(sql)
    assert "ENGINE = ReplicatedMergeTree" in formatted_once

    # Applying again should not change it
    formatted_twice = migrator._format_replicated_sql(formatted_once)
    assert "ENGINE = ReplicatedMergeTree" in formatted_twice
    assert "ReplicatedReplicatedMergeTree" not in formatted_twice


def test_non_replicated_preserves_table_names(migrator):
    # Test that in non-replicated mode, table names are not changed
    migrator.replicated = False
    migrator.use_distributed = False
    ch_client = migrator.ch_client
    ch_client.database = "original_db"

    # Execute
    migrator._execute_migration_command(
        "test_db", "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    )

    # Verify - should have called command once with original table name
    assert ch_client.command.call_count == 1
    call_sql = ch_client.command.call_args_list[0][0][0]
    assert "CREATE TABLE test (id Int32) ENGINE = MergeTree" == call_sql
    assert "test_local" not in call_sql  # Should NOT have _local suffix
    assert "Distributed" not in call_sql  # Should NOT create distributed table
