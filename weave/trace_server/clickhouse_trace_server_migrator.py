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

# Constants for table naming conventions
LOCAL_TABLE_SUFFIX = "_local"
VIEW_SUFFIX = "_view"


"""
Differences between cloud, replicated, and distributed modes:

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

**ALTER TABLE ... MODIFY QUERY (materialized views):**
  - Uses DROP/CREATE pattern instead of ALTER
  - Drops `view_name_local` ON CLUSTER
  - Creates `view_name_local` ON CLUSTER with `TO target_table_local`
  - All `FROM` clauses and qualified column references renamed to `_local` suffix

**CREATE/DROP VIEW:**
  - Only adds `ON CLUSTER` clause (views are metadata-only, no local/distributed split)

**MATERIALIZE commands:**
  - Skipped entirely (not supported by distributed tables)
"""


@dataclass
class DistributedTransformResult:
    """Result of transforming SQL for distributed tables."""

    local_command: str
    distributed_command: str | None


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

        # Log configuration
        logger.info(
            f"ClickHouseTraceServerMigrator initialized with: "
            f"replicated={self.replicated}, "
            f"use_distributed={self.use_distributed}, "
            f"replicated_cluster={self.replicated_cluster}, "
            f"replicated_path={self.replicated_path}, "
            f"management_db={self.management_db}"
        )

        self._initialize_migration_db()

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
            db_sql = _create_db_sql(
                target_db,
                self.replicated,
                self.replicated_cluster,
                self.replicated_path,
            )
            self.ch_client.command(db_sql)
        for target_version, migration_file in migrations_to_apply:
            self._apply_migration(target_db, target_version, migration_file)
        if should_insert_costs(status["curr_version"], target_version):
            insert_costs(self.ch_client, target_db)

    def _initialize_migration_db(self) -> None:
        db_sql = _create_db_sql(
            self.management_db,
            self.replicated,
            self.replicated_cluster,
            self.replicated_path,
        )
        self.ch_client.command(db_sql)
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
        if self.replicated:
            create_table_sql = _format_replicated_sql(create_table_sql)
            create_table_sql = _format_create_table_with_on_cluster_sql(
                create_table_sql, self.replicated_cluster
            )
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
            res = []
            for i in range(current_version, target_version, -1):
                if migration_map[i]["down"] is None:
                    raise MigrationError(f"Missing down migration file for version {i}")
                res.append((i - 1, f"{migration_map[i]['down']}"))
            return res

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
            self.ch_client.command(
                f"ALTER TABLE {self.management_db}.migrations UPDATE partially_applied_version = {target_version} WHERE db_name = '{target_db}'"
            )
        else:
            self.ch_client.command(
                f"ALTER TABLE {self.management_db}.migrations UPDATE curr_version = {target_version}, partially_applied_version = NULL WHERE db_name = '{target_db}'"
            )

    def _execute_migration_command(self, target_db: str, command: str) -> None:
        """Execute a single migration command in the context of the target database."""
        command = command.strip()
        if len(command) == 0:
            return

        curr_db = self.ch_client.database
        self.ch_client.database = target_db

        if not self.replicated:
            self.ch_client.command(command)
            self.ch_client.database = curr_db
            return

        formatted_command = _format_replicated_sql(
            command, use_distributed=self.use_distributed, target_db=target_db
        )
        formatted_command = _format_create_table_with_on_cluster_sql(
            formatted_command, self.replicated_cluster
        )
        else:
            self._execute_replicated_command(formatted_command)

        self.ch_client.database = curr_db

    def _execute_replicated_command(self, command: str) -> None:
        """Execute command in replicated mode."""
        formatted_command = _format_with_on_cluster_sql(
            command, self.replicated_cluster
        )
        self.ch_client.command(formatted_command)

    def _execute_distributed_command(self, command: str) -> None:
        """Execute command in distributed mode."""
        # Skip MATERIALIZE commands (not supported by distributed tables)
        if re.search(r"\bMATERIALIZE\b", command, flags=re.IGNORECASE):
            logger.warning(
                f"Skipping MATERIALIZE command (not supported in distributed mode): {command}"
            )
            return

        # Check for ALTER TABLE
        is_alter = re.search(r"\bALTER\s+TABLE\b", command, flags=re.IGNORECASE)
        if is_alter:
            self._execute_distributed_alter(command)
            return

        # Handle CREATE TABLE and other DDL
        self._execute_distributed_ddl(command)

    def _execute_distributed_alter(self, command: str) -> None:
        """Execute ALTER TABLE in distributed mode."""
        # Materialized view modification (MODIFY QUERY)
        is_modify_query = re.search(r"\bMODIFY\s+QUERY\b", command, flags=re.IGNORECASE)
        if is_modify_query:
            self._execute_materialized_view_alter(command)
            return

        # Index operations (ADD/DROP INDEX)
        is_index_op = re.search(r"\b(ADD|DROP)\s+INDEX\b", command, flags=re.IGNORECASE)
        if is_index_op:
            self._execute_index_operation(command)
            return

        # Regular ALTER: apply to both local and distributed tables
        local_command = _rename_alter_table_to_local(command)
        local_command = _format_with_on_cluster_sql(
            local_command, self.replicated_cluster
        )
        self.ch_client.command(local_command)

        distributed_command = _format_with_on_cluster_sql(
            command, self.replicated_cluster
        )
        self.ch_client.command(distributed_command)

    def _execute_materialized_view_alter(self, command: str) -> None:
        """Handle ALTER TABLE MODIFY QUERY for materialized views in distributed mode."""
        view_name = _extract_alter_table_name(command)
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
        select_query_local = _rename_from_tables_to_local(select_query)

        # Determine local view and target table names
        view_name_local = _add_local_suffix(view_name)
        if view_name.endswith(VIEW_SUFFIX):
            target_table = view_name[: -len(VIEW_SUFFIX)] + LOCAL_TABLE_SUFFIX
        else:
            target_table = view_name + LOCAL_TABLE_SUFFIX

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

    def _execute_index_operation(self, command: str) -> None:
        """Execute ADD/DROP INDEX (only on local tables)."""
        local_command = _rename_alter_table_to_local(command)
        local_command = _format_with_on_cluster_sql(
            local_command, self.replicated_cluster
        )
        self.ch_client.command(local_command)

    def _execute_distributed_ddl(self, command: str) -> None:
        """Execute DDL in distributed mode (CREATE TABLE, CREATE/DROP VIEW)."""
        formatted_command = _format_with_on_cluster_sql(
            command, self.replicated_cluster
        )
        result = _format_distributed_sql(formatted_command, self.replicated_cluster)

        self.ch_client.command(result.local_command)
        if result.distributed_command:
            self.ch_client.command(result.distributed_command)


