from __future__ import annotations

import logging
import sqlite3
import tempfile
from pathlib import Path
from typing import Generic, NotRequired, TypedDict, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class ItemDict(TypedDict):
    type: str
    data: BaseModel
    _wal_id: NotRequired[int]


class SQLiteWriteAheadLog(Generic[T]):
    """A SQLite-based write-ahead log for durably storing batched operations.

    This class provides a durable storage mechanism for batched operations,
    ensuring that operations are not lost in case of crashes or failures.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        table_name: str = "batch_items",
        max_items: int = 1_000_000,
    ) -> None:
        """Initialize the SQLite write-ahead log.

        Args:
            db_path: Path to the SQLite database file. If None, a temporary file will be used.
            table_name: Name of the table to store batched items.
            max_items: Maximum number of items to keep in the WAL.
        """
        self.table_name = table_name
        self.max_items = max_items

        if db_path is None:
            # Create a directory in the user's temp directory
            weave_dir = Path(tempfile.gettempdir()) / "weave"
            weave_dir.mkdir(exist_ok=True)
            self.db_path = weave_dir / "weave_batch_wal.db"
        else:
            self.db_path = Path(db_path)

        # Ensure the directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database with the required schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Enable WAL mode and create the WAL table if it doesn't exist
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type TEXT NOT NULL,
                    item_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at
                ON {self.table_name} (created_at)
            """)

    def append(self, items: list[T]) -> None:
        """Append items to the write-ahead log.

        Args:
            items: List of items to append to the log.
        """
        if not items:
            return

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            batch_data = [
                (
                    item.__class__.__name__,  # item_type
                    item.model_dump_json(),  # item_data
                )
                for item in items
            ]
            cursor.executemany(
                f"INSERT INTO {self.table_name} (item_type, item_data) VALUES (?, ?)",
                batch_data,
            )

            # Clean up old items if we have too many
            self._cleanup(cursor)

    def _cleanup(self, cursor: sqlite3.Cursor) -> None:
        """Clean up old items if we have too many."""
        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        count = cursor.fetchone()[0]

        if count > self.max_items:
            # Delete the oldest items, keeping max_items
            cursor.execute(f"""
                DELETE FROM {self.table_name}
                WHERE id IN (
                    SELECT id FROM {self.table_name}
                    ORDER BY created_at ASC
                    LIMIT {count - self.max_items}
                )
            """)

    def get_all_items(self, item_types: list[str] | None = None) -> list[ItemDict]:
        """Get all items from the write-ahead log.

        Args:
            item_types: Optional list of item types to filter by.

        Returns:
            List of items as dictionaries.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            if item_types:
                placeholders = ", ".join("?" for _ in item_types)
                cursor.execute(
                    f"""
                    SELECT id, item_type, item_data FROM {self.table_name}
                    WHERE item_type IN ({placeholders})
                    ORDER BY id ASC
                    """,
                    item_types,
                )
            else:
                cursor.execute(
                    f"""
                    SELECT id, item_type, item_data FROM {self.table_name}
                    ORDER BY id ASC
                    """
                )

            items = []
            for row in cursor.fetchall():
                id_, item_type, item_data = row
                try:
                    data = _load_pydantic(item_type, item_data)
                except Exception:
                    logger.warning(
                        f"Skipping item because failed to parse item data from WAL: {item_data}"
                    )
                    continue
                items.append(ItemDict(type=item_type, data=data, _wal_id=id_))

            return items

    def delete_items(self, ids: list[int]) -> None:
        """Delete items from the write-ahead log by their IDs.

        Args:
            ids: List of item IDs to delete.
        """
        if not ids:
            return

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            placeholders = ", ".join("?" for _ in ids)
            cursor.execute(
                f"DELETE FROM {self.table_name} WHERE id IN ({placeholders})", ids
            )

    def clear(self) -> None:
        """Clear all items from the write-ahead log."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.table_name}")


def _load_pydantic(item_type: str, item_data: str) -> BaseModel:
    """Loads a pydantic model from a string."""
    if item_type == "StartBatchItem":
        from weave.trace_server_bindings.remote_http_trace_server import StartBatchItem

        return StartBatchItem.model_validate_json(item_data)
    elif item_type == "EndBatchItem":
        from weave.trace_server_bindings.remote_http_trace_server import EndBatchItem

        return EndBatchItem.model_validate_json(item_data)

    raise ValueError(f"Unknown item type: {item_type}")
