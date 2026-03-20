from __future__ import annotations

import logging
import os
from typing import Literal

from pydantic import BaseModel

from weave.durability.wal import WALWriter

WALRecordType = Literal["obj_create", "table_create", "file_create"]
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_writer import JSONLWALWriter

logger = logging.getLogger(__name__)


class WALManager:
    """Owns the lifecycle of a project-scoped Write-Ahead Log.

    When *enabled* is False the manager is a no-op: write() and flush()
    return immediately with zero overhead.
    """

    def __init__(self, entity: str, project: str, *, enabled: bool) -> None:
        self.wal_dir: str | None = None
        self._writer: WALWriter | None = None

        if enabled:
            self.wal_dir = os.path.join(
                os.path.expanduser("~"),
                ".weave",
                "wal",
                entity,
                project,
            )
            dir_mgr = FileWALDirectoryManager(self.wal_dir)
            self._writer = JSONLWALWriter(dir_mgr)

    @property
    def enabled(self) -> bool:
        return self._writer is not None

    def write(self, record_type: WALRecordType, req: BaseModel) -> None:
        """Write a request to the WAL.  No-op when disabled.  Never raises."""
        if self._writer is None:
            return
        try:
            self._writer.write(
                {"type": record_type, "req": req.model_dump(mode="json")}
            )
        except Exception:
            logger.warning("Failed to write %s to WAL", record_type, exc_info=True)

    def flush(self) -> None:
        """Flush the WAL to disk.  No-op when disabled."""
        if self._writer is not None:
            self._writer.flush()

    def close(self) -> None:
        """Close the WAL writer.  No-op when disabled."""
        if self._writer is not None:
            self._writer.close()
            self._writer = None
