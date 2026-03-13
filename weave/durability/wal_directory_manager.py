from __future__ import annotations

import os
import time
import uuid

from weave.durability.wal_writer import JSONLWALWriter


class FileWALDirectoryManager:
    """Manages per-process WAL files in a shared project directory."""

    def __init__(
        self,
        directory: str,
        file_ext: str = ".jsonl",
        checkpoint_ext: str = ".checkpoint",
    ) -> None:
        self._directory = directory
        self._file_ext = file_ext
        self._checkpoint_ext = checkpoint_ext

    def create_file(self) -> JSONLWALWriter:
        os.makedirs(self._directory, exist_ok=True)
        # Timestamp prefix ensures deterministic oldest-first ordering
        # when sorted alphabetically.  UUID suffix avoids collisions
        # between files created in the same nanosecond.
        ts = f"{time.time_ns():020d}"
        filename = f"{ts}_{uuid.uuid4().hex}{self._file_ext}"
        path = os.path.join(self._directory, filename)
        return JSONLWALWriter(path)

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
        for p in (path, base + self._checkpoint_ext):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
