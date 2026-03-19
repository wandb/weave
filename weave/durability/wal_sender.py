"""WAL sender — background thread that drains WAL records to handlers.

Complements the WAL writer: the writer persists requests to disk for
durability, and the sender reads them back and forwards them to their
destination (typically a trace server).

Architecture::

    WALWriter ──► disk ──► BackgroundWALSender ──► handlers (server calls)
                              │
                         background thread
                         polls on interval

The sender runs a background thread that periodically:

1. Discovers all WAL files via the directory manager.
2. Drains each file through the registered handlers via :func:`drain`.
3. Removes fully-consumed files that have no active writer.

File safety — two pluggable layers of protection:
    1. **Same-process** (``active_paths``): A callable returning paths
       the local writer owns.  Fast, no I/O.
    2. **Cross-process** (``is_file_active``): A callable that checks
       whether another process has a file open (e.g., PID lock check).
       The default implementation is :func:`is_writer_alive` from
       ``wal_writer``, but any ``Callable[[str], bool]`` works.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from weave.durability.wal import (
    WALConsumer,
    WALDirectoryManager,
    WALHandlers,
    drain,
)

logger = logging.getLogger(__name__)


class BackgroundWALSender:
    """Thread-based :class:`WALSender` that polls on an interval.

    Satisfies the :class:`~weave.durability.wal.WALSender` protocol.

    Thread safety:
        All drain operations are serialized via an internal lock.  The
        background thread and explicit :meth:`flush`/:meth:`drain_once`
        calls are safe to use concurrently.

    File cleanup:
        After draining a file, the sender removes it only if:

        1. The file is fully consumed (no pending records remain),
        2. The file's path is not in the ``active_paths`` set
           (same-process protection), **and**
        3. ``is_file_active`` returns False for the path
           (cross-process protection).

        When the caller closes the writer before calling :meth:`stop`,
        the writer's path leaves the active set *and* the lock file is
        removed, so the final drain cleans it up automatically.

    Usage::

        from weave.durability.wal_lock import is_writer_alive
        from weave.durability.wal_writer import JSONLWALWriter

        dir_mgr = FileWALDirectoryManager(wal_directory)
        writer = JSONLWALWriter(dir_mgr)

        handlers = {
            "call_start": lambda r: server.call_start(make_req(r)),
            "call_end": lambda r: server.call_end(make_req(r)),
        }
        sender = BackgroundWALSender(
            dir_mgr, handlers, JSONLWALConsumer,
            active_paths=lambda: {writer.active_path},
            is_file_active=is_writer_alive,
        )
        sender.start()

        # ... write records via writer ...

        writer.close()         # active_path is now None → active set empty
        sender.stop()          # final drain removes all consumed files

    Args:
        directory_manager: Manages WAL file discovery and cleanup.
        handlers: Maps record ``"type"`` strings to handler callables.
        consumer_factory: Creates a :class:`WALConsumer` for a given
            file path.  Typically :class:`JSONLWALConsumer`.
        poll_interval: Seconds between drain cycles.
        active_paths: Callable returning the set of file paths that
            must not be deleted (because a writer still has them open).
            The callable is invoked on every drain cycle so it always
            reflects current state.  ``None`` values in the returned
            set are ignored (convenient when ``writer.active_path``
            returns ``None`` after close).
        is_file_active: Callable that takes a WAL file path and returns
            True if a writer (possibly in another process) still has it
            open.  Checked before deleting any file.  Pass
            :func:`~weave.durability.wal_lock.is_writer_alive` for
            PID-lock-based cross-process detection, or any custom check.
    """

    def __init__(
        self,
        directory_manager: WALDirectoryManager,
        handlers: WALHandlers,
        consumer_factory: Callable[[str], WALConsumer],
        *,
        poll_interval: float = 1.0,
        active_paths: Callable[[], set[str | None]] | None = None,
        is_file_active: Callable[[str], bool] | None = None,
    ) -> None:
        self._mgr = directory_manager
        self._handlers = handlers
        self._consumer_factory = consumer_factory
        self._poll_interval = poll_interval
        self._active_paths_fn = active_paths
        self._is_file_active = is_file_active

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None

    # -- Public API --------------------------------------------------------

    def start(self) -> None:
        """Start the background drain thread.

        Raises:
            RuntimeError: If the sender is already running.
        """
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("BackgroundWALSender is already running")
        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="wal-sender",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the background thread and perform a final drain.

        The caller must close the writer before calling :meth:`stop`
        so that the writer's path leaves the active set and the final
        drain can clean it up.

        Args:
            timeout: Maximum seconds to wait for the thread to finish.
        """
        self._stop_event.set()
        self._wake_event.set()  # unblock the sleep
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def drain_once(self) -> int:
        """Drain all WAL files once.  Thread-safe.

        Each file is read from its checkpoint forward.  Records are
        dispatched to the matching handler.  Fully-consumed files are
        removed unless protected by ``active_paths`` or ``is_file_active``.

        Returns:
            Number of records successfully processed.
        """
        with self._lock:
            return self._drain_unlocked()

    def flush(self) -> int:
        """Drain all pending records synchronously.  Thread-safe.

        Safe to call while the background thread is running — the lock
        serializes access.

        Returns:
            Number of records processed.
        """
        return self.drain_once()

    # -- Context manager ---------------------------------------------------

    def __enter__(self) -> BackgroundWALSender:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    # -- Internals ---------------------------------------------------------

    def _run(self) -> None:
        """Background loop: drain → sleep → repeat → final drain on exit."""
        while not self._stop_event.is_set():
            try:
                self.drain_once()
            except Exception:
                logger.exception("Error in WAL sender drain cycle")
            self._wake_event.wait(self._poll_interval)
            self._wake_event.clear()

        # Final drain — writer should be closed, so its path is no longer
        # in the active set and fully-consumed files get cleaned up.
        try:
            self.drain_once()
        except Exception:
            logger.exception("Error in WAL sender final drain")

    def _get_active_paths(self) -> set[str]:
        """Return the current set of active file paths (None values filtered)."""
        if self._active_paths_fn is None:
            return set()
        raw = self._active_paths_fn()
        return {p for p in raw if p is not None}

    def _drain_unlocked(self) -> int:
        """Drain all WAL files.  Caller must hold ``self._lock``."""
        total = 0
        active = self._get_active_paths()

        for path in self._mgr.list_files():
            try:
                consumer = self._consumer_factory(path)
            except Exception:
                logger.exception("Failed to create consumer for %s", path)
                continue
            try:
                total += drain(consumer, self._handlers)
                # Never remove a file that a writer still has open —
                # writes to an unlinked inode are silently lost.
                # Layer 1: same-process check via active_paths callable.
                if path in active:
                    continue
                # Layer 2: cross-process check via pluggable callable.
                if self._is_file_active is not None and self._is_file_active(
                    path
                ):
                    continue
                # Remove the file only if fully consumed.
                if next(consumer.read_pending(), None) is None:
                    self._mgr.remove(path)
            except Exception:
                logger.exception("Error draining WAL file %s", path)
            finally:
                consumer.close()

        return total
