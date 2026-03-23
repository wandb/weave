from __future__ import annotations

import json
import os
import threading
import time

from weave.durability.wal import WALDirectoryManager, WALRecord
from weave.durability.wal_lock import acquire_lock, release_lock

# Default max file size before rotation.  64 MB keeps individual files
# manageable while avoiding excessive rotation churn.  Drained bytes at
# the front of a file are dead weight until the file is fully consumed
# and removed — rotation bounds that waste.
DEFAULT_MAX_FILE_SIZE = 64 * 1024 * 1024

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


class _JSONLWALFileWriter:
    """Single-file JSONL writer with fsync batching.  Private implementation detail.

    Use JSONLWALWriter (the rotating writer) as the public API.
    This class handles the low-level I/O for a single WAL file.
    """

    def __init__(
        self,
        path: str,
        fsync_batch_size: int = DEFAULT_FSYNC_BATCH_SIZE,
        fsync_timeout: float = DEFAULT_FSYNC_TIMEOUT,
    ) -> None:
        self.path = path
        # Lock MUST exist before the .jsonl file so the sender never sees
        # a discoverable WAL file without its liveness marker.
        self._lock_path = acquire_lock(path)
        try:
            self._file = open(path, "ab")
        except Exception:
            release_lock(self._lock_path)
            raise
        self._fsync_batch_size = fsync_batch_size
        self._fsync_timeout = fsync_timeout
        self._unsynced = 0
        self._last_fsync_time = time.monotonic()
        self._lock = threading.Lock()

    def write(self, record: WALRecord) -> int:
        # Serialize outside the lock — json.dumps is pure computation.
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self._lock:
            self._file.write(line.encode("utf-8"))
            # flush() pushes to OS page cache — survives process crashes.
            self._file.flush()
            self._unsynced += 1
            # fsync to disk if batch-count or timeout trigger fires.
            if self._should_fsync():
                self._fsync()
            # tell() returns the byte offset after this record — used by
            # WALEntry.end_offset for checkpoint-based progress tracking.
            return self._file.tell()

    def flush(self) -> None:
        with self._lock:
            self._flush_unlocked()

    def close(self) -> None:
        with self._lock:
            self._flush_unlocked()
            self._file.close()
            release_lock(self._lock_path)

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

    def __enter__(self) -> _JSONLWALFileWriter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _fsync(self) -> None:
        os.fsync(self._file.fileno())
        self._unsynced = 0
        self._last_fsync_time = time.monotonic()


class JSONLWALWriter:
    """Rotating JSONL WAL writer with configurable fsync batching.

    Delegates all I/O to a _JSONLWALFileWriter (single-file writer).  This
    class manages file rotation: when the current file exceeds
    ``max_file_size``, it closes the active _JSONLWALFileWriter and asks
    the WALDirectoryManager for a new one.  Old (rotated) files remain on
    disk for the consumer to drain; ``drain_all()`` picks them up
    oldest-first and deletes them after processing.

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

    Power-failure vulnerability window:
        Between a write() and the next fsync, records live only in the OS
        page cache.  A *process crash* in this window is safe (the page
        cache survives).  A *power failure* in this window loses unfsynced
        records.  The window is bounded by whichever trigger fires first:

        - At most ``fsync_batch_size`` writes (count trigger), or
        - At most ``fsync_timeout`` seconds (time trigger).

        With the defaults (batch_size=64, timeout=0.5s), the worst case is
        0.5 seconds of writes lost on power failure.  Set batch_size=1 for
        zero window (every write fsynced, ~2-5x slower on SSD).

        Note: the *directory entry* is not fsynced, so after a power failure
        the file itself may not appear in the directory listing on some
        filesystems (e.g., ext4 with default mount options).  The file
        contents are durable, but the filename is not.  Full power-loss
        durability of the filename requires a directory fsync (not yet
        implemented).

    Tuning guide::

        QPS   batch_size  timeout  fsyncs/sec  max unfsynced window
        ───   ──────────  ───────  ──────────  ────────────────────
          10       8       0.5s       ~2           0.5s (timeout)
         100      64       0.5s       ~2           0.5s (timeout)
        1000     256       0.5s       ~4           0.26s (batch)

        For maximum durability: fsync_batch_size=1 (every write fsynced).
        For maximum throughput: raise batch_size and timeout together.

    Args:
        directory_manager: Creates new WAL files on rotation.
        max_file_size: Rotate after the current file exceeds this many bytes.
            0 disables rotation (single file forever).
        fsync_batch_size: Number of writes between automatic os.fsync() calls.
        fsync_timeout: Maximum seconds between fsyncs.  0 disables the timeout.
    """

    def __init__(
        self,
        directory_manager: WALDirectoryManager,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
        fsync_batch_size: int = DEFAULT_FSYNC_BATCH_SIZE,
        fsync_timeout: float = DEFAULT_FSYNC_TIMEOUT,
    ) -> None:
        self._mgr = directory_manager
        self._max_file_size = max_file_size
        self._fsync_batch_size = fsync_batch_size
        self._fsync_timeout = fsync_timeout
        self._writer = self._new_file_writer()
        self._lock = threading.Lock()
        self._closed = False

    def write(self, record: WALRecord) -> int:
        # Delegates to _JSONLWALFileWriter.write(), then checks rotation.
        with self._lock:
            offset = self._writer.write(record)
            if self._max_file_size and offset >= self._max_file_size:
                self._writer.close()
                self._writer = self._new_file_writer()
            return offset

    def flush(self) -> None:
        # Delegates to _JSONLWALFileWriter.flush().
        with self._lock:
            self._writer.flush()

    @property
    def current_path(self) -> str:
        """Path of the currently active WAL file."""
        return self._writer.path

    def close(self) -> None:
        # Delegates to _JSONLWALFileWriter.close().
        with self._lock:
            self._writer.close()
            self._closed = True

    def __enter__(self) -> JSONLWALWriter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _new_file_writer(self) -> _JSONLWALFileWriter:
        writer = self._mgr.create_file()
        # Propagate fsync settings to the underlying file writer.
        assert isinstance(writer, _JSONLWALFileWriter)
        writer._fsync_batch_size = self._fsync_batch_size
        writer._fsync_timeout = self._fsync_timeout
        return writer
