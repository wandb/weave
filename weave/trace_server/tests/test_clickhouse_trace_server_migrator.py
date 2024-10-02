import unittest
from unittest.mock import MagicMock, patch
from clickhouse_connect.driver.client import Client as CHClient

# Import the ClickHouseTraceServerMigrator from its module
from weave.trace_server.clickhouse_trace_server_migrator import (
    ClickHouseTraceServerMigrator,
)


class TestClickHouseTraceServerMigrator(unittest.TestCase):
    def setUp(self):
        # Mock the CHClient
        self.mock_ch_client = MagicMock(spec=CHClient)
        # Instantiate the migrator with the mocked client
        self.migrator = ClickHouseTraceServerMigrator(ch_client=self.mock_ch_client)

    def test_initialize_migration_db(self):
        """Test that the migration database and table are initialized properly."""
        self.migrator._initialize_migration_db()
        self.mock_ch_client.command.assert_any_call(
            """
            CREATE DATABASE IF NOT EXISTS db_management
        """
        )
        self.mock_ch_client.command.assert_any_call(
            """
            CREATE TABLE IF NOT EXISTS db_management.migrations
            (
                db_name String,
                curr_version UInt64,
                partially_applied_version UInt64 NULL,
            )
            ENGINE = MergeTree()
            ORDER BY (db_name)
        """
        )

    def test_get_migration_status_exists(self):
        """Test getting migration status when the entry exists."""
        expected_columns = ["db_name", "curr_version", "partially_applied_version"]
        expected_result = ["test_db", 1, None]
        mock_query_result = MagicMock()
        mock_query_result.result_rows = [expected_result]
        self.mock_ch_client.query.return_value = mock_query_result

        status = self.migrator._get_migration_status("test_db")

        # Normalize SQL queries
        expected_sql = """
            SELECT db_name, curr_version, partially_applied_version FROM db_management.migrations WHERE db_name = 'test_db'
        """
        expected_sql_normalized = " ".join(expected_sql.split())
        actual_sql = self.mock_ch_client.query.call_args[0][0]
        actual_sql_normalized = " ".join(actual_sql.split())

        self.assertEqual(expected_sql_normalized, actual_sql_normalized)
        self.assertEqual(status, dict(zip(expected_columns, expected_result)))

    def test_get_migration_status_not_exists(self):
        """Test getting migration status when the entry does not exist."""
        mock_query_result_empty = MagicMock()
        mock_query_result_empty.result_rows = []

        expected_columns = ["db_name", "curr_version", "partially_applied_version"]
        expected_result = ["test_db", 0, None]
        mock_query_result_after_insert = MagicMock()
        mock_query_result_after_insert.result_rows = [expected_result]

        self.mock_ch_client.query.side_effect = [
            mock_query_result_empty,
            mock_query_result_after_insert,
        ]
        self.mock_ch_client.insert = MagicMock()

        status = self.migrator._get_migration_status("test_db")

        self.mock_ch_client.insert.assert_called_with(
            "db_management.migrations",
            data=[["test_db", 0, None]],
            column_names=expected_columns,
        )
        self.assertEqual(status, dict(zip(expected_columns, expected_result)))

    @patch("os.listdir")
    def test_get_migrations(self, mock_listdir):
        """Test loading migration files."""
        mock_listdir.return_value = [
            "1_init.up.sql",
            "1_init.down.sql",
            "2_add_table.up.sql",
            "2_add_table.down.sql",
        ]
        self.migrator.migration_dir = "migrations"

        with patch("os.path.join") as mock_path_join:
            # Mock os.path.join to return the correct paths
            def side_effect(*args):
                return "/".join(args)

            mock_path_join.side_effect = side_effect

            migration_map = self.migrator._get_migrations()

        expected_migration_map = {
            1: {"up": "1_init.up.sql", "down": "1_init.down.sql"},
            2: {"up": "2_add_table.up.sql", "down": "2_add_table.down.sql"},
        }
        self.assertEqual(migration_map, expected_migration_map)

    def test_determine_migrations_to_apply_upgrade(self):
        """Test determining migrations to apply for an upgrade."""
        migration_map = {
            1: {"up": "1_init.up.sql", "down": "1_init.down.sql"},
            2: {"up": "2_add_table.up.sql", "down": "2_add_table.down.sql"},
            3: {"up": "3_update_table.up.sql", "down": "3_update_table.down.sql"},
        }
        current_version = 1
        target_version = 3

        migrations_to_apply = self.migrator._determine_migrations_to_apply(
            current_version=current_version,
            migration_map=migration_map,
            target_version=target_version,
        )

        expected_migrations = [
            (2, "2_add_table.up.sql"),
            (3, "3_update_table.up.sql"),
        ]
        self.assertEqual(migrations_to_apply, expected_migrations)

    def test_determine_migrations_to_apply_downgrade(self):
        """Test determining migrations to apply for a downgrade."""
        migration_map = {
            1: {"up": "1_init.up.sql", "down": "1_init.down.sql"},
            2: {"up": "2_add_table.up.sql", "down": "2_add_table.down.sql"},
            3: {"up": "3_update_table.up.sql", "down": "3_update_table.down.sql"},
        }
        current_version = 3
        target_version = 1

        migrations_to_apply = self.migrator._determine_migrations_to_apply(
            current_version=current_version,
            migration_map=migration_map,
            target_version=target_version,
        )

        expected_migrations = [
            (2, "3_update_table.down.sql"),
            (1, "2_add_table.down.sql"),
        ]
        self.assertEqual(migrations_to_apply, expected_migrations)

    @patch.object(ClickHouseTraceServerMigrator, "_apply_migration")
    @patch.object(ClickHouseTraceServerMigrator, "_determine_migrations_to_apply")
    @patch.object(ClickHouseTraceServerMigrator, "_get_migrations")
    @patch.object(ClickHouseTraceServerMigrator, "_get_migration_status")
    def test_apply_migrations(
        self,
        mock_get_status,
        mock_get_migrations,
        mock_determine_migrations,
        mock_apply_migration,
    ):
        """Test applying migrations when there are migrations to apply."""
        mock_get_status.return_value = {
            "db_name": "test_db",
            "curr_version": 1,
            "partially_applied_version": None,
        }
        mock_get_migrations.return_value = {
            1: {"up": "1_init.up.sql", "down": "1_init.down.sql"},
            2: {"up": "2_add_table.up.sql", "down": "2_add_table.down.sql"},
        }
        mock_determine_migrations.return_value = [(2, "2_add_table.up.sql")]

        self.migrator.apply_migrations(target_db="test_db")

        mock_apply_migration.assert_called_with(
            "test_db", 2, "2_add_table.up.sql", None
        )

    @patch("weave.trace_server.clickhouse_trace_server_migrator.logger")
    @patch.object(ClickHouseTraceServerMigrator, "_apply_migration")
    @patch.object(ClickHouseTraceServerMigrator, "_determine_migrations_to_apply")
    @patch.object(ClickHouseTraceServerMigrator, "_get_migrations")
    @patch.object(ClickHouseTraceServerMigrator, "_get_migration_status")
    def test_apply_migrations_no_migrations(
        self,
        mock_get_status,
        mock_get_migrations,
        mock_determine_migrations,
        mock_apply_migration,
        mock_logger,
    ):
        """Test applying migrations when there are no migrations to apply."""
        mock_get_status.return_value = {
            "db_name": "test_db",
            "curr_version": 2,
            "partially_applied_version": None,
        }
        mock_get_migrations.return_value = {
            1: {"up": "1_init.up.sql", "down": "1_init.down.sql"},
            2: {"up": "2_add_table.up.sql", "down": "2_add_table.down.sql"},
        }
        mock_determine_migrations.return_value = []

        self.migrator.apply_migrations(target_db="test_db")

        mock_apply_migration.assert_not_called()
        mock_logger.info.assert_any_call("No migrations to apply to `test_db`")

    @patch(
        "builtins.open",
        new_callable=unittest.mock.mock_open,
        read_data="CREATE TABLE test; INSERT INTO test VALUES (1);",
    )
    def test_apply_migration(self, mock_open):
        """Test applying a single migration."""
        self.mock_ch_client.command = MagicMock()
        self.migrator.migration_dir = "migrations"

        with patch("os.path.join") as mock_path_join:
            # Mock os.path.join to return the correct paths
            def side_effect(*args):
                return "/".join(args)

            mock_path_join.side_effect = side_effect

            self.migrator._apply_migration(
                target_db="test_db",
                target_version=1,
                migration_file="1_init.up.sql",
                target_db_migration_alias=None,
            )

        # Normalize expected SQL commands
        expected_sql_1 = """
            ALTER TABLE db_management.migrations UPDATE partially_applied_version = 1 WHERE db_name = 'test_db'
        """
        expected_sql_1_normalized = " ".join(expected_sql_1.split())

        expected_sql_2 = """
            ALTER TABLE db_management.migrations UPDATE curr_version = 1, partially_applied_version = NULL WHERE db_name = 'test_db'
        """
        expected_sql_2_normalized = " ".join(expected_sql_2.split())

        # Extract actual SQL commands from mock calls and normalize
        actual_calls = [
            call_args[0][0] for call_args in self.mock_ch_client.command.call_args_list
        ]
        actual_sql_normalized = [" ".join(sql.split()) for sql in actual_calls]

        self.assertIn(expected_sql_1_normalized, actual_sql_normalized)
        self.assertIn(expected_sql_2_normalized, actual_sql_normalized)

        # Check that the migration SQL commands were executed
        expected_migration_calls = [
            unittest.mock.call("CREATE TABLE test"),
            unittest.mock.call("INSERT INTO test VALUES (1)"),
        ]
        self.mock_ch_client.command.assert_has_calls(
            expected_migration_calls, any_order=False
        )

    @patch("weave.trace_server.clickhouse_trace_server_migrator.logger")
    @patch.object(ClickHouseTraceServerMigrator, "_apply_migration")
    @patch.object(ClickHouseTraceServerMigrator, "_determine_migrations_to_apply")
    @patch.object(ClickHouseTraceServerMigrator, "_get_migrations")
    @patch.object(ClickHouseTraceServerMigrator, "_get_migration_status")
    def test_apply_migrations_partially_applied(
        self,
        mock_get_status,
        mock_get_migrations,
        mock_determine_migrations,
        mock_apply_migration,
        mock_logger,
    ):
        """Test applying migrations when there is a partially applied version."""
        mock_get_status.return_value = {
            "db_name": "test_db",
            "curr_version": 1,
            "partially_applied_version": 2,
        }

        self.migrator.apply_migrations(target_db="test_db")

        mock_apply_migration.assert_not_called()
        mock_logger.info.assert_any_call(
            "Unable to apply migrations to `test_db`. Found partially applied migration version 2. Please fix the database manually and try again."
        )

    def test_determine_migrations_to_apply_invalid_target(self):
        """Test determining migrations to apply with an invalid target version."""
        migration_map = {
            1: {"up": "1_init.up.sql", "down": "1_init.down.sql"},
            2: {"up": "2_add_table.up.sql", "down": "2_add_table.down.sql"},
        }
        current_version = 1
        target_version = 3

        with self.assertRaises(Exception) as context:
            self.migrator._determine_migrations_to_apply(
                current_version=current_version,
                migration_map=migration_map,
                target_version=target_version,
            )
        self.assertTrue("Invalid target version" in str(context.exception))

    @patch.object(ClickHouseTraceServerMigrator, "_apply_migration")
    @patch("weave.trace_server.clickhouse_trace_server_migrator.os.listdir")
    @patch("weave.trace_server.clickhouse_trace_server_migrator.os.path.join")
    @patch.object(ClickHouseTraceServerMigrator, "_get_migration_status")
    def test_apply_migrations_with_alias_and_custom_migration_dir(
        self,
        mock_get_migration_status,
        mock_path_join,
        mock_listdir,
        mock_apply_migration,
    ):
        """
        Test applying migrations with a custom migration directory and target_db_migration_alias.
        This is how we run the migrations for the costs table.
        """
        # Set up the migration directory and alias
        custom_migration_dir = "costs/migrations"
        target_db_alias = "costs"
        target_db = "test_db"

        # Instantiate the migrator with the custom migration directory
        self.migrator = ClickHouseTraceServerMigrator(
            ch_client=self.mock_ch_client,
            migration_dir=custom_migration_dir,
        )

        # Mock the migration status
        mock_get_migration_status.return_value = {
            "db_name": target_db_alias,
            "curr_version": 0,
            "partially_applied_version": None,
        }

        # Mock os.path.join to correctly handle the custom migration directory
        def mock_join(*args):
            return "/".join(args)

        mock_path_join.side_effect = mock_join

        # Mock os.listdir to return a set of migration files
        mock_listdir.return_value = [
            "1_create_table.up.sql",
            "1_create_table.down.sql",
            "2_add_column.up.sql",
            "2_add_column.down.sql",
        ]

        # Prepare the migration map
        expected_migration_map = {
            1: {"up": "1_create_table.up.sql", "down": "1_create_table.down.sql"},
            2: {"up": "2_add_column.up.sql", "down": "2_add_column.down.sql"},
        }

        # Patch the _get_migrations method to use the expected migration map
        with patch.object(
            ClickHouseTraceServerMigrator,
            "_get_migrations",
            return_value=expected_migration_map,
        ):
            # Mock the _determine_migrations_to_apply method
            with patch.object(
                ClickHouseTraceServerMigrator,
                "_determine_migrations_to_apply",
                return_value=[
                    (1, "1_create_table.up.sql"),
                    (2, "2_add_column.up.sql"),
                ],
            ) as mock_determine_migrations:
                # Call apply_migrations with the alias
                self.migrator.apply_migrations(
                    target_db=target_db,
                    target_db_migration_alias=target_db_alias,
                )

                # Assertions
                # Check that _get_migration_status was called with the alias
                mock_get_migration_status.assert_called_with(target_db_alias)

                # Check that _determine_migrations_to_apply was called with correct parameters
                mock_determine_migrations.assert_called_with(
                    0, expected_migration_map, None
                )

                # Check that _apply_migration was called twice with correct arguments
                expected_calls = [
                    unittest.mock.call(
                        target_db,
                        1,
                        "1_create_table.up.sql",
                        target_db_alias,
                    ),
                    unittest.mock.call(
                        target_db,
                        2,
                        "2_add_column.up.sql",
                        target_db_alias,
                    ),
                ]
                mock_apply_migration.assert_has_calls(expected_calls, any_order=False)


if __name__ == "__main__":
    unittest.main()
