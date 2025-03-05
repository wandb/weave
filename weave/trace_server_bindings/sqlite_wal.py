from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class SQLiteWriteAheadLog:
    """A SQLite-based write-ahead log for durably storing batched operations.

    This class provides a durable storage mechanism for batched operations,
    ensuring that operations are not lost in case of crashes or failures.
    """

    def __init__(
        self,
        db_path: str | None = None,
        table_name: str = "batch_items",
        max_items: int = 10000,
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
            weave_dir = os.path.join(tempfile.gettempdir(), "weave")
            os.makedirs(weave_dir, exist_ok=True)
            self.db_path = os.path.join(weave_dir, "weave_batch_wal.db")
        else:
            self.db_path = db_path

        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        # Initialize the database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database with the required schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Enable WAL mode for better performance and durability
            cursor.execute("PRAGMA journal_mode=WAL;")

            # Create the table if it doesn't exist
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type TEXT NOT NULL,
                    item_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create an index on created_at for faster cleanup
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at
                ON {self.table_name} (created_at)
            """)

            conn.commit()
        finally:
            conn.close()

    def append(self, items: list[T]) -> None:
        """Append items to the write-ahead log.

        Args:
            items: List of items to append to the log.
        """
        if not items:
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            for item in items:
                item_type = item.__class__.__name__
                item_data = item.model_dump_json()

                cursor.execute(
                    f"INSERT INTO {self.table_name} (item_type, item_data) VALUES (?, ?)",
                    (item_type, item_data),
                )

            conn.commit()

            # Clean up old items if we have too many
            self._cleanup(cursor)
            conn.commit()
        finally:
            conn.close()

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

    def get_all_items(self, item_types: list[str] | None = None) -> list[dict]:
        """Get all items from the write-ahead log.

        Args:
            item_types: Optional list of item types to filter by.

        Returns:
            List of items as dictionaries.
        """
        conn = sqlite3.connect(self.db_path)
        try:
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
                id, item_type, item_data = row
                item = json.loads(item_data)
                item["_wal_id"] = id  # Add the WAL ID for later deletion
                items.append({"type": item_type, "data": item})

            return items
        finally:
            conn.close()

    def delete_items(self, ids: list[int]) -> None:
        """Delete items from the write-ahead log by their IDs.

        Args:
            ids: List of item IDs to delete.
        """
        if not ids:
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            placeholders = ", ".join("?" for _ in ids)
            cursor.execute(
                f"DELETE FROM {self.table_name} WHERE id IN ({placeholders})", ids
            )

            conn.commit()
        finally:
            conn.close()

    def clear(self) -> None:
        """Clear all items from the write-ahead log."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.table_name}")
            conn.commit()
        finally:
            conn.close()
