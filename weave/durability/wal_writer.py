from __future__ import annotations

import json
import os

from weave.durability.wal import WALRecord

# Number of writes between automatic os.fsync() calls.  Every write is pushed
# to the OS page cache (file.flush()), which survives process crashes.  The
# fsync — which survives power failures — is the expensive operation and is
# batched to amortize cost.  64 is a reasonable default for bursty workloads
# (training loops, evaluation logging).  Set to 1 for maximum durability.
DEFAULT_FSYNC_BATCH_SIZE = 64


class JSONLWALWriter:
    """Appends JSON line records to a WAL file with configurable fsync batching.

    Durability guarantees:
        - Every write() calls file.flush(), pushing data to the OS page
          cache.  This survives process crashes (SIGKILL, OOM, exceptions).
        - os.fsync() is called every fsync_batch_size writes, or explicitly
          via flush().  This makes file *contents* durable against power
          loss, but note: the directory entry is not fsynced, so after a
          power failure the file itself may not appear in the directory
          listing on some filesystems.  Full power-loss durability of the
          filename requires a directory fsync (not yet implemented).

    Args:
        path: Absolute path to the .jsonl file.
        fsync_batch_size: Number of writes between automatic os.fsync() calls.
            1 means every write is immediately fsynced (maximum durability,
            lowest throughput).  Higher values amortize fsync cost across
            multiple writes while still surviving process crashes on every
            write.
    """

    def __init__(
        self, path: str, fsync_batch_size: int = DEFAULT_FSYNC_BATCH_SIZE
    ) -> None:
        self._path = path
        self._file = open(path, "ab")
        self._fsync_batch_size = fsync_batch_size
        self._unsynced = 0

    def write(self, record: WALRecord) -> int:
        line = json.dumps(record, separators=(",", ":")) + "\n"
        self._file.write(line.encode("utf-8"))
        # Always push to OS page cache (survives process crash).
        # Only fsync to disk (survives power failure) every fsync_batch_size writes.
        self._file.flush()
        self._unsynced += 1
        if self._unsynced >= self._fsync_batch_size:
            self._fsync()
        return self._file.tell()

    def flush(self) -> None:
        if self._unsynced > 0:
            self._fsync()

    def close(self) -> None:
        self.flush()
        self._file.close()

    def __enter__(self) -> JSONLWALWriter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _fsync(self) -> None:
        os.fsync(self._file.fileno())
        self._unsynced = 0
