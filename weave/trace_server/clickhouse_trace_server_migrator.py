# Clickhouse Trace Server Manager

"""Differences between cloud, replicated, and distributed modes:

## Cloud Mode (replicated=False, use_distributed=False)
- Single-node ClickHouse deployment managed by cloud provider (e.g., ClickHouse Cloud)
- All SQL commands executed as-is without transformation

## Replicated Mode (replicated=True, use_distributed=False)
- Multi-node ClickHouse cluster with automatic replication
- Tables have 'Replicated' prepended to MergeTree engine with ZooKeeper coordination
- All DDL statements include `ON CLUSTER {cluster_name}` for cluster-wide execution

## Distributed Mode (replicated=True, use_distributed=True)
- Extends replicated mode with sharding and distributed query capabilities
- Requires replicated mode as foundation (distributed tables reference local replicated tables)
- Two-tier table structure:
  - Local tables (`table_name_local`): ReplicatedMergeTree, store actual data on each shard
  - Distributed tables (`table_name`): Distributed engine, query router across all shards
- All DDL statements include `ON CLUSTER {cluster_name}`

### Distributed Mode Special Handling:

**CREATE TABLE:**
  - Creates `table_name_local` (ReplicatedMergeTree on each node)
  - Creates `table_name` (Distributed table pointing to `table_name_local`)

**ALTER TABLE (regular columns):**
  - Alters both `table_name_local` AND `table_name` (both need schema updates)

**ALTER TABLE ADD/DROP INDEX:**
  - Only alters `table_name_local` (distributed tables don't support indexes)
  - Skips altering the distributed table

**ALTER TABLE DELETE/UPDATE (mutations):**
  - Only alters `table_name_local` (distributed tables don't support mutations)
  - Skips altering the distributed table

**ALTER TABLE ... MODIFY QUERY (materialized views):**
  - Uses DROP/CREATE pattern instead of ALTER
  - Drops `view_name_local` ON CLUSTER
  - Creates `view_name_local` ON CLUSTER with `TO target_table_local`
  - All `FROM` clauses and qualified column references renamed to `_local` suffix

**CREATE VIEW and CREATE MATERIALIZED VIEW:**
  - Only adds `ON CLUSTER` clause (views are metadata-only, no local/distributed split)
  - Note: In distributed mode, materialized views from initial CREATE statements should reference
    base tables (not _local), as the migrator doesn't transform initial CREATE statements

**DROP TABLE:**
  - Drops both `table_name_local` AND `table_name`
  - Ensures complete cleanup of both local and distributed tables

**DROP VIEW:**
  - Only adds `ON CLUSTER` clause (views are metadata-only, no local/distributed split)
  - Works identically to replicated mode
  - Note: For materialized views that were modified via ALTER TABLE MODIFY QUERY,
    you must drop the `_local` version explicitly (e.g., `DROP VIEW view_name_local`)

**MATERIALIZE commands:**
  - Skipped entirely (not supported by distributed tables)
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from re import Pattern

from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.costs.insert_costs import insert_costs, should_insert_costs

logger = logging.getLogger(__name__)

# These settings are only used when `replicated` mode is enabled for
# self managed clickhouse instances.
DEFAULT_REPLICATED_PATH = "/clickhouse/tables/{db}"
DEFAULT_REPLICATED_CLUSTER = "weave_cluster"

# Constants for table naming conventions
VIEW_SUFFIX = "_view"


class BaseClickHouseTraceServerMigrator(ABC):
    """Base class for ClickHouse trace server migration strategies.

    This abstract base class defines the common interface and shared logic for
    migrating ClickHouse databases across different deployment modes (cloud,
    replicated, and distributed).
    """

    ch_client: CHClient
    management_db: str

    def __init__(
        self,
        ch_client: CHClient,
        management_db: str = "db_management",
    ):
        super().__init__()
        self.ch_client = ch_client
        self.management_db = management_db
        self._initialize_migration_db()

    @abstractmethod
    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute a single migration command (to be implemented by subclasses)."""
        pass

    @abstractmethod
    def _create_management_table_sql(self) -> str:
        """Generate SQL to create the management table (to be implemented by subclasses)."""
        pass

    @abstractmethod
    def _create_db_sql(self, db_name: str) -> str:
        """Generate SQL to create a database (to be implemented by subclasses)."""
        pass

    def apply_migrations(
        self, target_db: str, target_version: int | None = None
    ) -> None:
        """Apply migrations to the target database up to the specified version.

        Args:
            target_db: The database to migrate
            target_version: The target version to migrate to (None = latest)
        """
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
            db_sql = self._create_db_sql(target_db)
            self.ch_client.command(db_sql)
        for target_version, migration_file in migrations_to_apply:
            self._apply_migration(target_db, target_version, migration_file)
        if should_insert_costs(status["curr_version"], target_version):
            insert_costs(self.ch_client, target_db)

    def _initialize_migration_db(self) -> None:
        """Initialize the management database and migrations table."""
        db_sql = self._create_db_sql(self.management_db)
        self.ch_client.command(db_sql)

        create_table_sql = self._create_management_table_sql()
        self.ch_client.command(create_table_sql)

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

    def _update_migration_status(
        self, target_db: str, target_version: int, is_start: bool = True
    ) -> None:
        """Update the migration status in management database migrations table."""
        if is_start:
            command = f"ALTER TABLE {self.management_db}.migrations UPDATE partially_applied_version = {target_version} WHERE db_name = '{target_db}'"
            self.ch_client.command(command)
        else:
            command = f"ALTER TABLE {self.management_db}.migrations UPDATE curr_version = {target_version}, partially_applied_version = NULL WHERE db_name = '{target_db}'"
            self.ch_client.command(command)

    @staticmethod
    def _is_safe_identifier(value: str) -> bool:
        """Check if a string is safe to use as an identifier in SQL."""
        return bool(SQLPatterns.SAFE_IDENTIFIER.match(value))


