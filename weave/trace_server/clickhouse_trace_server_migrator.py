# Clickhouse Trace Server Manager
import logging
import os
import re
from dataclasses import dataclass

from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.costs.insert_costs import insert_costs, should_insert_costs

logger = logging.getLogger(__name__)

# These settings are only used when `replicated` mode is enabled for
# self managed clickhouse instances.
DEFAULT_REPLICATED_PATH = "/clickhouse/tables/{db}"
DEFAULT_REPLICATED_CLUSTER = "weave_cluster"


@dataclass
class DistributedTransformResult:
    """Result of transforming SQL for distributed tables."""

    local_command: str
    distributed_command: str | None


class MigrationError(RuntimeError):
    """Raised when a migration error occurs."""


class ClickHouseTraceServerMigrator:
    ch_client: CHClient
    replicated: bool
    replicated_path: str
    replicated_cluster: str
    use_distributed: bool
    management_db: str

    def __init__(
        self,
        ch_client: CHClient,
        replicated: bool | None = None,
        replicated_path: str | None = None,
        replicated_cluster: str | None = None,
        use_distributed: bool | None = None,
        management_db: str = "db_management",
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
        self.use_distributed = False if use_distributed is None else use_distributed
        self.management_db = management_db

        # Validate configuration
        if self.use_distributed and not self.replicated:
            raise MigrationError(
                "Distributed tables can only be used with replicated tables. "
                "Set replicated=True or use_distributed=False."
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
        # but only if it doesn't already start with "Replicated"
        pattern = r"ENGINE\s*=\s*(\w+)?MergeTree\b"

        def replace_engine(match: re.Match[str]) -> str:
            engine_prefix = match.group(1) or ""
            # Don't add "Replicated" if it's already there
            if engine_prefix.lower().startswith("replicated"):
                return match.group(0)
            return f"ENGINE = Replicated{engine_prefix}MergeTree"

        return re.sub(pattern, replace_engine, sql_query, flags=re.IGNORECASE)

    def _add_on_cluster_to_alter(self, sql_query: str) -> str:
        """Add ON CLUSTER clause to ALTER TABLE statements if replicated mode is enabled."""
        if not self.replicated:
            return sql_query

        # Check if this is an ALTER TABLE statement and doesn't already have ON CLUSTER
        if re.search(r"\bALTER\s+TABLE\b", sql_query, flags=re.IGNORECASE):
            # Don't add if already present
            if re.search(r"\bON\s+CLUSTER\b", sql_query, flags=re.IGNORECASE):
                return sql_query

            # Insert ON CLUSTER after the table name
            # Pattern: ALTER TABLE [table_name] [rest of command]
            pattern = r"(\bALTER\s+TABLE\s+)([a-zA-Z0-9_]+)(\s+)"

            def add_cluster(match: re.Match[str]) -> str:
                return f"{match.group(1)}{match.group(2)} ON CLUSTER {self.replicated_cluster}{match.group(3)}"

            return re.sub(pattern, add_cluster, sql_query, flags=re.IGNORECASE)

        return sql_query

    def _extract_table_name(self, sql_query: str) -> str | None:
        """Extract table name from CREATE TABLE statement."""
        # Match "CREATE TABLE [IF NOT EXISTS] table_name"
        pattern = r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)"
        match = re.search(pattern, sql_query, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _rename_table_to_local(self, sql_query: str, table_name: str) -> str:
        """Rename table in CREATE TABLE statement to table_name_local."""
        # Replace the table name with table_name_local
        pattern = rf"(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?){table_name}\b"
        return re.sub(pattern, rf"\1{table_name}_local", sql_query, flags=re.IGNORECASE)

    def _create_distributed_table_sql(
        self, table_name: str, local_table_name: str
    ) -> str:
        """Generate SQL to create a distributed table on top of a local replicated table."""
        if not self._is_safe_identifier(table_name):
            raise MigrationError(f"Invalid table name: {table_name}")
        if not self._is_safe_identifier(local_table_name):
            raise MigrationError(f"Invalid local table name: {local_table_name}")
        if not self._is_safe_identifier(self.replicated_cluster):
            raise MigrationError(f"Invalid cluster name: {self.replicated_cluster}")

        # Create distributed table that routes to the local tables across the cluster
        distributed_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} ON CLUSTER {self.replicated_cluster}
            AS {local_table_name}_local
            ENGINE = Distributed({self.replicated_cluster}, currentDatabase(), {local_table_name}_local, rand())
        """
        return distributed_sql

    def _transform_for_distributed(self, sql_query: str) -> DistributedTransformResult:
        """Transform SQL to create distributed tables if use_distributed is enabled.

        Returns:
            DistributedTransformResult with local_command and optional distributed_command.
        """
        if not self.use_distributed or not self.replicated:
            return DistributedTransformResult(
                local_command=sql_query, distributed_command=None
            )

        # Check if this is a CREATE TABLE statement
        table_name = self._extract_table_name(sql_query)
        if not table_name:
            return DistributedTransformResult(
                local_command=sql_query, distributed_command=None
            )

        # Rename the table to table_name_local
        local_command = self._rename_table_to_local(sql_query, table_name)

        # Create the distributed table
        distributed_command = self._create_distributed_table_sql(table_name, table_name)

        return DistributedTransformResult(
            local_command=local_command, distributed_command=distributed_command
        )

    def _create_db_sql(self, db_name: str) -> str:
        """Generate SQL database create string for normal and replicated databases."""
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
        self, target_db: str, target_version: int | None = None
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
        self.ch_client.command(self._create_db_sql(self.management_db))
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.management_db}.migrations
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
            SELECT {select_columns} FROM {self.management_db}.migrations WHERE db_name = '{db_name}'
        """
        res = self.ch_client.query(query)
        result_rows = res.result_rows
        if res is None or len(result_rows) == 0:
            self.ch_client.insert(
                f"{self.management_db}.migrations",
                data=[[db_name, 0, None]],
                column_names=column_names,
            )
        res = self.ch_client.query(query)
        result_rows = res.result_rows
        if res is None or len(result_rows) == 0:
            raise MigrationError("Migration table not found")

        return dict(zip(column_names, result_rows[0], strict=False))

    def _get_migrations(
        self,
    ) -> dict[int, dict[str, str | None]]:
        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        migration_files = os.listdir(migration_dir)
        migration_map: dict[int, dict[str, str | None]] = {}
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
        target_version: int | None = None,
    ) -> list[tuple[int, str]]:
        if target_version is None:
            target_version = len(migration_map)
            # Do not run down migrations if not explicitly requesting target_version
            if current_version > target_version:
                logger.warning(
                    f"Found current version ({current_version}) greater than known versions ({len(migration_map)}). Will not run any migrations."
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
            logger.warning(
                f"Automatically running down migrations is disabled and should be done manually. Current version ({current_version}) is greater than target version ({target_version})."
            )
            # res = []
            # for i in range(current_version, target_version, -1):
            #     if migration_map[i]["down"] is None:
            #         raise MigrationError(f"Missing down migration file for version {i}")
            #     res.append((i - 1, f"{migration_map[i]['down']}"))
            # return res

        return []

    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute a single migration command in the context of the target database."""
        command = command.strip()
        if len(command) == 0:
            return
        curr_db = self.ch_client.database
        self.ch_client.database = target_db

        # If not in replicated mode, execute command as-is without any transformations
        if not self.replicated:
            self.ch_client.command(command)
            self.ch_client.database = curr_db
            return

        # Apply replicated transformations
        formatted_command = self._format_replicated_sql(command)
        formatted_command = self._add_on_cluster_to_alter(formatted_command)

        # Then check if we need to create distributed tables
        result = self._transform_for_distributed(formatted_command)

        # Execute the local table creation (or original command if not a CREATE TABLE)
        self.ch_client.command(result.local_command)

        # If we have a distributed table to create, execute that too
        if result.distributed_command:
            self.ch_client.command(result.distributed_command)

        self.ch_client.database = curr_db

    def _update_migration_status(
        self, target_db: str, target_version: int, is_start: bool = True
    ) -> None:
        """Update the migration status in management database migrations table."""
        if is_start:
            self.ch_client.command(
                f"ALTER TABLE {self.management_db}.migrations UPDATE partially_applied_version = {target_version} WHERE db_name = '{target_db}'"
            )
        else:
            self.ch_client.command(
                f"ALTER TABLE {self.management_db}.migrations UPDATE curr_version = {target_version}, partially_applied_version = NULL WHERE db_name = '{target_db}'"
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
