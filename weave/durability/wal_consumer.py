from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterator

from weave.durability.wal import WALEntry

logger = logging.getLogger(__name__)


class JSONLWALConsumer:
    """Reads unprocessed JSONL records and tracks progress via a checkpoint sidecar.

    Not thread-safe.  If a background drain thread is added, callers must
    synchronize access or use separate consumer instances.
    """

    def __init__(self, path: str, checkpoint_ext: str = ".checkpoint") -> None:
        self._path = path
        base, _ = os.path.splitext(path)
        self._checkpoint_path = base + checkpoint_ext

    def read_pending(self) -> Iterator[WALEntry]:
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
                        logger.warning(
                            "Skipping corrupt WAL line at offset %d in %s",
                            offset,
                            self._path,
                        )
                        continue
                    yield WALEntry(record=record, end_offset=offset)
        except FileNotFoundError:
            return

    def acknowledge(self, offset: int) -> None:
        # Atomically persist checkpoint: write temp → fsync → replace.
        # Note: the directory is not fsynced, so after power loss the
        # checkpoint rename may not be durable on all filesystems.
        # This is acceptable for process-crash durability.
        dir_name = os.path.dirname(self._checkpoint_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name)
        try:
            os.write(fd, str(offset).encode("utf-8"))
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp_path, self._checkpoint_path)
        except (
            BaseException
        ):  # intentional: clean up temp file on KeyboardInterrupt too
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _load_checkpoint(self) -> int:
        try:
            with open(self._checkpoint_path, encoding="utf-8") as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0
