# Clickhouse Trace Server Manager
import logging
import os
import re
from typing import Optional

from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.costs.insert_costs import insert_costs, should_insert_costs

logger = logging.getLogger(__name__)

# These settings are only used when `replicated` mode is enabled for
# self managed clickhouse instances.
DEFAULT_REPLICATED_PATH = "/clickhouse/tables/{db}"
DEFAULT_REPLICATED_CLUSTER = "weave_cluster"


class MigrationError(RuntimeError):
    """Raised when a migration error occurs."""


class ClickHouseTraceServerMigrator:
    ch_client: CHClient
    replicated: bool
    replicated_path: str
    replicated_cluster: str

    def __init__(
        self,
        ch_client: CHClient,
        replicated: Optional[bool] = None,
        replicated_path: Optional[str] = None,
        replicated_cluster: Optional[str] = None,
    ):
        super().__init__()
        self.ch_client = ch_client
        self.replicated = False if replicated is None else replicated
        self.replicated_path = (
            DEFAULT_REPLICATED_PATH if replicated_path is None else replicated_path
        )
        self.replicated_cluster = (
            DEFAULT_REPLICATED_CLUSTER
            if replicated_cluster is None
            else replicated_cluster
        )
        self._initialize_migration_db()

    def _is_safe_identifier(self, value: str) -> bool:
        """Check if a string is safe to use as an identifier in SQL."""
        return bool(re.match(r"^[a-zA-Z0-9_\.]+$", value))

    def _format_replicated_sql(self, sql_query: str) -> str:
        """Format SQL query to use replicated engines if replicated mode is enabled."""
        if not self.replicated:
            return sql_query

        # Match "ENGINE = <optional words>MergeTree" followed by word boundary
        pattern = r"ENGINE\s*=\s*(\w+)?MergeTree\b"

        def replace_engine(match: re.Match[str]) -> str:
            engine_prefix = match.group(1) or ""
            return f"ENGINE = Replicated{engine_prefix}MergeTree"

        return re.sub(pattern, replace_engine, sql_query, flags=re.IGNORECASE)

    def _create_db_sql(self, db_name: str) -> str:
        """Geneate SQL database create string for normal and replicated databases."""
        if not self._is_safe_identifier(db_name):
            raise MigrationError(f"Invalid database name: {db_name}")

        replicated_engine = ""
        replicated_cluster = ""
        if self.replicated:
            if not self._is_safe_identifier(self.replicated_cluster):
                raise MigrationError(f"Invalid cluster name: {self.replicated_cluster}")

            replicated_path = self.replicated_path.replace("{db}", db_name)
            if not all(
                self._is_safe_identifier(part)
                for part in replicated_path.split("/")
                if part
            ):
                raise MigrationError(f"Invalid replicated path: {replicated_path}")

            replicated_cluster = f" ON CLUSTER {self.replicated_cluster}"
            replicated_engine = (
                f" ENGINE=Replicated('{replicated_path}', '{{shard}}', '{{replica}}')"
            )

        create_db_sql = f"""
            CREATE DATABASE IF NOT EXISTS {db_name}{replicated_cluster}{replicated_engine}
        """
        return create_db_sql

    def apply_migrations(
        self, target_db: str, target_version: Optional[int] = None
    ) -> None:
        status = self._get_migration_status(target_db)
        logger.info(f"""`{target_db}` migration status: {status}""")
        if status["partially_applied_version"]:
            logger.info(
                f"Unable to apply migrations to `{target_db}`. Found partially applied migration version {status['partially_applied_version']}. Please fix the database manually and try again."
            )
            return
        migration_map = self._get_migrations()
        migrations_to_apply = self._determine_migrations_to_apply(
            status["curr_version"], migration_map, target_version
        )
        if len(migrations_to_apply) == 0:
            logger.info(f"No migrations to apply to `{target_db}`")
            if should_insert_costs(status["curr_version"], target_version):
                insert_costs(self.ch_client, target_db)
            return
        logger.info(f"Migrations to apply: {migrations_to_apply}")
        if status["curr_version"] == 0:
            self.ch_client.command(self._create_db_sql(target_db))
        for target_version, migration_file in migrations_to_apply:
            self._apply_migration(target_db, target_version, migration_file)
        if should_insert_costs(status["curr_version"], target_version):
            insert_costs(self.ch_client, target_db)

    def _initialize_migration_db(self) -> None:
        self.ch_client.command(self._create_db_sql("db_management"))
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS db_management.migrations
            (
                db_name String,
                curr_version UInt64,
                partially_applied_version UInt64 NULL,
            )
            ENGINE = MergeTree()
            ORDER BY (db_name)
        """
        self.ch_client.command(self._format_replicated_sql(create_table_sql))

    def _get_migration_status(self, db_name: str) -> dict:
        column_names = ["db_name", "curr_version", "partially_applied_version"]
        select_columns = ", ".join(column_names)
        query = f"""
            SELECT {select_columns} FROM db_management.migrations WHERE db_name = '{db_name}'
        """
        res = self.ch_client.query(query)
        result_rows = res.result_rows
        if res is None or len(result_rows) == 0:
            self.ch_client.insert(
                "db_management.migrations",
                data=[[db_name, 0, None]],
                column_names=column_names,
            )
        res = self.ch_client.query(query)
        result_rows = res.result_rows
        if res is None or len(result_rows) == 0:
            raise MigrationError("Migration table not found")

        return dict(zip(column_names, result_rows[0]))

    def _get_migrations(
        self,
    ) -> dict[int, dict[str, Optional[str]]]:
        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        migration_files = os.listdir(migration_dir)
        migration_map: dict[int, dict[str, Optional[str]]] = {}
        max_version = 0
        for file in migration_files:
            if not file.endswith(".up.sql") and not file.endswith(".down.sql"):
                raise MigrationError(f"Invalid migration file: {file}")
            file_name_parts = file.split("_", 1)
            if len(file_name_parts) <= 1:
                raise MigrationError(f"Invalid migration file: {file}")
            version = int(file_name_parts[0], 10)
            if version < 1:
                raise MigrationError(f"Invalid migration file: {file}")

            is_up = file.endswith(".up.sql")

            if version not in migration_map:
                migration_map[version] = {"up": None, "down": None}

            if is_up:
                if migration_map[version]["up"] is not None:
                    raise MigrationError(
                        f"Duplicate migration file for version {version}"
                    )
                migration_map[version]["up"] = file
            else:
                if migration_map[version]["down"] is not None:
                    raise MigrationError(
                        f"Duplicate migration file for version {version}"
                    )
                migration_map[version]["down"] = file

            if version > max_version:
                max_version = version

        if len(migration_map) == 0:
            raise MigrationError("No migrations found")

        if max_version != len(migration_map):
            raise MigrationError(
                f"Invalid migration versioning. Expected {max_version} migrations but found {len(migration_map)}"
            )

        for version in range(1, max_version + 1):
            if version not in migration_map:
                raise MigrationError(f"Missing migration file for version {version}")
            if migration_map[version]["up"] is None:
                raise MigrationError(f"Missing up migration file for version {version}")
            if migration_map[version]["down"] is None:
                raise MigrationError(
                    f"Missing down migration file for version {version}"
                )

        return migration_map

    def _determine_migrations_to_apply(
        self,
        current_version: int,
        migration_map: dict,
        target_version: Optional[int] = None,
    ) -> list[tuple[int, str]]:
        if target_version is None:
            target_version = len(migration_map)
            # Do not run down migrations if not explicitly requesting target_version
            if current_version > target_version:
                logger.warning(
                    f"NOT running down migration from {current_version} to {target_version}"
                )
                return []
        if target_version < 0 or target_version > len(migration_map):
            raise MigrationError(f"Invalid target version: {target_version}")

        if target_version > current_version:
            res = []
            for i in range(current_version + 1, target_version + 1):
                if migration_map[i]["up"] is None:
                    raise MigrationError(f"Missing up migration file for version {i}")
                res.append((i, f"{migration_map[i]['up']}"))
            return res
        if target_version < current_version:
            res = []
            for i in range(current_version, target_version, -1):
                if migration_map[i]["down"] is None:
                    raise MigrationError(f"Missing down migration file for version {i}")
                res.append((i - 1, f"{migration_map[i]['down']}"))
            return res

        return []

    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute a single migration command in the context of the target database."""
        command = command.strip()
        if len(command) == 0:
            return
        curr_db = self.ch_client.database
        self.ch_client.database = target_db
        self.ch_client.command(self._format_replicated_sql(command))
        self.ch_client.database = curr_db

    def _update_migration_status(
        self, target_db: str, target_version: int, is_start: bool = True
    ) -> None:
        """Update the migration status in db_management.migrations table."""
        if is_start:
            self.ch_client.command(
                f"ALTER TABLE db_management.migrations UPDATE partially_applied_version = {target_version} WHERE db_name = '{target_db}'"
            )
        else:
            self.ch_client.command(
                f"ALTER TABLE db_management.migrations UPDATE curr_version = {target_version}, partially_applied_version = NULL WHERE db_name = '{target_db}'"
            )

    def _apply_migration(
        self, target_db: str, target_version: int, migration_file: str
    ) -> None:
        logger.info(f"Applying migration {migration_file} to `{target_db}`")
        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        migration_file_path = os.path.join(migration_dir, migration_file)

        with open(migration_file_path) as f:
            migration_sql = f.read()

        # Mark migration as partially applied
        self._update_migration_status(target_db, target_version, is_start=True)

        # Execute each command in the migration
        migration_sub_commands = migration_sql.split(";")
        for command in migration_sub_commands:
            self._execute_migration_command(target_db, command)

        # Mark migration as fully applied
        self._update_migration_status(target_db, target_version, is_start=False)

        logger.info(f"Migration {migration_file} applied to `{target_db}`")
