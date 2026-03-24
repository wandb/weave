from __future__ import annotations

import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)

from weave.durability.wal_lock import LOCK_EXT
from weave.durability.wal_writer import (
    DEFAULT_FSYNC_BATCH_SIZE,
    DEFAULT_FSYNC_TIMEOUT,
    _JSONLWALFileWriter,
)


class FileWALDirectoryManager:
    """Manages per-process WAL files in a shared project directory."""

    def __init__(
        self,
        directory: str,
        file_ext: str = ".jsonl",
        checkpoint_ext: str = ".checkpoint",
        dead_letter_ext: str = ".deadletter",
        fsync_batch_size: int = DEFAULT_FSYNC_BATCH_SIZE,
        fsync_timeout: float = DEFAULT_FSYNC_TIMEOUT,
    ) -> None:
        self._directory = directory
        self._file_ext = file_ext
        self._checkpoint_ext = checkpoint_ext
        self._dead_letter_ext = dead_letter_ext
        self._fsync_batch_size = fsync_batch_size
        self._fsync_timeout = fsync_timeout

    def create_file(self) -> _JSONLWALFileWriter:
        os.makedirs(self._directory, exist_ok=True)
        # Timestamp prefix ensures deterministic oldest-first ordering
        # when sorted alphabetically.  UUID suffix avoids collisions
        # between files created in the same nanosecond.
        ts = f"{time.time_ns():020d}"
        filename = f"{ts}_{uuid.uuid4().hex}{self._file_ext}"
        path = os.path.join(self._directory, filename)
        return _JSONLWALFileWriter(
            path,
            fsync_batch_size=self._fsync_batch_size,
            fsync_timeout=self._fsync_timeout,
        )

    def list_files(self) -> list[str]:
        if not os.path.isdir(self._directory):
            return []
        paths: list[str] = []
        for name in os.listdir(self._directory):
            if not name.endswith(self._file_ext):
                continue
            paths.append(os.path.join(self._directory, name))
        # Filenames start with a zero-padded nanosecond timestamp,
        # so alphabetical sort == chronological sort.
        paths.sort()
        return paths

    def remove(self, path: str) -> None:
        base, _ = os.path.splitext(path)
        # Sidecar extensions that accompany each WAL file:
        #   .checkpoint  — consumer read-offset tracker
        #   .deadletter  — records that failed all retry attempts
        #   .lock        — PID lock written by the active writer
        sidecars = (
            self._checkpoint_ext,
            self._dead_letter_ext,
            LOCK_EXT,
        )
        all_paths = [path] + [base + ext for ext in sidecars]
        for p in all_paths:
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
            except PermissionError:
                # On Windows, file handles may linger after close() due to
                # GC timing or antivirus scans.  The file will be retried
                # on the next drain cycle.
                logger.debug("Cannot remove %s (still locked), will retry later", p)
