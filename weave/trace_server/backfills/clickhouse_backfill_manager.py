import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from clickhouse_connect.driver.client import Client as CHClient

logger = logging.getLogger(__name__)

DEFAULT_REPLICATED_PATH = "/clickhouse/tables/{db}"
DEFAULT_REPLICATED_CLUSTER = "weave_cluster"


class BackfillError(RuntimeError):
    """Raised when a backfill error occurs."""


class ClickHouseBackfillManager:
    """Manages ClickHouse data backfills with checkpointing and resumability.

    Examples:
        manager = ClickHouseBackfillManager(ch_client)

        manager.list_backfills(database="weave")
        manager.run_backfill(database="weave", version=22)
        status = manager.get_status(database="weave", version=22)
    """

    def __init__(
        self,
        ch_client: CHClient,
        replicated: Optional[bool] = None,
        replicated_path: Optional[str] = None,
        replicated_cluster: Optional[str] = None,
    ):
        """Initialize the backfill manager.

        Args:
            ch_client (CHClient): ClickHouse client instance.
            replicated (Optional[bool]): Whether to use replicated tables. If None, auto-detect.
            replicated_path (Optional[str]): Path template for replicated tables.
            replicated_cluster (Optional[str]): Cluster name for replicated tables.
        """
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
        self._initialize_backfill_table()

    def _is_safe_identifier(self, value: str) -> bool:
        """Check if a string is safe to use as an identifier in SQL."""
        return bool(re.match(r"^[a-zA-Z0-9_\.]+$", value))

    def _format_time_range(self, checkpoint: dict, metadata: dict) -> str:
        """Format time range information for logging.

        Args:
            checkpoint (dict): Current checkpoint state.
            metadata (dict): Backfill metadata.

        Returns:
            str: Formatted time range string.
        """
        if "sortable_datetime" in metadata["checkpoint_columns"]:
            current_time = checkpoint.get("sortable_datetime", "1970-01-01 00:00:00")
            window_minutes = checkpoint.get("current_window_minutes", 60)

            # Calculate end time
            try:
                current_dt = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
                end_dt = current_dt + timedelta(minutes=window_minutes)
                end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                return f"[{current_time} +{window_minutes}m]"
            else:
                return f"[{current_time} to {end_time}]"
        else:
            # For non-time-based checkpointing, show checkpoint columns
            checkpoint_parts = []
            for col in metadata["checkpoint_columns"]:
                value = checkpoint.get(col, "")
                if value:
                    checkpoint_parts.append(f"{col}={value}")
            return f"[{', '.join(checkpoint_parts)}]" if checkpoint_parts else "[]"

    def _format_replicated_sql(self, sql_query: str) -> str:
        """Format SQL query to use replicated engines if replicated mode is enabled."""
        if not self.replicated:
            return sql_query

        pattern = r"ENGINE\s*=\s*(\w+)?MergeTree\b"

        def replace_engine(match: re.Match[str]) -> str:
            engine_prefix = match.group(1) or ""
            return f"ENGINE = Replicated{engine_prefix}MergeTree"

        return re.sub(pattern, replace_engine, sql_query, flags=re.IGNORECASE)

    def _initialize_backfill_table(self) -> None:
        """Create backfills table if it doesn't exist."""
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS db_management.backfills (
                backfill_id String,
                migration_version UInt64,
                db_name String,
                status String,
                checkpoint_data String,
                rows_processed UInt64 DEFAULT 0,
                started_at Nullable(DateTime64(3)),
                updated_at DateTime64(3) DEFAULT now64(3),
                completed_at Nullable(DateTime64(3)),
                error_log Nullable(String)
            ) ENGINE = MergeTree()
            ORDER BY (db_name, migration_version)
        """
        self.ch_client.command(self._format_replicated_sql(create_table_sql))

    def _discover_backfill_files(self) -> dict[int, dict[str, Any]]:
        """Scan backfills/migrations directory for backfill files.

        Returns:
            dict: Mapping of version to backfill metadata and paths.
        """
        backfill_dir = Path(__file__).parent / "migrations"
        if not backfill_dir.exists():
            return {}

        backfills = {}

        for file in backfill_dir.iterdir():
            if file.suffix == ".meta" and ".backfill" in file.name:
                version_str = file.name.split("_")[0]
                version = int(version_str)

                sql_file = backfill_dir / file.name.replace(".meta", ".sql")

                if not sql_file.exists():
                    raise BackfillError(
                        f"Missing SQL file for backfill version {version}: {sql_file}"
                    )

                with open(file) as f:
                    metadata = json.load(f)

                metadata = {k: v for k, v in metadata.items() if not k.startswith("_")}

                self._validate_metadata(metadata, version)

                backfills[version] = {
                    "sql_path": str(sql_file),
                    "metadata": metadata,
                }

        return backfills

    def _validate_metadata(self, metadata: dict, version: int) -> None:
        """Validate backfill metadata structure.

        Args:
            metadata (dict): Metadata to validate.
            version (int): Migration version for error messages.

        Raises:
            BackfillError: If metadata is invalid.
        """
        required = ["migration_version", "batch_size", "checkpoint_columns"]
        for field in required:
            if field not in metadata:
                raise BackfillError(
                    f"Missing required field '{field}' in backfill metadata for version {version}"
                )

        if metadata["migration_version"] != version:
            raise BackfillError(
                f"Metadata version mismatch: expected {version}, got {metadata['migration_version']}"
            )

        if not isinstance(metadata["batch_size"], int) or metadata["batch_size"] < 1:
            raise BackfillError(f"Invalid batch_size for version {version}")

        if (
            not isinstance(metadata["checkpoint_columns"], list)
            or len(metadata["checkpoint_columns"]) == 0
        ):
            raise BackfillError(f"Invalid checkpoint_columns for version {version}")

    def _load_checkpoint(self, backfill_id: str) -> Optional[dict]:
        """Load checkpoint from database.

        Args:
            backfill_id (str): Backfill identifier.

        Returns:
            Optional[dict]: Checkpoint data or None if not found.
        """
        query = f"SELECT checkpoint_data FROM db_management.backfills WHERE backfill_id = '{backfill_id}'"
        result = self.ch_client.query(query)

        if not result.result_rows:
            return None

        checkpoint_json = result.result_rows[0][0]
        try:
            return json.loads(checkpoint_json) if checkpoint_json else {}
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse checkpoint data for {backfill_id}: {e}")
            return {}

    def _save_checkpoint(self, backfill_id: str, checkpoint: dict) -> None:
        """Save checkpoint to database.

        Args:
            backfill_id (str): Backfill identifier.
            checkpoint (dict): Checkpoint data to save.
        """
        checkpoint_json = json.dumps(checkpoint)
        rows_processed = checkpoint.get("rows_processed", 0)

        self.ch_client.command(
            f"""
            ALTER TABLE db_management.backfills
            UPDATE
                checkpoint_data = '{checkpoint_json}',
                rows_processed = {rows_processed},
                updated_at = now64(3)
            WHERE backfill_id = '{backfill_id}'
        """
        )

    def _create_initial_checkpoint(self, metadata: dict, db_name: str) -> dict:
        """Create initial checkpoint with metadata defaults.

        Args:
            metadata (dict): Backfill metadata.
            db_name (str): Target database name.

        Returns:
            dict: Initial checkpoint.
        """
        checkpoint = {
            "current_batch_size": metadata["batch_size"],
            "current_window_minutes": 60,  # Default 60-minute window
            "rows_processed": 0,
            "batches_completed": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "backfill_start_time": time.time(),
        }

        for col in metadata["checkpoint_columns"]:
            if col == "sortable_datetime":
                # Find the actual oldest record in the database
                oldest_query = f"SELECT MIN(sortable_datetime) FROM {db_name}.calls_merged WHERE sortable_datetime IS NOT NULL"
                result = self.ch_client.query(oldest_query)
                if result.result_rows and result.result_rows[0][0]:
                    oldest_time = result.result_rows[0][0]
                    checkpoint[col] = oldest_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    # Fallback to 30 days ago if no data found
                    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                    checkpoint[col] = thirty_days_ago.strftime("%Y-%m-%d %H:%M:%S")
                    logger.warning("No data found, starting from 30 days ago")

        checkpoint.update(self._calculate_custom_fields(metadata, db_name))

        return checkpoint

    def _calculate_custom_fields(self, metadata: dict, db_name: str) -> dict:
        """Calculate any custom fields needed for this backfill.

        Args:
            metadata (dict): Backfill metadata.
            db_name (str): Target database name.

        Returns:
            dict: Custom fields to add to checkpoint.
        """
        custom_fields = {}

        if "cutover_timestamp" in metadata.get("custom_fields", []):
            # Check if cutover_timestamp is provided directly in metadata
            if "cutover_timestamp" in metadata:
                custom_fields["cutover_timestamp"] = metadata["cutover_timestamp"]
            else:
                # Calculate dynamically from data
                query = f"SELECT dateAdd(HOUR, -1, MIN(started_at)) as cutover FROM {db_name}.call_parts WHERE started_at IS NOT NULL"

                try:
                    result = self.ch_client.query(query)

                    if result.result_rows and result.result_rows[0][0]:
                        cutover_value = result.result_rows[0][0]
                        custom_fields["cutover_timestamp"] = cutover_value.isoformat()
                    else:
                        logger.warning("No cutover value found")
                except Exception as e:
                    logger.exception("Error calculating cutover timestamp")
                    raise

        if "dedup_window_seconds" in metadata:
            custom_fields["dedup_window_seconds"] = metadata["dedup_window_seconds"]

        return custom_fields

    def _render_sql(
        self, template: str, checkpoint: dict, metadata: dict, db_name: str
    ) -> str:
        """Render SQL template with checkpoint values.

        Args:
            template (str): SQL template with placeholders.
            checkpoint (dict): Current checkpoint state.
            metadata (dict): Backfill metadata.
            db_name (str): Target database name.

        Returns:
            str: Rendered SQL query.
        """
        sql = template

        sql = sql.replace("{db}", db_name)

        sql = sql.replace(
            "{batch_size}",
            str(checkpoint.get("current_batch_size", metadata["batch_size"])),
        )

        # Set default window to 60 minutes for time-based checkpointing
        window_minutes = checkpoint.get("current_window_minutes", 60)
        sql = sql.replace("{window_minutes}", str(window_minutes))

        for col in metadata["checkpoint_columns"]:
            value = checkpoint.get(col, "")
            placeholder = f"{{checkpoint_{col}}}"
            sql = sql.replace(placeholder, str(value))

        for key, value in checkpoint.items():
            if (
                key
                not in [
                    "current_batch_size",
                    "rows_processed",
                    "batches_completed",
                    "started_at",
                    "last_updated",
                ]
                and key not in metadata["checkpoint_columns"]
            ):
                placeholder = f"{{{key}}}"
                sql = sql.replace(placeholder, str(value))

        return sql

    def _render_sql_with_batch_size(self, sql: str, batch_size: int) -> str:
        """Re-render SQL with a specific batch size for retry attempts.

        Args:
            sql (str): Already rendered SQL query.
            batch_size (int): New batch size to use.

        Returns:
            str: SQL with updated batch size.
        """
        # Find the LIMIT clause and replace the number
        import re

        pattern = r"LIMIT\s+\d+"
        replacement = f"LIMIT {batch_size}"
        return re.sub(pattern, replacement, sql, flags=re.IGNORECASE)

    def _advance_checkpoint_by_window(
        self, checkpoint: dict, current_time: str
    ) -> None:
        """Advance checkpoint by the current window size.

        Args:
            checkpoint (dict): Current checkpoint state.
            current_time (str): Current time string to advance from.
        """
        window_minutes = checkpoint.get("current_window_minutes", 60)
        advance_query = f"SELECT dateAdd(MINUTE, {window_minutes}, toDateTime64('{current_time}', 6)) as new_time"
        advance_result = self.ch_client.query(advance_query)
        if advance_result.result_rows and advance_result.result_rows[0][0]:
            new_time = advance_result.result_rows[0][0]
            checkpoint["sortable_datetime"] = new_time.strftime("%Y-%m-%d %H:%M:%S")

    def _execute_batch(self, sql: str, checkpoint: dict, metadata: dict) -> dict:
        """Execute a single batch with time window reduction retry logic.

        Args:
            sql (str): Rendered SQL query.
            checkpoint (dict): Current checkpoint state.
            metadata (dict): Backfill metadata.

        Returns:
            dict: Result with rows_affected, success, optional error, execution_time, and max_started_at.
        """
        batch_size = checkpoint.get("current_batch_size", metadata["batch_size"])
        max_retries = metadata.get("max_retries", 3)
        timeout = metadata.get("timeout_seconds", 3600)

        batch_start_time = time.time()

        for attempt in range(max_retries):
            try:
                result = self.ch_client.query(
                    sql,
                    settings={
                        "max_execution_time": timeout,
                        # TODO: make constant
                        "max_memory_usage": "10000000000",
                    },
                )

                rows_affected = 0
                if hasattr(result, "summary") and result.summary:
                    rows_affected = int(result.summary.get("written_rows", 0))
                    batch_execution_time = time.time() - batch_start_time
                    return {
                        "rows_affected": rows_affected,
                        "success": True,
                        "error": None,
                        "execution_time": batch_execution_time,
                    }
                else:
                    batch_execution_time = time.time() - batch_start_time
                    return {
                        "rows_affected": rows_affected,
                        "success": True,
                        "error": None,
                        "execution_time": batch_execution_time,
                    }

            except Exception as e:
                error_msg = str(e).lower()

                # Check if this is an OOM error
                if "memory" in error_msg or "too many" in error_msg:
                    # For time-based checkpointing, reduce the time window instead of batch size
                    if "sortable_datetime" in metadata["checkpoint_columns"]:
                        current_window_minutes = checkpoint.get(
                            "current_window_minutes", 60
                        )  # Default 60 minutes
                        new_window_minutes = current_window_minutes / 2

                        if new_window_minutes < 1:  # Minimum 1 minute
                            batch_execution_time = time.time() - batch_start_time
                            return {
                                "rows_affected": 0,
                                "success": False,
                                "error": f"Time window too small after retries: {e}",
                                "execution_time": batch_execution_time,
                            }

                        logger.warning(
                            f"OOM on attempt {attempt + 1}, reducing time window to {new_window_minutes} minutes"
                        )
                        checkpoint["current_window_minutes"] = new_window_minutes

                        # Return a special status indicating we need to re-render SQL with new window
                        batch_execution_time = time.time() - batch_start_time
                        return {
                            "rows_affected": 0,
                            "success": False,
                            "error": "RENDER_SQL",
                            "retry": True,
                            "execution_time": batch_execution_time,
                        }
                    else:
                        # For non-time-based checkpointing, fall back to batch size reduction
                        batch_size = batch_size // 2
                        if batch_size < 1000:
                            batch_execution_time = time.time() - batch_start_time
                            return {
                                "rows_affected": 0,
                                "success": False,
                                "error": f"Batch size too small after retries: {e}",
                                "execution_time": batch_execution_time,
                            }

                        logger.warning(
                            f"OOM on attempt {attempt + 1}, reducing batch size to {batch_size}"
                        )
                        checkpoint["current_batch_size"] = batch_size
                        continue

                # For non-OOM errors, retry with exponential backoff
                logger.exception(f"Batch execution failed on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    batch_execution_time = time.time() - batch_start_time
                    return {
                        "rows_affected": 0,
                        "success": False,
                        "error": str(e),
                        "execution_time": batch_execution_time,
                    }

                time.sleep(2**attempt)

        batch_execution_time = time.time() - batch_start_time
        return {
            "rows_affected": 0,
            "success": False,
            "error": "Max retries exceeded",
            "execution_time": batch_execution_time,
        }

    def _get_last_inserted_position(self, db_name: str, metadata: dict) -> dict:
        """Get the last inserted position from target table.

        Args:
            db_name (str): Target database name.
            metadata (dict): Backfill metadata.

        Returns:
            dict: Dictionary with checkpoint column values.
        """
        target_table = metadata.get(
            "target_table", metadata.get("description", "").split()[-1]
        )
        checkpoint_cols = metadata["checkpoint_columns"]

        # This method is only used for non-time-based checkpointing
        # Time-based checkpointing is handled directly in run_backfill
        max_selects = [f"MAX({col}) as {col}" for col in checkpoint_cols]
        query = f"SELECT {', '.join(max_selects)} FROM {db_name}.{target_table}"

        result = self.ch_client.query(query)

        if not result.result_rows:
            return {
                col: ("1970-01-01 00:00:00" if col == "sortable_datetime" else "")
                for col in checkpoint_cols
            }

        row = result.result_rows[0]
        return {
            col: (
                row[i]
                if row[i] is not None
                else ("1970-01-01 00:00:00" if col == "sortable_datetime" else "")
            )
            for i, col in enumerate(checkpoint_cols)
        }

    def _register_backfill(
        self,
        backfill_id: str,
        db_name: str,
        version: int,
        metadata: dict,
        checkpoint: dict,
    ) -> None:
        """Register a new backfill in the tracking table.

        Args:
            backfill_id (str): Unique backfill identifier.
            db_name (str): Target database name.
            version (int): Migration version.
            metadata (dict): Backfill metadata.
            checkpoint (dict): Initial checkpoint.
        """
        checkpoint_json = json.dumps(checkpoint)
        description = metadata.get("description", "")

        now = datetime.now(timezone.utc)
        self.ch_client.insert(
            "db_management.backfills",
            data=[
                [
                    backfill_id,
                    version,
                    db_name,
                    "pending",
                    checkpoint_json,
                    0,
                    None,
                    now,
                    None,
                    None,
                ]
            ],
            # TODO: this should be a constant
            column_names=[
                "backfill_id",
                "migration_version",
                "db_name",
                "status",
                "checkpoint_data",
                "rows_processed",
                "started_at",
                "updated_at",
                "completed_at",
                "error_log",
            ],
        )

    def _update_status(
        self, backfill_id: str, status: str, error: Optional[str] = None
    ) -> None:
        """Update backfill status in tracking table.

        Args:
            backfill_id (str): Backfill identifier.
            status (str): New status value.
            error (Optional[str]): Error message if failed.
        """
        updates = [f"status = '{status}'", "updated_at = now64(3)"]

        if status == "running":
            updates.append("started_at = now64(3)")
        elif status == "completed":
            updates.append("completed_at = now64(3)")

        if error:
            error_escaped = error.replace("'", "\\'")
            updates.append(f"error_log = '{error_escaped}'")

        self.ch_client.command(
            f"""
            ALTER TABLE db_management.backfills
            UPDATE {", ".join(updates)}
            WHERE backfill_id = '{backfill_id}'
        """
        )

    def run_backfill(
        self, database: str, version: int, max_batches: Optional[int] = None
    ) -> None:
        """Execute a backfill from current checkpoint to completion.

        Args:
            database (str): Target database name.
            version (int): Migration version number.
            max_batches (Optional[int]): Optional limit for testing/debugging.
        """
        backfill_id = f"{database}_{version}"

        backfills = self._discover_backfill_files()
        backfill = backfills.get(version)
        if not backfill:
            raise BackfillError(f"No backfill found for version {version}")

        sql_template = Path(backfill["sql_path"]).read_text()
        metadata = backfill["metadata"]

        checkpoint = self._load_checkpoint(backfill_id)
        if not checkpoint:
            checkpoint = self._create_initial_checkpoint(metadata, database)
            self._register_backfill(
                backfill_id, database, version, metadata, checkpoint
            )
        else:
            # Ensure backfill_start_time is set for resumed backfills
            if "backfill_start_time" not in checkpoint:
                checkpoint["backfill_start_time"] = time.time()

        self._update_status(backfill_id, "running")

        try:
            batch_num = checkpoint.get("batches_completed", 0)

            while True:
                if max_batches and batch_num >= max_batches:
                    logger.info(f"Reached max_batches limit: {max_batches}")
                    break

                sql = self._render_sql(sql_template, checkpoint, metadata, database)

                result = self._execute_batch(sql, checkpoint, metadata)

                if not result["success"]:
                    if result.get("retry") and result["error"] == "RENDER_SQL":
                        # Time window was reduced, re-render SQL and try again
                        continue
                    else:
                        self._update_status(backfill_id, "failed", result["error"])
                        raise BackfillError(
                            f"Batch execution failed: {result['error']}"
                        )

                # For time-based checkpointing, handle checkpoint advancement based on whether we hit batch limit
                if "sortable_datetime" in metadata["checkpoint_columns"]:
                    # Check if we've reached the end of available data
                    current_time = checkpoint.get(
                        "sortable_datetime", "1970-01-01 00:00:00"
                    )
                    max_time_query = f"SELECT MAX(sortable_datetime) FROM {database}.calls_merged WHERE sortable_datetime IS NOT NULL"
                    max_result = self.ch_client.query(max_time_query)

                    if max_result.result_rows and max_result.result_rows[0][0]:
                        max_time = max_result.result_rows[0][0]
                        current_time_dt = datetime.strptime(
                            current_time, "%Y-%m-%d %H:%M:%S"
                        )

                        # If we've processed past the maximum time in the table, we're done
                        if current_time_dt >= max_time:
                            self._update_status(backfill_id, "completed")
                            total_wall_time = time.time() - checkpoint.get(
                                "backfill_start_time", time.time()
                            )
                            total_time_str = f"{total_wall_time:.2f}s"
                            final_batch_size = checkpoint.get(
                                "current_batch_size", metadata["batch_size"]
                            )
                            logger.info(
                                f"Backfill {backfill_id} completed! Reached end of available data. Total time: {total_time_str}, final batch_size: {final_batch_size}"
                            )
                            self._print_status_table()
                            break

                    # Determine how to advance the checkpoint
                    logger.debug(
                        f"Batch result: rows_affected={result['rows_affected']}, current_time={current_time}"
                    )
                    if result["rows_affected"] > 0:
                        # We processed rows - check if we hit the batch limit
                        batch_size = checkpoint.get(
                            "current_batch_size", metadata["batch_size"]
                        )
                        logger.debug(
                            f"Checking batch limit: rows_affected={result['rows_affected']}, batch_size={batch_size}"
                        )
                        # Check if we might have hit the batch limit
                        # If we processed exactly batch_size rows, we likely hit the LIMIT
                        if result["rows_affected"] >= batch_size:
                            # We hit the batch limit - query for the started_at of the last processed call
                            logger.info(
                                f"Hit batch limit! rows_affected={result['rows_affected']}, batch_size={batch_size}"
                            )
                            window_minutes = checkpoint.get(
                                "current_window_minutes", 60
                            )
                            last_started_query = f"""
                                SELECT started_at
                                FROM {database}.calls_merged
                                WHERE sortable_datetime > toDateTime64('{current_time}', 6)
                                  AND sortable_datetime < dateAdd(MINUTE, {window_minutes}, toDateTime64('{current_time}', 6))
                                  AND started_at IS NOT NULL
                                  AND ended_at IS NOT NULL
                                ORDER BY started_at DESC
                                LIMIT 1
                            """
                            try:
                                last_started_result = self.ch_client.query(
                                    last_started_query
                                )
                                logger.debug(
                                    f"Last started query result: {last_started_result.result_rows}"
                                )
                                if (
                                    last_started_result.result_rows
                                    and last_started_result.result_rows[0][0]
                                ):
                                    last_started_at = last_started_result.result_rows[
                                        0
                                    ][0]
                                    last_started_at_str = last_started_at.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                    logger.info(
                                        f"Hit batch limit, advancing from {current_time} to last started_at: {last_started_at_str}"
                                    )
                                    checkpoint["sortable_datetime"] = (
                                        last_started_at_str
                                    )
                                    # Reset window to 60 minutes from this point
                                    checkpoint["current_window_minutes"] = 60
                                else:
                                    # Fallback to window advancement if no started_at found
                                    logger.warning(
                                        "Hit batch limit but no started_at found, falling back to window advancement"
                                    )
                                    self._advance_checkpoint_by_window(
                                        checkpoint, current_time
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to get last started_at: {e}, falling back to window advancement"
                                )
                                self._advance_checkpoint_by_window(
                                    checkpoint, current_time
                                )
                        else:
                            # We didn't hit the batch limit - advance by full window
                            logger.debug(
                                f"Didn't hit batch limit (rows_affected={result['rows_affected']} < batch_size={batch_size}), advancing by full window"
                            )
                            self._advance_checkpoint_by_window(checkpoint, current_time)
                    else:
                        # No rows processed - advance by full window
                        logger.debug("No rows processed, advancing by full window")
                        self._advance_checkpoint_by_window(checkpoint, current_time)
                else:
                    # For non-time-based checkpointing, stop if no rows were processed
                    if result["rows_affected"] == 0:
                        self._update_status(backfill_id, "completed")
                        total_wall_time = time.time() - checkpoint.get(
                            "backfill_start_time", time.time()
                        )
                        total_time_str = f"{total_wall_time:.2f}s"
                        final_batch_size = checkpoint.get(
                            "current_batch_size", metadata["batch_size"]
                        )
                        logger.info(
                            f"Backfill {backfill_id} completed! Total time: {total_time_str}, final batch_size: {final_batch_size}"
                        )
                        self._print_status_table()
                        break

                checkpoint["rows_processed"] += result["rows_affected"]
                checkpoint["batches_completed"] = batch_num + 1
                checkpoint["last_updated"] = datetime.now(timezone.utc).isoformat()

                # Update timing information
                batch_execution_time = result.get("execution_time", 0)
                # Total time is wall clock time since backfill started
                total_wall_time = time.time() - checkpoint.get(
                    "backfill_start_time", time.time()
                )

                # For non-time-based checkpointing, update position from last inserted record
                if "sortable_datetime" not in metadata["checkpoint_columns"]:
                    new_position = self._get_last_inserted_position(database, metadata)
                    checkpoint.update(new_position)

                self._save_checkpoint(backfill_id, checkpoint)

                # Format timing information
                time_range = self._format_time_range(checkpoint, metadata)
                batch_time_str = f"{batch_execution_time:.2f}s"
                total_time_str = f"{total_wall_time:.2f}s"
                current_batch_size = checkpoint.get(
                    "current_batch_size", metadata["batch_size"]
                )

                logger.info(
                    f"Batch {batch_num + 1}: {result['rows_affected']} source rows processed, "
                    f"total: {checkpoint['rows_processed']} | "
                    f"batch: {batch_time_str}, total: {total_time_str} | "
                    f"batch_size: {current_batch_size} groups | {time_range}"
                )

                batch_num += 1

        except KeyboardInterrupt:
            logger.info(f"Backfill interrupted, checkpoint saved at batch {batch_num}")
            self._update_status(backfill_id, "paused")
            raise

    def _print_status_table(self) -> None:
        """Print a status table of all backfills."""
        backfills = self.list_backfills()

        if not backfills:
            logger.info("No backfills found")
            return

        # Print header
        logger.info("")
        logger.info(
            "Version    Database        Status       Rows Processed     Started              Updated"
        )
        logger.info("=" * 100)

        # Print each backfill
        for backfill in backfills:
            started = (
                backfill.get("started_at", "").strftime("%Y-%m-%d %H:%M:%S")
                if backfill.get("started_at")
                else ""
            )
            updated = (
                backfill.get("updated_at", "").strftime("%Y-%m-%d %H:%M:%S")
                if backfill.get("updated_at")
                else ""
            )

            logger.info(
                f"{backfill['migration_version']:<10} {backfill['db_name']:<15} {backfill['status']:<12} {backfill['rows_processed']:<17} {started:<19} {updated}"
            )

        logger.info("")

    def get_status(self, database: str, version: int) -> dict:
        """Get detailed status of a backfill.

        Args:
            database (str): Target database name.
            version (int): Migration version.

        Returns:
            dict: Status information including checkpoint and progress.
        """
        backfill_id = f"{database}_{version}"

        # TOD: use constant
        query = f"""
            SELECT
                backfill_id,
                migration_version,
                db_name,
                status,
                checkpoint_data,
                rows_processed,
                started_at,
                updated_at,
                completed_at,
                error_log
            FROM db_management.backfills
            WHERE backfill_id = '{backfill_id}'
        """

        result = self.ch_client.query(query)

        if not result.result_rows:
            return {"found": False, "backfill_id": backfill_id}

        row = result.result_rows[0]
        checkpoint_data = json.loads(row[4]) if row[4] else {}

        # TODO: pydantic type this
        return {
            "found": True,
            "backfill_id": row[0],
            "migration_version": row[1],
            "db_name": row[2],
            "status": row[3],
            "checkpoint": checkpoint_data,
            "rows_processed": row[5],
            "started_at": row[6],
            "updated_at": row[7],
            "completed_at": row[8],
            "error_log": row[9],
        }

    def list_backfills(
        self, database: Optional[str] = None, status: Optional[str] = None
    ) -> list[dict]:
        """List all backfills with optional filters.

        Args:
            database (Optional[str]): Filter by database name.
            status (Optional[str]): Filter by status.

        Returns:
            list[dict]: List of backfill status dictionaries.
        """
        # TODO: use constant
        query = """
            SELECT
                backfill_id,
                migration_version,
                db_name,
                status,
                rows_processed,
                started_at,
                updated_at,
                completed_at
            FROM db_management.backfills
        """

        filters = []
        if database:
            filters.append(f"db_name = '{database}'")
        if status:
            filters.append(f"status = '{status}'")

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY migration_version"

        result = self.ch_client.query(query)

        backfills = []
        for row in result.result_rows:
            # TODO: pydantic type this
            backfills.append(
                {
                    "backfill_id": row[0],
                    "migration_version": row[1],
                    "db_name": row[2],
                    "status": row[3],
                    "rows_processed": row[4],
                    "started_at": row[5],
                    "updated_at": row[6],
                    "completed_at": row[7],
                }
            )

        return backfills

    def pause_backfill(self, database: str, version: int) -> None:
        """Pause a running backfill.

        Args:
            database (str): Target database name.
            version (int): Migration version.
        """
        backfill_id = f"{database}_{version}"
        self._update_status(backfill_id, "paused")
        logger.info(f"Backfill {backfill_id} paused")

    def resume_backfill(
        self, database: str, version: int, max_batches: Optional[int] = None
    ) -> None:
        """Resume a paused or failed backfill.

        Args:
            database (str): Target database name.
            version (int): Migration version.
            max_batches (Optional[int]): Optional limit for testing/debugging.
        """
        status = self.get_status(database, version)

        if not status.get("found"):
            raise BackfillError(f"Backfill not found: {database}_{version}")

        if status["status"] not in ["paused", "failed"]:
            raise BackfillError(
                f"Cannot resume backfill with status: {status['status']}"
            )

        logger.info(f"Resuming backfill {database}_{version} from checkpoint")
        self.run_backfill(database, version, max_batches)

    def register_pending_backfills(
        self, db_name: str, migration_versions: list[int]
    ) -> None:
        """Register pending backfills for newly applied migrations.

        Args:
            db_name (str): Target database name.
            migration_versions (list[int]): List of migration versions to check.
        """
        backfills = self._discover_backfill_files()

        for version in migration_versions:
            if version not in backfills:
                continue

            backfill_id = f"{db_name}_{version}"
            metadata = backfills[version]["metadata"]

            existing = self.get_status(db_name, version)
            if existing.get("found"):
                logger.info(f"Backfill {backfill_id} already registered")
                continue

            checkpoint = self._create_initial_checkpoint(metadata, db_name)
            self._register_backfill(backfill_id, db_name, version, metadata, checkpoint)

            logger.info(f"Registered backfill {backfill_id}")

            if metadata.get("run_on_startup", False):
                logger.info(
                    f"Running backfill {backfill_id} inline (run_on_startup=true)"
                )
                self.run_backfill(db_name, version)
            else:
                logger.info(
                    f"Backfill {backfill_id} registered. Run manually: manager.run_backfill(database='{db_name}', version={version})"
                )
