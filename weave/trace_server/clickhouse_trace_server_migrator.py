# Clickhouse Trace Server Manager
import logging
import os
import typing

from clickhouse_connect.driver.client import Client as CHClient

logger = logging.getLogger(__name__)


class ClickHouseTraceServerMigrator:
    ch_client: CHClient

    def __init__(
        self,
        ch_client: CHClient,
    ):
        super().__init__()
        self.ch_client = ch_client
        self._initialize_migration_db()

    def apply_migrations(
        self, target_db: str, target_version: typing.Optional[int] = None
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
            return
        logger.info(f"Migrations to apply: {migrations_to_apply}")
        if status["curr_version"] == 0:
            self.ch_client.command(f"CREATE DATABASE IF NOT EXISTS {target_db}")
        for target_version, migration_file in migrations_to_apply:
            self._apply_migration(target_db, target_version, migration_file)

    def _initialize_migration_db(self) -> None:
        self.ch_client.command(
            """
            CREATE DATABASE IF NOT EXISTS db_management
        """
        )
        self.ch_client.command(
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

    def _get_migration_status(self, db_name: str) -> typing.Dict:
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
            raise Exception("Migration table not found")

        return dict(zip(column_names, result_rows[0]))

    def _get_migrations(
        self,
    ) -> typing.Dict[int, typing.Dict[str, typing.Optional[str]]]:
        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        migration_files = os.listdir(migration_dir)
        migration_map: typing.Dict[int, typing.Dict[str, typing.Optional[str]]] = {}
        max_version = 0
        for file in migration_files:
            if not file.endswith(".up.sql") and not file.endswith(".down.sql"):
                raise Exception(f"Invalid migration file: {file}")
            file_name_parts = file.split("_", 1)
            if len(file_name_parts) <= 1:
                raise Exception(f"Invalid migration file: {file}")
            version = int(file_name_parts[0], 10)
            if version < 1:
                raise Exception(f"Invalid migration file: {file}")

            is_up = file.endswith(".up.sql")

            if version not in migration_map:
                migration_map[version] = {"up": None, "down": None}

            if is_up:
                if migration_map[version]["up"] is not None:
                    raise Exception(f"Duplicate migration file for version {version}")
                migration_map[version]["up"] = file
            else:
                if migration_map[version]["down"] is not None:
                    raise Exception(f"Duplicate migration file for version {version}")
                migration_map[version]["down"] = file

            if version > max_version:
                max_version = version

        if len(migration_map) == 0:
            raise Exception("No migrations found")

        if max_version != len(migration_map):
            raise Exception(
                f"Invalid migration versioning. Expected {max_version} migrations but found {len(migration_map)}"
            )

        for version in range(1, max_version + 1):
            if version not in migration_map:
                raise Exception(f"Missing migration file for version {version}")
            if migration_map[version]["up"] is None:
                raise Exception(f"Missing up migration file for version {version}")
            if migration_map[version]["down"] is None:
                raise Exception(f"Missing down migration file for version {version}")

        return migration_map

    def _determine_migrations_to_apply(
        self,
        current_version: int,
        migration_map: typing.Dict,
        target_version: typing.Optional[int] = None,
    ) -> typing.List[typing.Tuple[int, str]]:
        if target_version is None:
            target_version = len(migration_map)
        if target_version < 0 or target_version > len(migration_map):
            raise Exception(f"Invalid target version: {target_version}")

        if target_version > current_version:
            res = []
            for i in range(current_version + 1, target_version + 1):
                if migration_map[i]["up"] is None:
                    raise Exception(f"Missing up migration file for version {i}")
                res.append((i, f"{migration_map[i]['up']}"))
            return res
        if target_version < current_version:
            res = []
            for i in range(current_version, target_version, -1):
                if migration_map[i]["down"] is None:
                    raise Exception(f"Missing down migration file for version {i}")
                res.append((i - 1, f"{migration_map[i]['down']}"))
            return res

        return []

    def _apply_migration(
        self, target_db: str, target_version: int, migration_file: str
    ) -> None:
        logger.info(f"Applying migration {migration_file} to `{target_db}`")
        migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
        migration_file_path = os.path.join(migration_dir, migration_file)
        with open(migration_file_path, "r") as f:
            migration_sql = f.read()
        self.ch_client.command(
            f"""
            ALTER TABLE db_management.migrations UPDATE partially_applied_version = {target_version} WHERE db_name = '{target_db}'
        """
        )
        migration_sub_commands = migration_sql.split(";")
        for command in migration_sub_commands:
            command = command.strip()
            if len(command) == 0:
                continue
            curr_db = self.ch_client.database
            self.ch_client.database = target_db
            self.ch_client.command(command)
            self.ch_client.database = curr_db
        self.ch_client.command(
            f"""
            ALTER TABLE db_management.migrations UPDATE curr_version = {target_version}, partially_applied_version = NULL WHERE db_name = '{target_db}'
        """
        )
        logger.info(f"Migration {migration_file} applied to `{target_db}`")