class CloudClickHouseTraceServerMigrator(BaseClickHouseTraceServerMigrator):
    """Migrator for single-node ClickHouse Cloud deployments.

    SQL commands are executed as-is without transformation.
    """

    def _create_db_sql(self, db_name: str) -> str:
        """Generate SQL to create a database in cloud mode."""
        if not self._is_safe_identifier(db_name):
            raise MigrationError(f"Invalid database name: {db_name}")
        return f"CREATE DATABASE IF NOT EXISTS {db_name}"

    def _create_management_table_sql(self) -> str:
        """Generate SQL to create the management table in cloud mode."""
        return f"""
            CREATE TABLE IF NOT EXISTS {self.management_db}.migrations
            (
                db_name String,
                curr_version UInt64,
                partially_applied_version UInt64 NULL,
            )
            ENGINE = MergeTree()
            ORDER BY (db_name)
        """

    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute command in cloud mode (no transformations)."""
        command = command.strip()
        if len(command) == 0:
            return

        curr_db = self.ch_client.database
        self.ch_client.database = target_db
        self.ch_client.command(command)
        self.ch_client.database = curr_db


class ReplicatedClickHouseTraceServerMigrator(BaseClickHouseTraceServerMigrator):
    """Migrator for replicated ClickHouse deployments.

    In replicated mode:
    - Tables use ReplicatedMergeTree engines with ZooKeeper coordination
    - All DDL statements include `ON CLUSTER {cluster_name}`
    """

    replicated_path: str
    replicated_cluster: str

    def __init__(
        self,
        ch_client: CHClient,
        replicated_path: str | None = None,
        replicated_cluster: str | None = None,
        management_db: str = "db_management",
    ):
        self.replicated_path = (
            DEFAULT_REPLICATED_PATH if replicated_path is None else replicated_path
        )
        self.replicated_cluster = (
            DEFAULT_REPLICATED_CLUSTER
            if replicated_cluster is None
            else replicated_cluster
        )

        # Validate configuration
        if not self._is_safe_identifier(self.replicated_cluster):
            raise MigrationError(f"Invalid cluster name: {self.replicated_cluster}")

        logger.info(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
            f"ReplicatedClickHouseTraceServerMigrator initialized with: "
            f"replicated_cluster={self.replicated_cluster}, "
            f"replicated_path={self.replicated_path}, "
            f"management_db={management_db}"
        )

        super().__init__(ch_client, management_db)

    def _create_db_sql(self, db_name: str) -> str:
        """Generate SQL to create a database in replicated mode."""
        if not self._is_safe_identifier(db_name):
            raise MigrationError(f"Invalid database name: {db_name}")
        return f"CREATE DATABASE IF NOT EXISTS {db_name} ON CLUSTER {self.replicated_cluster}"

    def _create_management_table_sql(self) -> str:
        """Generate SQL to create the management table in replicated mode."""
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
        create_table_sql = self._format_replicated_sql(create_table_sql)
        create_table_sql = self._add_on_cluster_clause(create_table_sql)
        return create_table_sql

    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute command in replicated mode."""
        command = command.strip()
        if len(command) == 0:
            return

        curr_db = self.ch_client.database
        self.ch_client.database = target_db

        # Format for replicated tables
        formatted_command = self._format_replicated_sql(command)
        formatted_command = self._add_on_cluster_clause(formatted_command)

        self.ch_client.command(formatted_command)
        self.ch_client.database = curr_db

    def _format_replicated_sql(self, sql_query: str) -> str:
        """Format SQL query to use replicated engines."""

        def replace_engine(match: re.Match[str]) -> str:
            engine_prefix = match.group(1) or ""
            if engine_prefix.lower().startswith("replicated"):
                return match.group(0)
            return f"ENGINE = Replicated{engine_prefix}MergeTree"

        return SQLPatterns.MERGETREE_ENGINE.sub(replace_engine, sql_query)

    def _add_on_cluster_clause(self, sql_query: str) -> str:
        """Add ON CLUSTER clause to DDL statements if not present."""
        if SQLPatterns.ON_CLUSTER.search(sql_query):
            return sql_query

        # ALTER TABLE
        if SQLPatterns.ALTER_TABLE_STMT.search(sql_query):
            return SQLPatterns.ALTER_TABLE_NAME_PATTERN.sub(
                lambda m: f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}",
                sql_query,
            )

        # CREATE TABLE
        if SQLPatterns.CREATE_TABLE_STMT.search(sql_query):
            return SQLPatterns.CREATE_TABLE_NAME_PATTERN.sub(
                lambda m: f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}",
                sql_query,
            )

        # DROP VIEW
        if SQLPatterns.DROP_VIEW_STMT.search(sql_query):
            return SQLPatterns.DROP_VIEW_NAME_PATTERN.sub(
                lambda m: f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}",
                sql_query,
            )

        # CREATE VIEW / CREATE MATERIALIZED VIEW
        if SQLPatterns.CREATE_VIEW_STMT.search(sql_query):
            return SQLPatterns.CREATE_VIEW_NAME_PATTERN.sub(
                lambda m: f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}",
                sql_query,
            )

        return sql_query


