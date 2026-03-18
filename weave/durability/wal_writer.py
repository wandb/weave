from __future__ import annotations

import json
import os
import threading
import time

from weave.durability.wal import WALRecord

# Number of writes between automatic os.fsync() calls.  Every write is pushed
# to the OS page cache (file.flush()), which survives process crashes.  The
# fsync — which survives power failures — is the expensive operation and is
# batched to amortize cost.  64 is a reasonable default for bursty workloads
# (training loops, evaluation logging).  Set to 1 for maximum durability.
DEFAULT_FSYNC_BATCH_SIZE = 64

# Maximum seconds between fsyncs.  If the batch hasn't filled up within this
# window, the next write() triggers an fsync anyway.  This bounds the
# power-failure vulnerability window for low-QPS workloads where records
# trickle in slowly.  0 disables the timeout (batch-count only).
DEFAULT_FSYNC_TIMEOUT = 0.5


class JSONLWALWriter:
    """Appends JSON line records to a WAL file with configurable fsync batching.

    Durability model:
        Every write() is immediately flushed to the OS page cache, which
        survives process crashes (SIGKILL, OOM, uncaught exceptions).
        Power-failure durability (os.fsync) is triggered by *either*:

        - **Batch count**: after ``fsync_batch_size`` writes, or
        - **Timeout**: if ``fsync_timeout`` seconds have elapsed since the
          last fsync (checked on each write).

        Whichever fires first wins.  This means records are always durable
        against process crashes on every write, and durable against power
        failures within at most ``fsync_timeout`` seconds or
        ``fsync_batch_size`` writes.

        Note: the directory entry is not fsynced, so after a power failure
        the file itself may not appear in the directory listing on some
        filesystems.  Full power-loss durability of the filename requires
        a directory fsync (not yet implemented).

    Tuning guide::

        QPS   batch_size  timeout  fsyncs/sec  max unfsynced window
        ───   ──────────  ───────  ──────────  ────────────────────
          10       8       0.5s       ~2           0.5s (timeout)
         100      64       0.5s       ~2           0.5s (timeout)
        1000     256       0.5s       ~4           0.26s (batch)

        For maximum durability: fsync_batch_size=1 (every write fsynced).
        For maximum throughput: raise batch_size and timeout together.

    Args:
        path: Absolute path to the .jsonl file.
        fsync_batch_size: Number of writes between automatic os.fsync() calls.
            1 means every write is immediately fsynced (maximum durability,
            lowest throughput).  Higher values amortize fsync cost across
            multiple writes while still surviving process crashes on every
            write.
        fsync_timeout: Maximum seconds between fsyncs.  On each write, if
            this many seconds have passed since the last fsync, an fsync is
            triggered regardless of batch count.  0 disables the timeout.
    """

    def __init__(
        self,
        path: str,
        fsync_batch_size: int = DEFAULT_FSYNC_BATCH_SIZE,
        fsync_timeout: float = DEFAULT_FSYNC_TIMEOUT,
    ) -> None:
        self._path = path
        self._file = open(path, "ab")
        self._fsync_batch_size = fsync_batch_size
        self._fsync_timeout = fsync_timeout
        self._unsynced = 0
        self._last_fsync_time = time.monotonic()
        self._lock = threading.Lock()

    def write(self, record: WALRecord) -> int:
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self._lock:
            self._file.write(line.encode("utf-8"))
            self._file.flush()
            self._unsynced += 1
            if self._should_fsync():
                self._fsync()
            return self._file.tell()

    def flush(self) -> None:
        with self._lock:
            self._flush_unlocked()

    def close(self) -> None:
        with self._lock:
            self._flush_unlocked()
            self._file.close()

    def _should_fsync(self) -> bool:
        # Batch-count trigger: enough writes have accumulated.
        if self._unsynced >= self._fsync_batch_size:
            return True
        # Timeout trigger: too long since last fsync (bounds the
        # power-failure window for low-QPS workloads).
        if (
            self._fsync_timeout > 0
            and self._unsynced > 0
            and (time.monotonic() - self._last_fsync_time) >= self._fsync_timeout
        ):
            return True
        return False

    def _flush_unlocked(self) -> None:
        if self._unsynced > 0:
            self._fsync()

    def __enter__(self) -> JSONLWALWriter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _fsync(self) -> None:
        os.fsync(self._file.fileno())
        self._unsynced = 0
        self._last_fsync_time = time.monotonic()
