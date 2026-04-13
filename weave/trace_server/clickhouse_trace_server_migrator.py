# Clickhouse Trace Server Manager

"""ClickHouse trace-server migrator.

We keep one simple data-table rule across replicated and distributed deployments:

- Rewrite MergeTree-family engines to bare ``Replicated*MergeTree``.
- Let the target database engine decide whether the DDL also needs
  ``ON CLUSTER``.

That gives us two normal data layouts:

- Replicated DB: bare ``Replicated*MergeTree``, no ``ON CLUSTER``.
- Atomic DB: bare ``Replicated*MergeTree`` plus ``ON CLUSTER``.

Distributed mode adds only the `_local` / `Distributed(...)` table split on top
of that. The only remaining explicit ZooKeeper-path handling is the shared
``db_management.migrations`` table in distributed mode when the management DB is
Atomic; that table must be shared across shards instead of per-shard.
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from re import Pattern

from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.exceptions import DatabaseError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.costs.insert_costs import insert_costs, should_insert_costs
from weave.trace_server.database_engine import (
    ENGINE_DISCOVERY_MAX_WAIT_SECONDS,
    EngineDiscoveryError,
    get_database_engine,
    wait_for_database_engine,
)
from weave.trace_server.environment import wf_clickhouse_calls_shard_key

logger = logging.getLogger(__name__)

# Retry configuration for transient ClickHouse errors during migrations.
# Error 517 (CANNOT_ASSIGN_ALTER) occurs when a replica hasn't caught up with
# the latest ALTER metadata — common on multi-replica managed ClickHouse clusters
# when sequential DDL statements run faster than replication can propagate.
_TRANSIENT_CH_ERROR_CODES = {517}
_MAX_RETRIES = 3
_RETRY_MAX_WAIT_SECONDS = 8
_COMMAND_PREVIEW_LENGTH = 100


def _is_transient_ch_error(exc: BaseException) -> bool:
    """Check if a ClickHouse error is a known transient replication error."""
    if not isinstance(exc, DatabaseError):
        return False
    # clickhouse_connect.DatabaseError has no structured error code attr; parse from message.
    match = re.search(r"Code:\s*(\d+)", str(exc))
    if match is None:
        return False
    return int(match.group(1)) in _TRANSIENT_CH_ERROR_CODES


# These settings are only used when `replicated` mode is enabled for
# self managed clickhouse instances.
DEFAULT_REPLICATED_PATH = "/clickhouse/tables/{db}"
DEFAULT_REPLICATED_CLUSTER = "weave_cluster"

# Constants for table naming conventions
VIEW_SUFFIX = "_view"

# Schema for the migration tracking table (shared across all migrator variants)
_MIGRATIONS_TABLE_COLUMNS = """
    db_name String,
    curr_version UInt64,
    partially_applied_version UInt64 NULL,
