"""WAL sender — background thread that drains WAL records to handlers.

Complements the WAL writer: the writer persists requests to disk for
durability, and the sender (in a separate process) reads them back and
forwards them to their destination (typically a trace server).

Architecture::

    Process A (writer):
        WALWriter ──► disk (.jsonl + .lock files)

    Process B (sender):
        BackgroundWALSender ──► reads disk ──► handlers (server calls)
                                    │
                               background thread
                               polls on interval

The sender runs a background thread that periodically:

1. Discovers all WAL files via the directory manager.
2. Drains each file through the registered handlers via :func:`drain`.
3. Removes fully-consumed files whose writer is no longer alive.

File safety:
    The writer creates a ``.lock`` sidecar containing its PID.  Before
    deleting any file, the sender calls ``is_file_active`` to check
    whether the writer process is still alive.  By default this uses
    :func:`~weave.durability.wal_lock.is_writer_alive` (PID lock check),
    but any ``Callable[[str], bool]`` can be substituted.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from weave.durability.wal import (
    WALConsumer,
    WALDirectoryManager,
    WALHandlers,
    drain_all,
)
from weave.durability.wal_lock import is_writer_alive

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

        1. The file is fully consumed (no pending records remain), **and**
        2. ``is_file_active`` returns False for the path (i.e., the
           writer process is no longer alive).

        When the writer process closes the file, the ``.lock`` sidecar
        is removed and ``is_file_active`` returns False.  If the writer
        crashes, the ``.lock`` file contains a stale PID which
        ``is_file_active`` detects as dead.

    Usage::

        # Process A (writer)
        dir_mgr = FileWALDirectoryManager(wal_directory)
        writer = JSONLWALWriter(dir_mgr)
        writer.write({"type": "call_start", ...})
        writer.close()

        # Process B (sender)
        dir_mgr = FileWALDirectoryManager(wal_directory)
        sender = BackgroundWALSender(dir_mgr, handlers, JSONLWALConsumer)
        sender.start()
        # ... sender drains and cleans up files ...
        sender.stop()

    Args:
        directory_manager: Manages WAL file discovery and cleanup.
        handlers: Maps record ``"type"`` strings to handler callables.
        consumer_factory: Creates a :class:`WALConsumer` for a given
            file path.  Typically :class:`JSONLWALConsumer`.
        poll_interval: Seconds between drain cycles.
        is_file_active: Callable that takes a WAL file path and returns
            True if a writer still has it open.  Defaults to
            :func:`~weave.durability.wal_lock.is_writer_alive` which
            checks the PID lock sidecar.
    """

    def __init__(
        self,
        directory_manager: WALDirectoryManager,
        handlers: WALHandlers,
        consumer_factory: Callable[[str], WALConsumer],
        *,
        poll_interval: float = 1.0,
        is_file_active: Callable[[str], bool] = is_writer_alive,
    ) -> None:
        self._mgr = directory_manager
        self._handlers = handlers
        self._consumer_factory = consumer_factory
        self._poll_interval = poll_interval
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
        removed unless ``is_file_active`` returns True.

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

        # Final drain — writer process should have exited, so lock files
        # are either removed (clean close) or stale (crash).
        try:
            self.drain_once()
        except Exception:
            logger.exception("Error in WAL sender final drain")

    def _drain_unlocked(self) -> int:
        """Drain all WAL files.  Caller must hold ``self._lock``."""
        return drain_all(
            self._mgr,
            self._handlers,
            self._consumer_factory,
            is_file_active=self._is_file_active,
        )
