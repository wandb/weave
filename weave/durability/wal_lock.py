"""PID-based lock files for cross-process WAL writer detection.

Each WAL file gets a ``.lock`` sidecar containing the PID of the process
that has the file open for writing.  The sender reads this sidecar to
decide whether a file is safe to delete:

- Lock file missing → writer closed cleanly (or never started) → safe.
- Lock file exists, PID alive → writer is active → skip deletion.
- Lock file exists, PID dead → writer crashed → stale lock → safe.

This mechanism is portable (works on Windows, macOS, Linux) and requires
no platform-specific APIs.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys

logger = logging.getLogger(__name__)

LOCK_EXT = ".lock"


def lock_path_for(wal_path: str, lock_ext: str = LOCK_EXT) -> str:
    """Return the lock sidecar path for a given WAL file path."""
    base, _ = os.path.splitext(wal_path)
    return base + lock_ext


def acquire_lock(wal_path: str, lock_ext: str = LOCK_EXT) -> str:
    """Create a PID lock sidecar for a WAL file.

    Uses ``O_CREAT | O_EXCL`` for atomic creation — if the lock file
    already exists, we check the PID inside:

    - **PID alive** → another writer genuinely holds the file → raise.
    - **PID dead** → stale lock from a crashed writer → warn and overwrite.

    Args:
        wal_path: Path to the WAL file being opened for writing.
        lock_ext: Extension for the lock sidecar file.

    Returns:
        The path to the lock file (for later release).

    Raises:
        FileExistsError: If the lock is held by a living process.
    """
    path = lock_path_for(wal_path, lock_ext)
    try:
        # Atomic exclusive create — fails if the file already exists.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
    except FileExistsError as exc:
        # Lock file exists — check if the holder is still alive.
        existing_pid = _read_lock_pid(path)
        if existing_pid is not None and _is_pid_alive(existing_pid):
            raise FileExistsError(
                f"Lock file {path} is held by living process {existing_pid}"
            ) from exc
        # Stale lock from a crashed writer — safe to overwrite.
        logger.warning(
            "Lock file %s contains stale PID %s — overwriting.",
            path,
            existing_pid,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    return path


def _read_lock_pid(path: str) -> int | None:
    """Read the PID from a lock file.  Returns None if unreadable.

    ValueError occurs when the file exists but doesn't contain a valid
    integer — most commonly because the writer crashed between creating
    the lock file (os.open with O_CREAT|O_EXCL) and writing its PID
    (os.write), leaving an empty file.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return None
    except ValueError:
        logger.warning(
            "Lock file %s exists but contains no valid PID — likely a "
            "crash during lock acquisition. Treating as stale.",
            path,
        )
        return None


def release_lock(lock_path: str) -> None:
    """Remove a PID lock sidecar (idempotent)."""
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        logger.warning(
            "Lock file %s was already missing on release. This may indicate "
            "external tampering or a logic error.",
            lock_path,
        )
    except PermissionError:
        # On Windows, the sender thread may have the lock file open for
        # reading (in _read_lock_pid / is_writer_alive) at the moment we
        # try to unlink.  Windows forbids deleting files with open handles.
        # The sender's next drain cycle will see the stale PID and treat
        # the file as safe to clean up, so this is not a data-loss risk.
        logger.debug(
            "Cannot remove lock file %s (still open by another thread/process), "
            "will be cleaned up by the sender.",
            lock_path,
        )


def is_writer_alive(wal_path: str, lock_ext: str = LOCK_EXT) -> bool:
    """Check if a WAL file has an active writer (cross-process safe).

    Reads the PID from the lock sidecar file and checks whether that
    process is still running.  Returns False if:

    - The lock file doesn't exist (writer closed cleanly or never started).
    - The lock file contains a PID for a dead process (writer crashed).

    This is the default ``is_file_active`` implementation for
    :class:`~weave.durability.wal_sender.BackgroundWALSender`.
    """
    path = lock_path_for(wal_path, lock_ext)
    pid = _read_lock_pid(path)
    if pid is None:
        return False
    return _is_pid_alive(pid)


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running.

    On Unix, sends signal 0 (no-op) to probe the process.
    On Windows, os.kill(pid, 0) is unreliable (raises OSError with
    varying error codes across Python versions), so we use the
    Win32 OpenProcess API directly.
    """
    if sys.platform == "win32":
        return _is_pid_alive_win32(pid)
    try:
        # Signal 0 doesn't deliver a signal — it just checks whether the
        # process exists and we have permission to signal it.
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it.
        return True
    return True


def _is_pid_alive_win32(pid: int) -> bool:
    """Windows-specific PID liveness check using OpenProcess."""
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(
        0x1000, False, pid
    )  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle == 0:
        # Process doesn't exist or access denied with no handle.
        return False
    kernel32.CloseHandle(handle)
    return True
