import types
from unittest.mock import Mock, call, patch

import pytest

from weave.trace_server import clickhouse_trace_server_migrator as trace_server_migrator
from weave.trace_server.clickhouse_trace_server_migrator import (
    MigrationError,
    _create_db_sql,
    _create_distributed_table_sql,
    _extract_table_name,
    _format_alter_with_on_cluster_sql,
    _format_distributed_sql,
    _format_replicated_sql,
    _is_safe_identifier,
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
    assert _is_safe_identifier("test_db")
    assert _is_safe_identifier("my_db123")
    assert _is_safe_identifier("db.table")

    # Invalid identifiers
    assert not _is_safe_identifier("test-db")
    assert not _is_safe_identifier("db;")
    assert not _is_safe_identifier("db'name")
    assert not _is_safe_identifier("db/*")


def test_create_db_sql(migrator):
    # Test invalid database name
    with pytest.raises(MigrationError, match="Invalid database name"):
        _create_db_sql("test;db", False, "test_cluster", "/clickhouse/tables/{db}")

    # Test with invalid cluster name
    with pytest.raises(MigrationError, match="Invalid cluster name"):
        _create_db_sql("test_db", True, "test;cluster", "/clickhouse/tables/{db}")

    # Test with invalid replicated path
    with pytest.raises(MigrationError, match="Invalid replicated path"):
        _create_db_sql("test_db", True, "test_cluster", "/clickhouse/bad;path/{db}")

    # Test non-replicated mode
    sql = _create_db_sql("test_db", False, "test_cluster", "/clickhouse/tables/{db}")
    assert sql.strip() == "CREATE DATABASE IF NOT EXISTS test_db"

    # Test replicated mode
    sql = _create_db_sql("test_db", True, "test_cluster", "/clickhouse/tables/{db}")
    expected = """
        CREATE DATABASE IF NOT EXISTS test_db ON CLUSTER test_cluster ENGINE=Replicated('/clickhouse/tables/test_db', '{shard}', '{replica}')
    """.strip()
    assert sql.strip() == expected


def test_format_replicated_sql(migrator):
    # Test that MergeTree engines are converted to Replicated variants
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
        assert _format_replicated_sql(input_sql) == expected_sql

    # Test that non-MergeTree engines are left unchanged
    non_mergetree_cases = [
        "CREATE TABLE test (id Int32) ENGINE = Memory",
        "CREATE TABLE test (id Int32) ENGINE = Log",
        "CREATE TABLE test (id Int32) ENGINE = TinyLog",
        # This should not be changed as it's not a complete word match
        "CREATE TABLE test (id Int32) ENGINE = MyMergeTreeCustom",
    ]

    for sql in non_mergetree_cases:
        assert _format_replicated_sql(sql) == sql


def test_format_alter_with_on_cluster_sql(migrator):
    # Test that ALTER TABLE gets ON CLUSTER added
    cluster_name = "test_cluster"

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
        result = _format_alter_with_on_cluster_sql(input_sql, cluster_name)
        assert result == expected_sql, f"Failed for: {input_sql}"

    # Should not modify if ON CLUSTER already present (idempotent)
    sql_with_cluster = "ALTER TABLE test ON CLUSTER existing_cluster ADD COLUMN x Int32"
    assert (
        _format_alter_with_on_cluster_sql(sql_with_cluster, cluster_name)
        == sql_with_cluster
    )

    # Non-ALTER statements should be left unchanged
    for sql in [
        "CREATE TABLE test (id Int32) ENGINE = MergeTree",
        "INSERT INTO test VALUES (1)",
        "DROP TABLE test",
    ]:
        assert _format_alter_with_on_cluster_sql(sql, cluster_name) == sql


def test_table_name_operations(migrator):
    # Test extracting table names from CREATE TABLE statements
    assert _extract_table_name("CREATE TABLE test (id Int32)") == "test"
    assert (
        _extract_table_name("CREATE TABLE IF NOT EXISTS my_table (id Int32)")
        == "my_table"
    )
    assert _extract_table_name("ALTER TABLE test ADD COLUMN x Int32") is None

    # Test renaming tables to _local suffix
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
    # Test creating distributed table SQL
    cluster_name = "test_cluster"
    sql = _create_distributed_table_sql("test", "test", cluster_name)
    expected = """
        CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster
        AS test_local
        ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())
    """
    assert sql.strip() == expected.strip()


def test_format_distributed_sql(migrator):
    # Test that non-CREATE TABLE statements are unchanged
    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    alter_sql = "ALTER TABLE test ADD COLUMN x Int32"
    cluster_name = "test_cluster"

    result = _format_distributed_sql(alter_sql, cluster_name)
    assert result.local_command == alter_sql
    assert result.distributed_command is None

    # Test full transformation for CREATE TABLE statements
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
    expected_local = "CREATE TABLE test_local (id Int32) ENGINE = ReplicatedMergeTree"
    assert first_call == expected_local

    # Check that distributed table was created
    second_call = ch_client.command.call_args_list[1][0][0]
    expected_distributed = """
        CREATE TABLE IF NOT EXISTS test ON CLUSTER test_cluster
        AS test_local
        ENGINE = Distributed(test_cluster, currentDatabase(), test_local, rand())
    """
    assert second_call.strip() == expected_distributed.strip()


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
    sql = "CREATE TABLE test (id Int32) ENGINE = MergeTree"
    formatted_once = _format_replicated_sql(sql)
    expected = "CREATE TABLE test (id Int32) ENGINE = ReplicatedMergeTree"
    assert formatted_once == expected

    # Applying again should not change it (idempotent)
    formatted_twice = _format_replicated_sql(formatted_once)
    assert formatted_twice == expected


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