def _add_local_suffix(name: str) -> str:
    """Add _local suffix to a name if it doesn't already have it."""
    return name if name.endswith(LOCAL_TABLE_SUFFIX) else name + LOCAL_TABLE_SUFFIX


def _is_safe_identifier(value: str) -> bool:
    """Check if a string is safe to use as an identifier in SQL."""
    return bool(re.match(r"^[a-zA-Z0-9_\.]+$", value))


    """Extract table name from CREATE TABLE statement."""
    # Match "CREATE TABLE [IF NOT EXISTS] table_name"
    # Note: table_name can be qualified with database name (e.g., db.table)
    pattern = r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)"
    match = re.search(pattern, sql_query, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _rename_table_to_local(sql_query: str, table_name: str) -> str:
    """Rename table in CREATE TABLE statement to table_name_local."""
    pattern = rf"(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?){table_name}\b"
    return re.sub(
        pattern, rf"\1{table_name}{LOCAL_TABLE_SUFFIX}", sql_query, flags=re.IGNORECASE
    )


def _rename_alter_table_to_local(sql_query: str) -> str:
    """Rename table in ALTER TABLE statement to table_name_local."""
    pattern = r"(ALTER\s+TABLE\s+)([a-zA-Z0-9_.]+)(\s+)"

    def add_suffix(match: re.Match[str]) -> str:
        table_name = match.group(2)
        table_name = _add_local_suffix(table_name)
        return f"{match.group(1)}{table_name}{match.group(3)}"

    return re.sub(pattern, add_suffix, sql_query, flags=re.IGNORECASE)


def _extract_alter_table_name(sql_query: str) -> str | None:
    """Extract table name from ALTER TABLE statement."""
    pattern = r"ALTER\s+TABLE\s+([a-zA-Z0-9_.]+)"
    match = re.search(pattern, sql_query, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _rename_from_tables_to_local(sql_query: str) -> str:
    """Rename table references in FROM clauses and qualified column names to use _local suffix.

    This is needed for materialized views in distributed mode where the local view
    should reference local tables (e.g., FROM call_parts_local and call_parts_local.column).

    Args:
        sql_query: The SQL query containing FROM clauses and table references

    Returns:
        SQL query with table names in FROM clauses and qualified column references renamed to include _local suffix
    """
    # First, strip out SQL comments to avoid matching "from" in comments
    # Remove single-line comments (-- comment)
    lines = sql_query.split("\n")
    sql_without_comments = []
    comment_lines = {}  # Store comments to restore later
    for i, line in enumerate(lines):
        if "--" in line:
            # Split on first occurrence of --
            code_part, comment_part = line.split("--", 1)
            sql_without_comments.append(code_part)
            comment_lines[i] = comment_part
        else:
            sql_without_comments.append(line)

    sql_to_process = "\n".join(sql_without_comments)

    # Match FROM keyword followed by table name
    # Use lookbehind to ensure FROM is either at start or preceded by whitespace/newline
    from_pattern = r"(?<=\s)FROM\s+([a-zA-Z0-9_.]+)\b|^FROM\s+([a-zA-Z0-9_.]+)\b"

    def add_suffix_to_from(match: re.Match[str]) -> str:
        # Group 1 is for FROM after whitespace, Group 2 is for FROM at start
        table_name = match.group(1) if match.group(1) else match.group(2)
        table_name = _add_local_suffix(table_name)
        return f"FROM {table_name}"

    # Collect table names from FROM clauses before renaming
    table_names = set()
    for match in re.finditer(
        from_pattern, sql_to_process, flags=re.IGNORECASE | re.MULTILINE
    ):
        table_name = match.group(1) if match.group(1) else match.group(2)
        # Handle database.table format - extract just the table name
        if "." in table_name:
            table_name = table_name.split(".")[-1]
        if not table_name.endswith(LOCAL_TABLE_SUFFIX):
            table_names.add(table_name)

    # Now rename FROM clauses
    sql_to_process = re.sub(
        from_pattern,
        add_suffix_to_from,
        sql_to_process,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Second, handle qualified column references (table_name.column_name) for tables we found in FROM clauses
    for table_name in table_names:
        # Match table_name.column_name
        qualified_pattern = rf"\b{re.escape(table_name)}\.([a-zA-Z0-9_]+)\b"
        replacement = rf"{table_name}{LOCAL_TABLE_SUFFIX}.\1"
        sql_to_process = re.sub(
            qualified_pattern, replacement, sql_to_process, flags=re.IGNORECASE
        )

    # Restore comments
    result_lines = sql_to_process.split("\n")
    for i, comment in comment_lines.items():
        if i < len(result_lines):
            result_lines[i] = result_lines[i] + "--" + comment

    return "\n".join(result_lines)


def _create_db_sql(
    db_name: str, replicated: bool, replicated_cluster: str, replicated_path: str
) -> str:
    """Generate SQL database create string for normal and replicated databases.

    Args:
        db_name: Name of the database to create
        replicated: Whether to use replicated tables (not database engine)
        replicated_cluster: The cluster name to use for replication
        replicated_path: The ZooKeeper path template for replication (unused for database creation)

    Returns:
        SQL string to create the database
    """
    if not _is_safe_identifier(db_name):
        raise MigrationError(f"Invalid database name: {db_name}")

    cluster_clause = ""
    if replicated:
        if not _is_safe_identifier(replicated_cluster):
            raise MigrationError(f"Invalid cluster name: {replicated_cluster}")
        cluster_clause = f" ON CLUSTER {replicated_cluster}"

    return f"CREATE DATABASE IF NOT EXISTS {db_name}{cluster_clause}"


def _format_replicated_sql(
    sql_query: str,
    use_distributed: bool = False,
    target_db: str | None = None,
) -> str:
    """Format SQL query to use replicated engines.

    Args:
        sql_query: The SQL query to transform
        use_distributed: Whether to use explicit ZooKeeper paths with {shard} macro
        target_db: Target database name for path substitution

    Returns:
        SQL with MergeTree engines converted to ReplicatedMergeTree variants
    """
    # Match any MergeTree variant engine (including custom ones)
    pattern = r"ENGINE\s*=\s*(\w+)?MergeTree\b(\(\))?"

    def replace_engine(match: re.Match[str]) -> str:
        engine_prefix = match.group(1) or ""
        if engine_prefix.lower().startswith("replicated"):
            return match.group(0)

        if use_distributed and target_db:
            table_name = _extract_table_name(sql_query)
            if table_name:
                if "." in table_name:
                    table_name = table_name.split(".")[-1]

                # When using distributed tables, append _local suffix to the table name in the path
                local_table_name = table_name + LOCAL_TABLE_SUFFIX
                return f"ENGINE = Replicated{engine_prefix}MergeTree('/clickhouse/tables/{{shard}}/{target_db}/{local_table_name}', '{{replica}}')"

        return f"ENGINE = Replicated{engine_prefix}MergeTree"

    return re.sub(pattern, replace_engine, sql_query, flags=re.IGNORECASE)


def _format_alter_with_on_cluster_sql(sql_query: str, cluster_name: str) -> str:
    """Format ALTER TABLE statements to include ON CLUSTER clause.

    Args:
        sql_query: The SQL query to transform
        cluster_name: The cluster name to use in the ON CLUSTER clause

    Returns:
        Transformed SQL with ON CLUSTER added if applicable
    """
    # Check if this is an ALTER TABLE statement and doesn't already have ON CLUSTER
    if re.search(r"\bALTER\s+TABLE\b", sql_query, flags=re.IGNORECASE):
        # Don't add if already present
        if re.search(r"\bON\s+CLUSTER\b", sql_query, flags=re.IGNORECASE):
            return sql_query

        pattern = r"(\bALTER\s+TABLE\s+)([a-zA-Z0-9_]+)(\s+)"

        def add_cluster(match: re.Match[str]) -> str:
            return f"{match.group(1)}{match.group(2)} ON CLUSTER {cluster_name}{match.group(3)}"

        return re.sub(pattern, add_cluster, sql_query, flags=re.IGNORECASE)

    return sql_query


def _format_create_table_with_on_cluster_sql(sql_query: str, cluster_name: str) -> str:
    """Format CREATE TABLE statements to include ON CLUSTER clause.

    Args:
        sql_query: The SQL query to transform
        cluster_name: The cluster name to use in the ON CLUSTER clause

    Returns:
        Transformed SQL with ON CLUSTER added if applicable
    """
    # Check if this is a CREATE TABLE statement and doesn't already have ON CLUSTER
    if re.search(r"\bCREATE\s+TABLE\b", sql_query, flags=re.IGNORECASE):
        # Don't add if already present
        if re.search(r"\bON\s+CLUSTER\b", sql_query, flags=re.IGNORECASE):
            return sql_query

        # Match "CREATE TABLE [IF NOT EXISTS] table_name" and add ON CLUSTER after table name
        # Note: table_name can be qualified with database name (e.g., db.table)
        pattern = (
            r"(\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)([a-zA-Z0-9_.]+)(\s*\()"
        )

        def add_cluster(match: re.Match[str]) -> str:
            return f"{match.group(1)}{match.group(2)} ON CLUSTER {cluster_name}{match.group(3)}"

        return re.sub(pattern, add_cluster, sql_query, flags=re.IGNORECASE)

    return sql_query


def _format_drop_view_with_on_cluster_sql(sql_query: str, cluster_name: str) -> str:
    """Format DROP VIEW statements to include ON CLUSTER clause.

    Args:
        sql_query: The SQL query to transform
        cluster_name: The cluster name to use in the ON CLUSTER clause

    Returns:
        Transformed SQL with ON CLUSTER added if applicable
    """
    # Check if this is a DROP VIEW statement and doesn't already have ON CLUSTER
    if re.search(r"\bDROP\s+VIEW\b", sql_query, flags=re.IGNORECASE):
        # Don't add if already present
        if re.search(r"\bON\s+CLUSTER\b", sql_query, flags=re.IGNORECASE):
            return sql_query

        # Match "DROP VIEW [IF EXISTS] view_name" and add ON CLUSTER after view name
        # Note: view_name can be qualified with database name (e.g., db.view)
        pattern = r"(\bDROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?)([a-zA-Z0-9_.]+)(\s|$)"

        def add_cluster(match: re.Match[str]) -> str:
            return f"{match.group(1)}{match.group(2)} ON CLUSTER {cluster_name}{match.group(3)}"

        return re.sub(pattern, add_cluster, sql_query, flags=re.IGNORECASE)

    return sql_query


def _format_create_view_with_on_cluster_sql(sql_query: str, cluster_name: str) -> str:
    """Format CREATE VIEW statements to include ON CLUSTER clause.

    Args:
        sql_query: The SQL query to transform
        cluster_name: The cluster name to use in the ON CLUSTER clause

    Returns:
        Transformed SQL with ON CLUSTER added if applicable
    """
    # Check if this is a CREATE VIEW statement and doesn't already have ON CLUSTER
    if re.search(r"\bCREATE\s+VIEW\b", sql_query, flags=re.IGNORECASE):
        # Don't add if already present
        if re.search(r"\bON\s+CLUSTER\b", sql_query, flags=re.IGNORECASE):
            return sql_query

        # Match "CREATE VIEW [IF NOT EXISTS] view_name" and add ON CLUSTER after view name
        # Note: view_name can be qualified with database name (e.g., db.view)
        pattern = r"(\bCREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?)([a-zA-Z0-9_.]+)(\s+)"

        def add_cluster(match: re.Match[str]) -> str:
            return f"{match.group(1)}{match.group(2)} ON CLUSTER {cluster_name}{match.group(3)}"

        return re.sub(pattern, add_cluster, sql_query, flags=re.IGNORECASE)

    return sql_query


def _format_with_on_cluster_sql(sql_query: str, cluster_name: str) -> str:
    """Generic function to format various DDL statements with ON CLUSTER clause.

    This function consolidates the logic for adding ON CLUSTER to multiple DDL types:
    - ALTER TABLE
    - CREATE TABLE
    - DROP VIEW
    - CREATE VIEW

    Args:
        sql_query: The SQL query to transform
        cluster_name: The cluster name to use in the ON CLUSTER clause

    Returns:
        Transformed SQL with ON CLUSTER added if applicable
    """
    # Apply transformations in order
    sql_query = _format_alter_with_on_cluster_sql(sql_query, cluster_name)
    sql_query = _format_create_table_with_on_cluster_sql(sql_query, cluster_name)
    sql_query = _format_drop_view_with_on_cluster_sql(sql_query, cluster_name)
    sql_query = _format_create_view_with_on_cluster_sql(sql_query, cluster_name)
    return sql_query


def _create_distributed_table_sql(
    table_name: str, local_table_name: str, cluster_name: str
) -> str:
    """Generate SQL to create a distributed table on top of a local replicated table.

    Args:
        table_name: Name for the distributed table
        local_table_name: Base name for the local table (will have _local appended)
        cluster_name: The cluster name to use

    Returns:
        SQL string to create the distributed table
    """
    distributed_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} ON CLUSTER {cluster_name}
        AS {local_table_name}{LOCAL_TABLE_SUFFIX}
        ENGINE = Distributed({cluster_name}, currentDatabase(), {local_table_name}{LOCAL_TABLE_SUFFIX}, rand())
    """
    return distributed_sql


def _format_distributed_sql(
    sql_query: str, cluster_name: str
) -> DistributedTransformResult:
    """Format SQL to create distributed tables.

    Args:
        sql_query: The SQL query to transform
        cluster_name: The cluster name to use for distributed tables

    Returns:
        DistributedTransformResult with local_command and optional distributed_command.
        If sql_query is not a CREATE TABLE statement, distributed_command will be None.
    """
    # Check if this is a CREATE TABLE statement
    table_name = _extract_table_name(sql_query)
    if not table_name:
        return DistributedTransformResult(
            local_command=sql_query, distributed_command=None
        )

    # Rename the table to table_name_local
    local_command = _rename_table_to_local(sql_query, table_name)

    # Create the distributed table
    distributed_command = _create_distributed_table_sql(
        table_name, table_name, cluster_name
    )

    return DistributedTransformResult(
        local_command=local_command, distributed_command=distributed_command
    )
