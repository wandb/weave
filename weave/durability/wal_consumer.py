from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterator

from weave.durability.wal import WALEntry

logger = logging.getLogger(__name__)


_active_consumers: set[str] = set()


class JSONLWALConsumer:
    """Reads unprocessed JSONL records and tracks progress via a checkpoint sidecar.

    One consumer per WAL file.  Multiple consumers on the same file will race
    on the checkpoint sidecar (each acknowledge() does an atomic rename, so
    the last writer wins and earlier checkpoints are lost).  In practice,
    drain() and drain_all() enforce this — they create exactly one consumer
    per file path.  A debug-mode assert catches violations during development.

    Not thread-safe.  If a background drain thread is added, callers must
    synchronize access or use separate consumer instances.
    """

    def __init__(
        self,
        path: str,
        checkpoint_ext: str = ".checkpoint",
        dead_letter_ext: str = ".deadletter",
    ) -> None:
        assert path not in _active_consumers, (
            f"A JSONLWALConsumer already exists for {path}. "
            "Only one consumer per WAL file is supported."
        )
        _active_consumers.add(path)
        self._path = path
        base, _ = os.path.splitext(path)
        self._checkpoint_path = base + checkpoint_ext
        self._dead_letter_path = base + dead_letter_ext

    def close(self) -> None:
        """Release this consumer's claim on its WAL file path."""
        _active_consumers.discard(self._path)

    @property
    def dead_letter_path(self) -> str:
        return self._dead_letter_path

    def read_pending(self) -> Iterator[WALEntry]:
        """Yield unacknowledged records from the WAL file.

        Loads the checkpoint offset, seeks to it, and yields each valid
        JSON line as a WALEntry.  Corrupt or truncated lines are skipped
        with a warning log.
        """
        offset = self._load_checkpoint()
        try:
            with open(self._path, "rb") as f:
                f.seek(offset)
                while True:
                    line = f.readline()
                    if not line:
                        break
                    offset += len(line)
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Skip corrupt/truncated lines instead of stopping.
                        # This recovers records after mid-file corruption.
                        # For trailing truncation (crash mid-write), the line
                        # won't end with \n so readline() returns it as the
                        # last line and we skip it here.
                        preview = line[:100].decode("utf-8", errors="replace").rstrip()
                        logger.warning(
                            "Skipping corrupt WAL line at offset %d in %s: %s",
                            offset,
                            self._path,
                            preview,
                        )
                        continue
                    yield WALEntry(record=record, end_offset=offset)
        except FileNotFoundError:
            return

    def acknowledge(self, offset: int) -> None:
        """Persist the checkpoint offset atomically (write temp, fsync, rename)."""
        # Atomically persist checkpoint: write temp → fsync → replace.
        # Note: the directory is not fsynced, so after power loss the
        # checkpoint rename may not be durable on all filesystems.
        # This is acceptable for process-crash durability.
        dir_name = os.path.dirname(self._checkpoint_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name)
        try:
            os.write(fd, str(offset).encode("utf-8"))
            os.fsync(fd)
        except BaseException:
            os.close(fd)
            os.unlink(tmp_path)
            raise
        os.close(fd)
        try:
            os.replace(tmp_path, self._checkpoint_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _load_checkpoint(self) -> int:
        try:
            with open(self._checkpoint_path, encoding="utf-8") as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0
