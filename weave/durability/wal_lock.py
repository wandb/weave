"""PID-based lock files for cross-process WAL writer detection.

Each WAL file gets a ``.lock`` sidecar containing the PID of the process
that has the file open for writing.  The sender reads this sidecar to
decide whether a file is safe to delete:

- Lock file missing → writer closed cleanly (or never started) → safe.
- Lock file exists, PID alive → writer is active → skip deletion.
- Lock file exists, PID dead → writer crashed → stale lock → safe.

This mechanism is portable (works on Windows, macOS, Linux) and requires
no platform-specific APIs.  It complements the same-process
``active_paths`` check in the sender.
"""

from __future__ import annotations

import os

LOCK_EXT = ".lock"


def lock_path_for(wal_path: str, lock_ext: str = LOCK_EXT) -> str:
    """Return the lock sidecar path for a given WAL file path."""
    base, _ = os.path.splitext(wal_path)
    return base + lock_ext


def acquire_lock(wal_path: str, lock_ext: str = LOCK_EXT) -> str:
    """Create a PID lock sidecar for a WAL file.

    Writes the current process's PID to the lock file.

    Args:
        wal_path: Path to the WAL file being opened for writing.
        lock_ext: Extension for the lock sidecar file.

    Returns:
        The path to the lock file (for later release).
    """
    path = lock_path_for(wal_path, lock_ext)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return path


def release_lock(lock_path: str) -> None:
    """Remove a PID lock sidecar (idempotent)."""
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass


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
    try:
        with open(path, encoding="utf-8") as f:
            pid = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return False
    return _is_pid_alive(pid)


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it.
        return True
    return True