"""

# Tables that use ID-based sharding (sipHash64(field)) instead of random sharding
# in distributed mode. Maps table name to the field used for sharding.
# calls_complete: shard key is configurable via WF_CLICKHOUSE_CALLS_SHARD_KEY env var
# Valid values: "trace_id" (default), "id", "project_id"
ID_SHARDED_TABLES: dict[str, str] = {"calls_complete": wf_clickhouse_calls_shard_key()}


@dataclass(frozen=True)
class PostMigrationHookContext:
    ch_client: CHClient
    target_db: str
    current_version: int
    target_version: int | None


PostMigrationHook = Callable[[PostMigrationHookContext], None]


def _default_trace_server_costs_post_migration_hook(
    ctx: PostMigrationHookContext,
) -> None:
    if should_insert_costs(ctx.current_version, ctx.target_version):
        insert_costs(ctx.ch_client, ctx.target_db)


class BaseClickHouseTraceServerMigrator(ABC):
    """Base class for ClickHouse trace server migration strategies.

    This abstract base class defines the common interface and shared logic for
    migrating ClickHouse databases across different deployment modes (cloud,
    replicated, and distributed).
    """

    ch_client: CHClient
    management_db: str
    migration_dir: str
    post_migration_hook: PostMigrationHook | None

    def __init__(
        self,
        ch_client: CHClient,
        management_db: str = "db_management",
        *,
        migration_dir: str,
        post_migration_hook: PostMigrationHook | None = None,
    ):
        super().__init__()
        self.ch_client = ch_client
        self.management_db = management_db
        self.migration_dir = self._resolve_migration_dir(migration_dir)
        self.post_migration_hook = post_migration_hook
        self._initialize_migration_db()

    def _ensure_database(self, db_name: str) -> None:
        """Create a database if it does not exist."""
        db_sql = self._create_db_sql(db_name)
        self._run_ddl_with_retry(db_sql)

    @staticmethod
    def _resolve_migration_dir(migration_dir: str) -> str:
        if not os.path.isabs(migration_dir):
            raise MigrationError(
                f"migration_dir must be an absolute path, got: {migration_dir}"
            )
        if not os.path.isdir(migration_dir):
            raise MigrationError(f"Migration directory not found: {migration_dir}")
        return migration_dir

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
        logger.info("""`%s` migration status: %s""", target_db, status)
        if status["partially_applied_version"]:
            raise MigrationError(
                f"Unable to apply migrations to `{target_db}`. Found partially applied "
                f"migration version {status['partially_applied_version']}. "
                f"Please fix the database manually and try again."
            )
        migration_map = self._get_migrations()
        migrations_to_apply = self._determine_migrations_to_apply(
            status["curr_version"], migration_map, target_version
        )
        if len(migrations_to_apply) == 0:
            logger.info("No migrations to apply to `%s`", target_db)
            self._run_post_migration_hook(
                target_db, status["curr_version"], target_version
            )
            return
        logger.info("Migrations to apply: %s", migrations_to_apply)
        if status["curr_version"] == 0:
            self._ensure_database(target_db)
        applied_target_version = target_version
        for migration_target_version, migration_file in migrations_to_apply:
            self._apply_migration(target_db, migration_target_version, migration_file)
            applied_target_version = migration_target_version
        self._run_post_migration_hook(
            target_db, status["curr_version"], applied_target_version
        )

    def _run_post_migration_hook(
        self, target_db: str, current_version: int, target_version: int | None
    ) -> None:
        if self.post_migration_hook is None:
            return
        self.post_migration_hook(
            PostMigrationHookContext(
                ch_client=self.ch_client,
                target_db=target_db,
                current_version=current_version,
                target_version=target_version,
            )
        )

    def _initialize_migration_db(self) -> None:
        """Initialize the management database and migrations table."""
        self._ensure_database(self.management_db)
        create_table_sql = self._create_management_table_sql()
        self._run_ddl_with_retry(create_table_sql)

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
        migration_files = os.listdir(self.migration_dir)
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

            max_version = max(max_version, version)

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
                    "Found current version (%s) greater than known versions (%s). Will not run any migrations.",
                    current_version,
                    len(migration_map),
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
                "Automatically running down migrations is disabled and should be done manually. Current version (%s) is greater than target version (%s).",
                current_version,
                target_version,
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
        logger.info("Applying migration %s to `%s`", migration_file, target_db)
        migration_file_path = os.path.join(self.migration_dir, migration_file)

        with open(migration_file_path, encoding="utf-8") as f:
            migration_sql = f.read()

        # Mark migration as partially applied
        self._update_migration_status(target_db, target_version, is_start=True)

        # Execute each command in the migration
        migration_sub_commands = migration_sql.split(";")
        for command in migration_sub_commands:
            self._execute_migration_command(target_db, command)

        # Mark migration as fully applied
        self._update_migration_status(target_db, target_version, is_start=False)

        logger.info("Migration %s applied to `%s`", migration_file, target_db)

    def _update_migration_status(
        self, target_db: str, target_version: int, is_start: bool = True
    ) -> None:
        """Update the migration status in management database migrations table."""
        if is_start:
            command = f"ALTER TABLE {self.management_db}.migrations UPDATE partially_applied_version = {target_version} WHERE db_name = '{target_db}'"
            self._run_ddl_with_retry(command)
        else:
            command = f"ALTER TABLE {self.management_db}.migrations UPDATE curr_version = {target_version}, partially_applied_version = NULL WHERE db_name = '{target_db}'"
            self._run_ddl_with_retry(command)

    @staticmethod
    def _is_safe_identifier(value: str) -> bool:
        """Check if a string is safe to use as an identifier in SQL."""
        return bool(SQLPatterns.SAFE_IDENTIFIER.match(value))

    @retry(
        stop=stop_after_attempt(_MAX_RETRIES + 1),
        wait=wait_exponential(multiplier=1, min=1, max=_RETRY_MAX_WAIT_SECONDS),
        retry=retry_if_exception(_is_transient_ch_error),
        reraise=True,
    )
    def _run_ddl_with_retry(self, command: str) -> None:
        """Execute a DDL command with retry for transient replication errors.

        On multi-replica clusters, sequential DDL can outpace metadata replication
        causing error 517 (CANNOT_ASSIGN_ALTER). This retries with exponential
        backoff for those known-transient codes.
        """
        self.ch_client.command(command)


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
            ({_MIGRATIONS_TABLE_COLUMNS})
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
        self._run_ddl_with_retry(command)
        self.ch_client.database = curr_db


class ReplicatedClickHouseTraceServerMigrator(BaseClickHouseTraceServerMigrator):
    """Migrator for replicated ClickHouse deployments.

    In replicated mode:
    - Fresh databases use ENGINE = Replicated(...)
    - MergeTree-family tables are rewritten to bare Replicated*MergeTree
    - Existing Atomic databases remain supported by adding ON CLUSTER
    """

    replicated_path: str
    replicated_cluster: str

    def __init__(
        self,
        ch_client: CHClient,
        replicated_path: str | None = None,
        replicated_cluster: str | None = None,
        management_db: str = "db_management",
        *,
        migration_dir: str,
        post_migration_hook: PostMigrationHook | None = None,
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
            "%s ReplicatedClickHouseTraceServerMigrator initialized with: "
            "replicated_cluster=%s, "
            "replicated_path=%s, "
            "management_db=%s",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            self.replicated_cluster,
            self.replicated_path,
            management_db,
        )

        self._database_engine_cache: dict[str, str] = {}
        super().__init__(
            ch_client,
            management_db,
            migration_dir=migration_dir,
            post_migration_hook=post_migration_hook,
        )

    def _ensure_database(self, db_name: str) -> None:
        """Create the database and cache the resulting engine."""
        db_sql = self._create_db_sql(db_name)
        self._run_ddl_with_retry(db_sql)
        try:
            engine = wait_for_database_engine(
                self.ch_client,
                db_name,
                max_wait_seconds=ENGINE_DISCOVERY_MAX_WAIT_SECONDS,
                context=db_sql,
            )
        except EngineDiscoveryError as exc:
            raise MigrationError(str(exc)) from exc
        self._database_engine_cache[db_name] = engine

    def _get_database_engine(self, db_name: str) -> str:
        if engine := self._database_engine_cache.get(db_name):
            return engine

        try:
            engine = get_database_engine(self.ch_client, db_name)
        except EngineDiscoveryError as exc:
            raise MigrationError(str(exc)) from exc
        if engine is None:
            raise MigrationError(f"Could not determine database engine for `{db_name}`")
        self._database_engine_cache[db_name] = engine
        return engine

    def _should_add_on_cluster(self, db_name: str) -> bool:
        return self._get_database_engine(db_name) != "Replicated"

    def _create_db_sql(self, db_name: str) -> str:
        """Generate SQL to create a database in replicated mode.

        Fresh databases use ENGINE = Replicated(...). Existing Atomic
        databases remain supported because later DDL checks the actual engine
        once and only adds ON CLUSTER when needed.
        """
        if not self._is_safe_identifier(db_name):
            raise MigrationError(f"Invalid database name: {db_name}")

        replicated_path = self.replicated_path.replace("{db}", db_name)
        if not all(
            self._is_safe_identifier(part)
            for part in replicated_path.split("/")
            if part
        ):
            raise MigrationError(f"Invalid replicated path: {replicated_path}")

        return (
            f"CREATE DATABASE IF NOT EXISTS {db_name}"
            f" ON CLUSTER {self.replicated_cluster}"
            f" ENGINE = Replicated('{replicated_path}', '{{shard}}', '{{replica}}')"
        )

    def _prepare_replicated_ddl(self, sql_query: str, target_db: str) -> str:
        """Rewrite tables to Replicated*MergeTree and add ON CLUSTER if needed."""
        sql_query = self._format_replicated_sql(sql_query)
        if self._should_add_on_cluster(target_db):
            return self._add_on_cluster_clause(sql_query)
        return sql_query

    def _create_management_table_sql(self) -> str:
        """Generate SQL to create the management table in replicated mode."""
        create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.management_db}.migrations
            ({_MIGRATIONS_TABLE_COLUMNS})
            ENGINE = MergeTree()
            ORDER BY (db_name)
        """
        return self._prepare_replicated_ddl(create_table_sql, self.management_db)

    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute command in replicated mode."""
        command = command.strip()
        if len(command) == 0:
            return

        curr_db = self.ch_client.database
        self.ch_client.database = target_db

        formatted_command = self._prepare_replicated_ddl(command, target_db)
        self._run_ddl_with_retry(formatted_command)

        self.ch_client.database = curr_db

    def _format_replicated_sql(self, sql_query: str) -> str:
        """Format SQL query to use replicated engines."""

        def replace_engine(match: re.Match[str]) -> str:
            engine_prefix = match.group(1) or ""
            engine_args = match.group(2) or ""
            if engine_prefix.lower().startswith("replicated"):
                return match.group(0)
            engine_args = match.group(2) or ""
            return f"ENGINE = Replicated{engine_prefix}MergeTree{engine_args}"

        return SQLPatterns.MERGETREE_ENGINE.sub(replace_engine, sql_query)

    def _get_on_cluster_clause(self, db_name: str) -> str:
        """Returns ' ON CLUSTER {cluster}' when the DB engine needs it."""
        if self._should_add_on_cluster(db_name):
            return f" ON CLUSTER {self.replicated_cluster}"
        return ""

    def _add_on_cluster_clause(self, sql_query: str) -> str:
        """Add ON CLUSTER clause to DDL statements if not already present."""
        if SQLPatterns.ON_CLUSTER.search(sql_query):
            return sql_query

        # ALTER TABLE
        if SQLPatterns.ALTER_TABLE_STMT.search(sql_query):
            return SQLPatterns.ALTER_TABLE_NAME_PATTERN.sub(
                lambda m: (
                    f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}"
                ),
                sql_query,
            )

        # CREATE TABLE
        if SQLPatterns.CREATE_TABLE_STMT.search(sql_query):
            return SQLPatterns.CREATE_TABLE_NAME_PATTERN.sub(
                lambda m: (
                    f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}"
                ),
                sql_query,
            )

        # DROP TABLE
        if SQLPatterns.DROP_TABLE_STMT.search(sql_query):
            return SQLPatterns.DROP_TABLE_NAME_PATTERN.sub(
                lambda m: (
                    f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}"
                ),
                sql_query,
            )

        # DROP VIEW
        if SQLPatterns.DROP_VIEW_STMT.search(sql_query):
            return SQLPatterns.DROP_VIEW_NAME_PATTERN.sub(
                lambda m: (
                    f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}"
                ),
                sql_query,
            )

        # CREATE VIEW / CREATE MATERIALIZED VIEW
        if SQLPatterns.CREATE_VIEW_STMT.search(sql_query):
            return SQLPatterns.CREATE_VIEW_NAME_PATTERN.sub(
                lambda m: (
                    f"{m.group(1)}{m.group(2)} ON CLUSTER {self.replicated_cluster}{m.group(3)}"
                ),
                sql_query,
            )

        # RENAME TABLE
        if SQLPatterns.RENAME_TABLE_STMT.search(sql_query):
            return f"{sql_query.rstrip()} ON CLUSTER {self.replicated_cluster}"

        return sql_query


@dataclass
class DistributedTransformResult:
    """Result of transforming SQL for distributed tables."""

    local_command: str
    distributed_command: str | None


class DistributedClickHouseTraceServerMigrator(ReplicatedClickHouseTraceServerMigrator):
    """Migrator for distributed ClickHouse deployments with sharding.

    In distributed mode (extends replicated mode):
    - Data DBs still use the same bare Replicated*MergeTree rewrite as replicated mode
    - Local tables (`table_name_local`) store data
    - Distributed tables (`table_name`) route queries across shards
    - The only explicit ZK-path special case is the shared migrations table when
      the management DB is Atomic
    """

    def __init__(
        self,
        ch_client: CHClient,
        replicated_path: str | None = None,
        replicated_cluster: str | None = None,
        management_db: str = "db_management",
        *,
        migration_dir: str,
        post_migration_hook: PostMigrationHook | None = None,
    ):
        logger.info(
            "%s DistributedClickHouseTraceServerMigrator initialized",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        super().__init__(
            ch_client,
            replicated_path,
            replicated_cluster,
            management_db,
            migration_dir=migration_dir,
            post_migration_hook=post_migration_hook,
        )

    def _create_db_sql(self, db_name: str) -> str:
        """Generate SQL to create a database in distributed mode.

        The management database uses ENGINE = Atomic (not Replicated) so that the
        migrations table can use an explicit shared ReplicatedMergeTree path
        across all shards. Data databases still use ENGINE = Replicated.
        """
        if db_name == self.management_db:
            if not self._is_safe_identifier(db_name):
                raise MigrationError(f"Invalid database name: {db_name}")
            return (
                f"CREATE DATABASE IF NOT EXISTS {db_name}"
                f" ON CLUSTER {self.replicated_cluster}"
                f" ENGINE = Atomic"
            )
        return super()._create_db_sql(db_name)

    def _create_management_table_sql(self) -> str:
        """Generate SQL to create the management table in distributed mode.

        Preferred layout:
        - Replicated-only DB: Replicated*MergeTree() with no ON CLUSTER
        - Distributed + Atomic DB: explicit ZK args plus ON CLUSTER
        - Distributed + Replicated DB: Replicated*MergeTree() with no explicit
          ZK args and no ON CLUSTER

        In distributed mode, the shared migrations table is the only case that
        still needs explicit ZK arguments: when the management DB is Atomic we
        must share one migrations table across all shards instead of giving
        each shard its own replicated table.
        """
        if self._get_database_engine(self.management_db) == "Replicated":
            return self._prepare_replicated_ddl(
                f"""
                    CREATE TABLE IF NOT EXISTS {self.management_db}.migrations
                    ({_MIGRATIONS_TABLE_COLUMNS})
                    ENGINE = MergeTree()
                    ORDER BY (db_name)
                """,
                self.management_db,
            )
        return f"""
            CREATE TABLE IF NOT EXISTS {self.management_db}.migrations
            ON CLUSTER {self.replicated_cluster}
            ({_MIGRATIONS_TABLE_COLUMNS})
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
        command_for_match = SQLPatterns.LINE_COMMENT.sub("", command)

        # Skip MATERIALIZE commands (not supported by distributed tables)
        if SQLPatterns.MATERIALIZE.search(command_for_match):
            logger.warning(
                "Skipping MATERIALIZE command (not supported in distributed mode): %s",
                command,
            )
            self.ch_client.database = curr_db
            return

        # Skip INSERT commands (backfill not supported in distributed mode)
        if SQLPatterns.INSERT_STMT.search(command_for_match):
            logger.warning(
                "Skipping INSERT command (not supported in distributed mode): %s...",
                command[:_COMMAND_PREVIEW_LENGTH],
            )
            self.ch_client.database = curr_db
            return

        # Handle RENAME TABLE (local rename + drop/recreate distributed table)
        if SQLPatterns.RENAME_TABLE_STMT.search(command_for_match):
            self._execute_distributed_rename(command)
            self.ch_client.database = curr_db
            return

        # Handle CREATE/DROP VIEW (no local/distributed split, just add ON CLUSTER)
        if SQLPatterns.CREATE_VIEW_STMT.search(
            command_for_match
        ) or SQLPatterns.DROP_VIEW_STMT.search(command_for_match):
            formatted_command = command
            if self._should_add_on_cluster(target_db):
                formatted_command = self._add_on_cluster_clause(formatted_command)
            self._run_ddl_with_retry(formatted_command)
            self.ch_client.database = curr_db
            return

        formatted_command = self._prepare_replicated_ddl(command, target_db)

        # Handle ALTER TABLE
        if SQLPatterns.ALTER_TABLE_STMT.search(command_for_match):
            self._execute_distributed_alter(formatted_command)
        else:
            # Handle CREATE TABLE and other DDL
            self._execute_distributed_ddl(formatted_command)

        self.ch_client.database = curr_db

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
        self._run_ddl_with_retry(local_command)

        self._run_ddl_with_retry(command)

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
        on_cluster = self._get_on_cluster_clause(self.ch_client.database)
        drop_statement = f"DROP TABLE IF EXISTS {view_name_local}{on_cluster}"
        self._run_ddl_with_retry(drop_statement)

        create_statement = f"CREATE MATERIALIZED VIEW {view_name_local}{on_cluster}\nTO {target_table}\nAS\n{select_query_local}"
        self._run_ddl_with_retry(create_statement)

    def _execute_local_table_operation(self, command: str) -> None:
        """Execute operations that only apply to local tables (indexes, mutations)."""
        local_command = self._rename_alter_table_to_local(command)
        self._run_ddl_with_retry(local_command)

    def _execute_distributed_rename(self, command: str) -> None:
        """Handle RENAME TABLE in distributed mode.

        Distributed tables bake the local table reference into the engine
        definition at CREATE time, so a plain RENAME is insufficient. Instead:
        1. Rename the local (Replicated*MergeTree) table ON CLUSTER.
        2. Drop the old distributed table ON CLUSTER.
        3. Create a new distributed table pointing to the renamed local table,
           picking up the correct sharding key from ID_SHARDED_TABLES.
        """
        match = SQLPatterns.RENAME_TABLE.search(command)
        if not match:
            raise MigrationError(f"Could not parse RENAME TABLE: {command}")

        old_name = match.group(1)
        new_name = match.group(2)

        old_local = self._add_local_suffix(old_name)
        new_local = self._add_local_suffix(new_name)

        on_cluster = self._get_on_cluster_clause(self.ch_client.database)
        self._run_ddl_with_retry(f"RENAME TABLE {old_local} TO {new_local}{on_cluster}")
        self._run_ddl_with_retry(f"DROP TABLE IF EXISTS {old_name}{on_cluster}")
        self._run_ddl_with_retry(self._create_distributed_table_sql(new_name))

    def _execute_distributed_ddl(self, command: str) -> None:
        """Execute DDL in distributed mode (CREATE TABLE, CREATE/DROP VIEW)."""
        result = self._format_distributed_sql(command)

        self._run_ddl_with_retry(result.local_command)
        if result.distributed_command:
            self._run_ddl_with_retry(result.distributed_command)

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
        """Generate SQL to create a distributed table.

        For tables in ID_SHARDED_TABLES, uses sipHash64(field) as the sharding key
        to ensure all data for a specific ID goes to the same shard, enabling
        efficient point lookups. Other tables use rand() for even distribution.
        """
        local_table_name = table_name + ch_settings.LOCAL_TABLE_SUFFIX
        if shard_field := ID_SHARDED_TABLES.get(table_name):
            sharding_key = f"sipHash64({shard_field})"
        else:
            sharding_key = "rand()"
        on_cluster = self._get_on_cluster_clause(self.ch_client.database)
        return f"""
        CREATE TABLE IF NOT EXISTS {table_name}{on_cluster}
        AS {local_table_name}
        ENGINE = Distributed({self.replicated_cluster}, currentDatabase(), {local_table_name}, {sharding_key})
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
                table_name += ch_settings.LOCAL_TABLE_SUFFIX
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
                table_name += ch_settings.LOCAL_TABLE_SUFFIX
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
    migration_dir: str | None = None,
    post_migration_hook: PostMigrationHook
    | None = _default_trace_server_costs_post_migration_hook,
) -> BaseClickHouseTraceServerMigrator:
    """Factory function to create the appropriate migrator based on configuration.

    Args:
        ch_client: ClickHouse client instance
        replicated: Whether to use replicated tables
        replicated_path: ZooKeeper path for replication
        replicated_cluster: Cluster name for replication
        use_distributed: Whether to use distributed tables (requires replicated=True)
        management_db: Database name for migration management
        migration_dir: Absolute path to a directory containing `*.up.sql` / `*.down.sql`
        post_migration_hook: Optional callable run after migrations; defaults to the Weave costs backfill hook (pass None to disable)

    Returns:
        An instance of the appropriate migrator class

    Raises:
        MigrationError: If configuration is invalid (e.g., use_distributed without replicated)
    """
    replicated = False if replicated is None else replicated
    use_distributed = False if use_distributed is None else use_distributed

    logger.info(
        "ClickHouseTraceServerMigrator initialized with: "
        "replicated=%s, "
        "use_distributed=%s, "
        "replicated_cluster=%s, "
        "replicated_path=%s, "
        "management_db=%s, "
        "migration_dir=%s, "
        "post_migration_hook=%s",
        replicated,
        use_distributed,
        replicated_cluster,
        replicated_path,
        management_db,
        migration_dir,
        "none" if post_migration_hook is None else "callable",
    )

    # Validate configuration
    if use_distributed and not replicated:
        raise MigrationError(
            "Distributed tables can only be used with replicated tables. "
            "Set replicated=True or use_distributed=False."
        )

    if migration_dir is None:
        migration_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "migrations")
        )

    if use_distributed:
        return DistributedClickHouseTraceServerMigrator(
            ch_client,
            replicated_path,
            replicated_cluster,
            management_db,
            migration_dir=migration_dir,
            post_migration_hook=post_migration_hook,
        )
    if replicated:
        return ReplicatedClickHouseTraceServerMigrator(
            ch_client,
            replicated_path,
            replicated_cluster,
            management_db,
            migration_dir=migration_dir,
            post_migration_hook=post_migration_hook,
        )

    return CloudClickHouseTraceServerMigrator(
        ch_client,
        management_db,
        migration_dir=migration_dir,
        post_migration_hook=post_migration_hook,
    )


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
    # Group 1: engine prefix (e.g. "Replacing", "Aggregating")
    # Group 2: engine arguments including parens (e.g. "(created_at)" or "()")
    MERGETREE_ENGINE: Pattern = re.compile(
        r"ENGINE\s*=\s*(\w+)?MergeTree\b(\([^)]*\))?", re.IGNORECASE
    )

    # DDL statement patterns
    ALTER_TABLE_STMT: Pattern = re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE)
    CREATE_TABLE_STMT: Pattern = re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE)
    DROP_TABLE_STMT: Pattern = re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)
    DROP_VIEW_STMT: Pattern = re.compile(r"\bDROP\s+VIEW\b", re.IGNORECASE)
    RENAME_TABLE_STMT: Pattern = re.compile(r"\bRENAME\s+TABLE\b", re.IGNORECASE)
    CREATE_VIEW_STMT: Pattern = re.compile(
        r"\bCREATE\s+(?:MATERIALIZED\s+)?VIEW\b", re.IGNORECASE
    )
    DROP_TABLE_OR_VIEW: Pattern = re.compile(
        r"\bDROP\s+(TABLE|VIEW)\s+(?:IF\s+EXISTS\s+)?([a-zA-Z0-9_.]+)", re.IGNORECASE
    )
    LINE_COMMENT: Pattern = re.compile(r"(?m)^\s*--.*$")

    # ON CLUSTER pattern
    ON_CLUSTER: Pattern = re.compile(r"\bON\s+CLUSTER\b", re.IGNORECASE)
    IF_EXISTS: Pattern = re.compile(r"\bIF\s+EXISTS\b", re.IGNORECASE)

    # Distributed mode patterns
    MODIFY_QUERY: Pattern = re.compile(r"\bMODIFY\s+QUERY\b", re.IGNORECASE)
    MATERIALIZE: Pattern = re.compile(r"\bMATERIALIZE\b", re.IGNORECASE)
    INSERT_STMT: Pattern = re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE)
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
    DROP_TABLE_NAME_PATTERN: Pattern = re.compile(
        r"(\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?)([a-zA-Z0-9_.]+)(\s|$)",
        re.IGNORECASE,
    )
    RENAME_TABLE: Pattern = re.compile(
        r"RENAME\s+TABLE\s+([a-zA-Z0-9_.]+)\s+TO\s+([a-zA-Z0-9_.]+)",
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
