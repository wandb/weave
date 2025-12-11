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


class MigrationError(RuntimeError):
    """Raised when a migration error occurs."""


@dataclass
class MigrationFileEntry:
    version: int
    name: str
    keys: list[str]
    is_up: bool


@dataclass
class MigrationStatus:
    db_name: str
    curr_version: int
    partially_applied_version: int | None


@dataclass
class MigrationInfo:
    up: str | None = None
    down: str | None = None
    keys: list[str] | None = None


class ClickHouseTraceServerMigrator:
    ch_client: CHClient
    replicated: bool
    replicated_path: str
    replicated_cluster: str
    management_db: str

    def __init__(
        self,
        ch_client: CHClient,
        replicated: bool | None = None,
        replicated_path: str | None = None,
        replicated_cluster: str | None = None,
        management_db: str = "db_management",
        migration_keys: list[str] | None = None,
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
        self.management_db = management_db
        if migration_keys is None:
            env_keys = os.environ.get("WEAVE_CH_MIGRATION_KEY", "")
            self.migration_keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        else:
            self.migration_keys = migration_keys
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
        if status.partially_applied_version:
            logger.info(
                f"Unable to apply migrations to `{target_db}`. Found partially applied migration version {status.partially_applied_version}. Please fix the database manually and try again."
            )
            return
        migration_map = self._get_migrations()
        migrations_to_apply = self._determine_migrations_to_apply(
            status.curr_version, migration_map, target_version
        )
        if len(migrations_to_apply) == 0:
            logger.info(f"No migrations to apply to `{target_db}`")
            if should_insert_costs(status.curr_version, target_version):
                insert_costs(self.ch_client, target_db)
            return
        logger.info(f"Migrations to apply: {migrations_to_apply}")
        if status.curr_version == 0:
            self.ch_client.command(self._create_db_sql(target_db))
        for target_version, migration_file in migrations_to_apply:
            # Check keys
            migration_keys = migration_map[target_version].keys or []
            if migration_keys and not any(
                k in self.migration_keys for k in migration_keys
            ):
                logger.info(
                    f"Skipping migration {migration_file} (version {target_version}) "
                    f"because keys {migration_keys} do not match active keys {self.migration_keys}"
                )
                # Mark as applied (skipped) by updating the version without running SQL
                self._update_migration_status(target_db, target_version, is_start=False)
                continue

            keys_msg = f" (keys: {migration_keys})" if migration_keys else ""
            logger.info(
                f"Applying migration {migration_file} to `{target_db}`{keys_msg}"
            )
            self._apply_migration(target_db, target_version, migration_file)
        if should_insert_costs(status.curr_version, target_version):
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

    def _get_migration_status(self, db_name: str) -> MigrationStatus:
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

        row = dict(zip(column_names, result_rows[0], strict=False))
        return MigrationStatus(
            db_name=row["db_name"],
            curr_version=row["curr_version"],
            partially_applied_version=row["partially_applied_version"],
        )

    def _parse_migration_filename(self, filename: str) -> MigrationFileEntry:
        """Parses a migration filename into its components.

        Args:
            filename: The migration filename (e.g., '1_init.up.sql' or '2_feature.experimental.up.sql').

        Returns:
            MigrationFileEntry containing version, name, keys, and direction.

        Raises:
            MigrationError: If the filename format is invalid.

        Example:
            >>> migrator._parse_migration_filename('2_feature.up.sql')
            MigrationFileEntry(version=2, name='feature', keys=[], is_up=True)
            >>> migrator._parse_migration_filename('3_feature.experimental.up.sql')
            MigrationFileEntry(version=3, name='feature', keys=['experimental'], is_up=True)
        """
        if not filename.endswith(".up.sql") and not filename.endswith(".down.sql"):
            raise MigrationError(f"Invalid migration file: {filename}")

        file_name_parts = filename.split("_", 1)
        if len(file_name_parts) <= 1:
            raise MigrationError(f"Invalid migration file: {filename}")

        try:
            version = int(file_name_parts[0], 10)
        except ValueError:
            raise MigrationError(
                f"Invalid migration version in file: {filename}"
            ) from None

        if version < 1:
            raise MigrationError(f"Invalid migration file: {filename}")

        is_up = filename.endswith(".up.sql")
        suffix = ".up.sql" if is_up else ".down.sql"

        # Remove suffix
        name_part = file_name_parts[1]
        if name_part.endswith(suffix):
            name_part = name_part[: -len(suffix)]

        # Parse keys from name (e.g. "feature.key1_key2" -> keys=["key1", "key2"])
        name_subparts = name_part.split(".")
        keys: list[str] = []
        if len(name_subparts) > 1:
            keys_str = ".".join(name_subparts[1:])
            keys = [k for k in keys_str.split("_") if k]

        return MigrationFileEntry(
            version=version, name=name_part, keys=keys, is_up=is_up
        )

    def _get_migrations(self) -> dict[int, MigrationInfo]:
        """Gets all migration files and returns a map of version to MigrationInfo.

        Returns:
            A dict mapping version number to MigrationInfo objects containing up and down migration filenames.

        Raises:
            MigrationError: If migrations are invalid or missing.
        """
        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        migration_files = os.listdir(migration_dir)
        migration_map: dict[int, MigrationInfo] = {}
        max_version = 0

        for file in migration_files:
            if not file.endswith(".up.sql") and not file.endswith(".down.sql"):
                continue  # Skip non-migration files

            try:
                entry = self._parse_migration_filename(file)
            except MigrationError:
                raise MigrationError(f"Invalid migration file: {file}") from None

            if entry.version not in migration_map:
                migration_map[entry.version] = MigrationInfo()

            # Validate consistency of keys between up/down files for the same version
            if migration_map[entry.version].keys is not None:
                existing_keys = migration_map[entry.version].keys or []
                if set(existing_keys) != set(entry.keys):
                    raise MigrationError(
                        f"Key mismatch for version {entry.version}: {existing_keys} vs {entry.keys}"
                    )
            else:
                migration_map[entry.version].keys = entry.keys

            if entry.is_up:
                if migration_map[entry.version].up is not None:
                    raise MigrationError(
                        f"Duplicate up migration file for version {entry.version}"
                    )
                migration_map[entry.version].up = file
            else:
                if migration_map[entry.version].down is not None:
                    raise MigrationError(
                        f"Duplicate down migration file for version {entry.version}"
                    )
                migration_map[entry.version].down = file

            if entry.version > max_version:
                max_version = entry.version

        if len(migration_map) == 0:
            raise MigrationError("No migrations found")

        if max_version != len(migration_map):
            raise MigrationError(
                f"Invalid migration versioning. Expected {max_version} migrations but found {len(migration_map)}"
            )

        for version in range(1, max_version + 1):
            if version not in migration_map:
                raise MigrationError(f"Missing migration file for version {version}")
            if migration_map[version].up is None:
                raise MigrationError(f"Missing up migration file for version {version}")
            if migration_map[version].down is None:
                raise MigrationError(
                    f"Missing down migration file for version {version}"
                )

        return migration_map

    def _determine_migrations_to_apply(
        self,
        current_version: int,
        migration_map: dict[int, MigrationInfo],
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
                up_file = migration_map[i].up
                if up_file is None:
                    raise MigrationError(f"Missing up migration file for version {i}")
                res.append((i, up_file))
            return res
        if target_version < current_version:
            logger.warning(
                f"Automatically running down migrations is disabled and should be done manually. Current version ({current_version}) is greater than target version ({target_version})."
            )
            # res = []
            # for i in range(current_version, target_version, -1):
            #     down_file = migration_map[i].down
            #     if down_file is None:
            #         raise MigrationError(f"Missing down migration file for version {i}")
            #     res.append((i - 1, down_file))
            # return res

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