@dataclass
class DistributedTransformResult:
    """Result of transforming SQL for distributed tables."""

    local_command: str
    distributed_command: str | None


class DistributedClickHouseTraceServerMigrator(ReplicatedClickHouseTraceServerMigrator):
    """Migrator for distributed ClickHouse deployments with sharding.

    In distributed mode (extends replicated mode):
    - Two-tier table structure:
      * Local tables (`table_name_local`): ReplicatedMergeTree, store actual data on each shard
      * Distributed tables (`table_name`): Distributed engine, query router across shards
    - Special handling for:
      * CREATE TABLE: creates both local and distributed tables
      * ALTER TABLE: differentiates between columns (both tables) and indexes/mutations (local only)
      * Materialized views: DROP/CREATE pattern with `_local` suffix renaming
      * DROP operations: drops both versions
    """

    def __init__(
        self,
        ch_client: CHClient,
        replicated_path: str | None = None,
        replicated_cluster: str | None = None,
        management_db: str = "db_management",
    ):
        logger.info(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
            f"DistributedClickHouseTraceServerMigrator initialized"
        )
        super().__init__(ch_client, replicated_path, replicated_cluster, management_db)

    def _create_management_table_sql(self) -> str:
        """Generate SQL to create the management table in distributed mode.

        Unlike data tables (which use {shard} in the ZK path to separate data per shard),
        the management table uses a shared path so all nodes replicate the same state.
        We use {shard}-{replica} for the replica ID since {replica} alone repeats across shards.
        """
        return f"""
            CREATE TABLE IF NOT EXISTS {self.management_db}.migrations ON CLUSTER {self.replicated_cluster}
            (
                db_name String,
                curr_version UInt64,
                partially_applied_version UInt64 NULL,
            )
            ENGINE = ReplicatedMergeTree('/clickhouse/tables/shared/{self.management_db}/migrations', '{{shard}}-{{replica}}')
            ORDER BY (db_name)
        """

    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute command in distributed mode."""
        command = command.strip()
        if len(command) == 0:
            return

        curr_db = self.ch_client.database
        self.ch_client.database = target_db

        # Skip MATERIALIZE commands (not supported by distributed tables)
        if SQLPatterns.MATERIALIZE.search(command):
            logger.warning(
                f"Skipping MATERIALIZE command (not supported in distributed mode): {command}"
            )
            self.ch_client.database = curr_db
            return

        # Handle CREATE/DROP VIEW (no local/distributed split, just add ON CLUSTER)
        if SQLPatterns.CREATE_VIEW_STMT.search(
            command
        ) or SQLPatterns.DROP_VIEW_STMT.search(command):
            formatted_command = self._format_replicated_sql(command)
            formatted_command = self._add_on_cluster_clause(formatted_command)
            self.ch_client.command(formatted_command)
            self.ch_client.database = curr_db
            return

        # Format for replicated tables with distributed-specific paths
        formatted_command = self._format_replicated_sql_distributed(command, target_db)

        # Handle ALTER TABLE
        if SQLPatterns.ALTER_TABLE_STMT.search(formatted_command):
            self._execute_distributed_alter(formatted_command)
        else:
            # Handle CREATE TABLE and other DDL
            self._execute_distributed_ddl(formatted_command)

        self.ch_client.database = curr_db

    def _format_replicated_sql_distributed(self, sql_query: str, target_db: str) -> str:
        """Format SQL query to use replicated engines with explicit paths for distributed mode."""

        def replace_engine(match: re.Match[str]) -> str:
            engine_prefix = match.group(1) or ""
            if engine_prefix.lower().startswith("replicated"):
                return match.group(0)

            # Extract table name for path
            table_match = SQLPatterns.CREATE_TABLE.search(sql_query)
            if table_match:
                table_name = table_match.group(1)
                if "." in table_name:
                    table_name = table_name.split(".")[-1]
                # Use _local suffix in the path for distributed tables
                local_table_name = table_name + ch_settings.LOCAL_TABLE_SUFFIX
                return f"ENGINE = Replicated{engine_prefix}MergeTree('/clickhouse/tables/{{shard}}/{target_db}/{local_table_name}', '{{replica}}')"

            return f"ENGINE = Replicated{engine_prefix}MergeTree"

        return SQLPatterns.MERGETREE_ENGINE.sub(replace_engine, sql_query)

    def _execute_distributed_alter(self, command: str) -> None:
        """Execute ALTER TABLE in distributed mode."""
        # Materialized view modification (MODIFY QUERY)
        if SQLPatterns.MODIFY_QUERY.search(command):
            self._execute_materialized_view_alter(command)
            return

        # Operations that only apply to local tables
        if self._is_local_only_operation(command):
            self._execute_local_table_operation(command)
            return

        # Regular ALTER: apply to both local and distributed tables
        local_command = self._rename_alter_table_to_local(command)
        local_command = self._add_on_cluster_clause(local_command)
        self.ch_client.command(local_command)

        distributed_command = self._add_on_cluster_clause(command)
        self.ch_client.command(distributed_command)

    def _execute_materialized_view_alter(self, command: str) -> None:
        """Handle ALTER TABLE MODIFY QUERY for materialized views in distributed mode."""
        view_name = self._extract_alter_table_name(command)
        if not view_name:
            raise MigrationError(f"Could not extract view name from: {command}")

        # Extract SELECT query
        modify_query_match = re.search(
            r"MODIFY\s+QUERY\s+(SELECT.+)",
            command,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not modify_query_match:
            raise MigrationError(
                f"Could not extract query from MODIFY QUERY: {command}"
            )

        select_query = modify_query_match.group(1).strip()
        select_query_local = self._rename_from_tables_to_local(select_query)

        # Determine local view and target table names
        view_name_local = self._add_local_suffix(view_name)
        if view_name.endswith(VIEW_SUFFIX):
            target_table = (
                view_name[: -len(VIEW_SUFFIX)] + ch_settings.LOCAL_TABLE_SUFFIX
            )
        else:
            target_table = view_name + ch_settings.LOCAL_TABLE_SUFFIX

        # DROP and CREATE the materialized view
        drop_statement = f"DROP TABLE IF EXISTS {view_name_local} ON CLUSTER {self.replicated_cluster}"
        self.ch_client.command(drop_statement)

        create_statement = (
            f"CREATE MATERIALIZED VIEW {view_name_local}\n"
            f"ON CLUSTER {self.replicated_cluster}\n"
            f"TO {target_table}\n"
            f"AS\n"
            f"{select_query_local}"
        )
        self.ch_client.command(create_statement)

    def _execute_local_table_operation(self, command: str) -> None:
        """Execute operations that only apply to local tables (indexes, mutations)."""
        local_command = self._rename_alter_table_to_local(command)
        local_command = self._add_on_cluster_clause(local_command)
        self.ch_client.command(local_command)

    def _execute_distributed_ddl(self, command: str) -> None:
        """Execute DDL in distributed mode (CREATE TABLE, CREATE/DROP VIEW)."""
        formatted_command = self._add_on_cluster_clause(command)
        result = self._format_distributed_sql(formatted_command)

        self.ch_client.command(result.local_command)
        if result.distributed_command:
            self.ch_client.command(result.distributed_command)

    def _format_distributed_sql(self, sql_query: str) -> DistributedTransformResult:
        """Format SQL for distributed mode (CREATE TABLE, DROP TABLE/VIEW)."""
        # Check if this is a DROP TABLE or DROP VIEW statement
        drop_match = SQLPatterns.DROP_TABLE_OR_VIEW.search(sql_query)
        if drop_match:
            object_type = drop_match.group(1).upper()
            object_name = drop_match.group(2)

            if object_type == "TABLE":
                local_name = self._add_local_suffix(object_name)
                local_command = sql_query.replace(object_name, local_name, 1)
                distributed_command = sql_query
                return DistributedTransformResult(
                    local_command=local_command, distributed_command=distributed_command
                )
            else:  # VIEW
                # For regular views, there's no local/distributed split
                # Views are metadata-only, so we just return a single command
                # (This applies to both regular VIEWs and materialized VIEWs created via CREATE)
                return DistributedTransformResult(
                    local_command=sql_query, distributed_command=None
                )

        # Check if this is a CREATE TABLE statement
        table_match = SQLPatterns.CREATE_TABLE.search(sql_query)
        if not table_match:
            return DistributedTransformResult(
                local_command=sql_query, distributed_command=None
            )

        table_name = table_match.group(1)
        # Rename the table to table_name_local
        local_command = self._rename_table_to_local(sql_query, table_name)

        # Create the distributed table
        distributed_command = self._create_distributed_table_sql(table_name)

        return DistributedTransformResult(
            local_command=local_command, distributed_command=distributed_command
        )

    def _create_distributed_table_sql(self, table_name: str) -> str:
        """Generate SQL to create a distributed table."""
        local_table_name = table_name + ch_settings.LOCAL_TABLE_SUFFIX
        return f"""
        CREATE TABLE IF NOT EXISTS {table_name} ON CLUSTER {self.replicated_cluster}
        AS {local_table_name}
        ENGINE = Distributed({self.replicated_cluster}, currentDatabase(), {local_table_name}, rand())
    """

    @staticmethod
    def _add_local_suffix(name: str) -> str:
        """Add _local suffix to a name if it doesn't already have it.

        This is specific to distributed mode where we have both local tables
        (table_name_local) and distributed tables (table_name).
        """
        return (
            name
            if name.endswith(ch_settings.LOCAL_TABLE_SUFFIX)
            else name + ch_settings.LOCAL_TABLE_SUFFIX
        )

    @staticmethod
    def _is_local_only_operation(command: str) -> bool:
        """Check if the command is an operation that only applies to local tables."""
        return bool(SQLPatterns.LOCAL_ONLY_OPS.search(command))

    @staticmethod
    def _rename_table_to_local(sql_query: str, table_name: str) -> str:
        """Rename table in CREATE TABLE statement to table_name_local."""
        pattern = rf"(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?){table_name}\b"
        return re.sub(
            pattern,
            rf"\1{table_name}{ch_settings.LOCAL_TABLE_SUFFIX}",
            sql_query,
            flags=re.IGNORECASE,
        )

    @staticmethod
    def _rename_alter_table_to_local(sql_query: str) -> str:
        """Rename table in ALTER TABLE statement to table_name_local."""

        def add_suffix(match: re.Match[str]) -> str:
            table_name = match.group(2)
            if not table_name.endswith(ch_settings.LOCAL_TABLE_SUFFIX):
                table_name = table_name + ch_settings.LOCAL_TABLE_SUFFIX
            return f"{match.group(1)}{table_name}{match.group(3)}"

        return SQLPatterns.ALTER_TABLE_NAME_PATTERN.sub(add_suffix, sql_query)

    @staticmethod
    def _extract_alter_table_name(sql_query: str) -> str | None:
        """Extract table name from ALTER TABLE statement."""
        match = SQLPatterns.ALTER_TABLE.search(sql_query)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _rename_from_tables_to_local(sql_query: str) -> str:
        """Rename table references in FROM clauses and qualified column names to use _local suffix."""
        # Strip out SQL comments to avoid matching "from" in comments
        lines = sql_query.split("\n")
        sql_without_comments = []
        comment_lines = {}
        for i, line in enumerate(lines):
            if "--" in line:
                code_part, comment_part = line.split("--", 1)
                sql_without_comments.append(code_part)
                comment_lines[i] = comment_part
            else:
                sql_without_comments.append(line)

        sql_to_process = "\n".join(sql_without_comments)

        def add_suffix_to_from(match: re.Match[str]) -> str:
            table_name = match.group(1) if match.group(1) else match.group(2)
            if not table_name.endswith(ch_settings.LOCAL_TABLE_SUFFIX):
                table_name = table_name + ch_settings.LOCAL_TABLE_SUFFIX
            return f"FROM {table_name}"

        # Collect table names from FROM clauses before renaming
        table_names = set()
        for match in SQLPatterns.FROM_TABLE.finditer(sql_to_process):
            table_name = match.group(1) if match.group(1) else match.group(2)
            if "." in table_name:
                table_name = table_name.split(".")[-1]
            if not table_name.endswith(ch_settings.LOCAL_TABLE_SUFFIX):
                table_names.add(table_name)

        # Rename FROM clauses
        sql_to_process = SQLPatterns.FROM_TABLE.sub(add_suffix_to_from, sql_to_process)

        # Handle qualified column references
        for table_name in table_names:
            qualified_pattern = rf"\b{re.escape(table_name)}\.([a-zA-Z0-9_]+)\b"
            replacement = rf"{table_name}{ch_settings.LOCAL_TABLE_SUFFIX}.\1"
            sql_to_process = re.sub(
                qualified_pattern, replacement, sql_to_process, flags=re.IGNORECASE
            )

        # Restore comments
        result_lines = sql_to_process.split("\n")
        for i, comment in comment_lines.items():
            if i < len(result_lines):
                result_lines[i] = result_lines[i] + "--" + comment

        return "\n".join(result_lines)


def get_clickhouse_trace_server_migrator(
    ch_client: CHClient,
    replicated: bool | None = None,
    replicated_path: str | None = None,
    replicated_cluster: str | None = None,
    use_distributed: bool | None = None,
    management_db: str = "db_management",
) -> BaseClickHouseTraceServerMigrator:
    """Factory function to create the appropriate migrator based on configuration.

    Args:
        ch_client: ClickHouse client instance
        replicated: Whether to use replicated tables
        replicated_path: ZooKeeper path for replication
        replicated_cluster: Cluster name for replication
        use_distributed: Whether to use distributed tables (requires replicated=True)
        management_db: Database name for migration management

    Returns:
        An instance of the appropriate migrator class

    Raises:
        MigrationError: If configuration is invalid (e.g., use_distributed without replicated)
    """
    replicated = False if replicated is None else replicated
    use_distributed = False if use_distributed is None else use_distributed

    logger.info(
        f"ClickHouseTraceServerMigrator initialized with: "
        f"replicated={replicated}, "
        f"use_distributed={use_distributed}, "
        f"replicated_cluster={replicated_cluster}, "
        f"replicated_path={replicated_path}, "
        f"management_db={management_db}"
    )

    # Validate configuration
    if use_distributed and not replicated:
        raise MigrationError(
            "Distributed tables can only be used with replicated tables. "
            "Set replicated=True or use_distributed=False."
        )

    if use_distributed:
        return DistributedClickHouseTraceServerMigrator(
            ch_client, replicated_path, replicated_cluster, management_db
        )
    elif replicated:
        return ReplicatedClickHouseTraceServerMigrator(
            ch_client, replicated_path, replicated_cluster, management_db
        )
    else:
        return CloudClickHouseTraceServerMigrator(ch_client, management_db)


class MigrationError(RuntimeError):
    """Raised when a migration error occurs."""


class SQLPatterns:
    """Consolidated SQL regex patterns for parsing and transforming SQL statements."""

    # Table and identifier patterns
    CREATE_TABLE: Pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)",
        re.IGNORECASE,
    )
    ALTER_TABLE: Pattern = re.compile(
        r"ALTER\s+TABLE\s+([a-zA-Z0-9_.]+)", re.IGNORECASE
    )
    SAFE_IDENTIFIER: Pattern = re.compile(r"^[a-zA-Z0-9_\.]+$")

    # Engine patterns
    MERGETREE_ENGINE: Pattern = re.compile(
        r"ENGINE\s*=\s*(\w+)?MergeTree\b(\(\))?", re.IGNORECASE
    )

    # DDL statement patterns
    ALTER_TABLE_STMT: Pattern = re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE)
    CREATE_TABLE_STMT: Pattern = re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE)
    DROP_VIEW_STMT: Pattern = re.compile(r"\bDROP\s+VIEW\b", re.IGNORECASE)
    CREATE_VIEW_STMT: Pattern = re.compile(
        r"\bCREATE\s+(?:MATERIALIZED\s+)?VIEW\b", re.IGNORECASE
    )
    DROP_TABLE_OR_VIEW: Pattern = re.compile(
        r"\bDROP\s+(TABLE|VIEW)\s+(?:IF\s+EXISTS\s+)?([a-zA-Z0-9_.]+)", re.IGNORECASE
    )

    # ON CLUSTER pattern
    ON_CLUSTER: Pattern = re.compile(r"\bON\s+CLUSTER\b", re.IGNORECASE)
    IF_EXISTS: Pattern = re.compile(r"\bIF\s+EXISTS\b", re.IGNORECASE)

    # Distributed mode patterns
    MODIFY_QUERY: Pattern = re.compile(r"\bMODIFY\s+QUERY\b", re.IGNORECASE)
    MATERIALIZE: Pattern = re.compile(r"\bMATERIALIZE\b", re.IGNORECASE)
    LOCAL_ONLY_OPS: Pattern = re.compile(
        r"\b(ADD|DROP)\s+INDEX\b|\b(DELETE|UPDATE)\b", re.IGNORECASE
    )

    # Table name extraction patterns
    ALTER_TABLE_NAME_PATTERN: Pattern = re.compile(
        r"(ALTER\s+TABLE\s+)([a-zA-Z0-9_.]+)(\s+)", re.IGNORECASE
    )
    CREATE_TABLE_NAME_PATTERN: Pattern = re.compile(
        r"(\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)([a-zA-Z0-9_.]+)(\s*\()",
        re.IGNORECASE,
    )
    DROP_VIEW_NAME_PATTERN: Pattern = re.compile(
        r"(\bDROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?)([a-zA-Z0-9_.]+)(\s|$)", re.IGNORECASE
    )
    CREATE_VIEW_NAME_PATTERN: Pattern = re.compile(
        r"(\bCREATE\s+(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?)([a-zA-Z0-9_.]+)(\s+)",
        re.IGNORECASE,
    )

    # FROM clause patterns
    FROM_TABLE: Pattern = re.compile(
        r"(?<=\s)FROM\s+([a-zA-Z0-9_.]+)\b|^FROM\s+([a-zA-Z0-9_.]+)\b",
        re.IGNORECASE | re.MULTILINE,
    )
