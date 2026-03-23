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
   Files whose writer is still alive are drained but kept on disk;
   they will be removed on a subsequent cycle after the writer closes.

File safety:
    The writer creates a ``.lock`` sidecar containing its PID.  Before
    deleting any file, the sender calls ``is_file_active`` to check
    whether the writer process is still alive.  By default this uses
    :func:`~weave.durability.wal_lock.is_writer_alive` (PID lock check),
    but any ``Callable[[str], bool]`` can be substituted.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from weave.durability.wal import (
    WALConsumer,
    WALDirectoryManager,
    WALHandlers,
    WALRecord,
    drain,
)
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_lock import is_writer_alive
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
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

        self._consumers: dict[str, WALConsumer] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._drain_event = threading.Event()
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
        self._drain_event.clear()
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

        Raises:
            TimeoutError: If the thread is still alive after *timeout*
                seconds.  ``_thread`` is left intact so :meth:`start`
                correctly rejects a second launch.
        """
        thread = self._thread
        if thread is not None:
            self._stop_event.set()
            self._drain_event.set()  # unblock the sleep
            thread.join(timeout)

            if thread.is_alive():
                raise TimeoutError(
                    f"BackgroundWALSender did not stop within {timeout}s"
                )

            self._thread = None

        # Close any remaining cached consumers.  If a close() fails, the
        # consumer's file handle leaks but the dict is still cleared below,
        # so the sender's internal state is clean and start() can be called
        # again.  The leaked fd does NOT prevent file cleanup on Unix (unlink
        # works on open fds), but on Windows the file cannot be deleted until
        # the process exits and the handle is reclaimed.
        for path, consumer in self._consumers.items():
            try:
                consumer.close()
            except Exception:
                logger.exception("Failed to close consumer for %s", path)
        self._consumers.clear()

    def notify(self) -> None:
        """Signal that new records are available for draining.

        Wakes the background thread so it drains immediately instead of
        waiting for the next poll interval.  Safe to call from any thread.

        If a wake signal is lost (race with the thread's clear()),
        the next poll-interval drain picks up the records — the WAL
        guarantees durability, so a missed wake is a latency blip,
        not data loss.
        """
        self._drain_event.set()

    def drain_once(self) -> int:
        """Drain all WAL files once.  Thread-safe.

        Consumers are cached across calls so that repeated poll cycles
        avoid re-reading the checkpoint file and re-opening the WAL.
        A consumer is evicted (and its file removed) only when fully
        consumed and no longer active.

        Returns:
            Number of records successfully processed.
        """
        with self._lock:
            total = 0
            current_paths = self._mgr.list_files()
            current_set = set(current_paths)

            # Evict consumers for files that disappeared from disk.
            # Snapshot keys because the loop may pop() entries.
            for path in list(self._consumers):
                if path not in current_set:
                    try:
                        self._consumers.pop(path).close()
                    except Exception:
                        logger.exception(
                            "Failed to close evicted consumer for %s", path
                        )

            for path in current_paths:
                if path not in self._consumers:
                    try:
                        self._consumers[path] = self._consumer_factory(path)
                    except Exception:
                        logger.exception("Failed to create consumer for %s", path)
                        continue
                consumer = self._consumers[path]
                try:
                    total += drain(consumer, self._handlers)
                    if self._is_file_active(path):
                        continue
                    if next(consumer.read_pending(), None) is None:
                        self._consumers.pop(path).close()
                        self._mgr.remove(path)
                        logger.debug("WAL removed fully-consumed file: %s", path)
                except Exception:
                    logger.exception("Error draining or cleaning up WAL file %s", path)

            return total

    # -- Context manager ---------------------------------------------------

    def __enter__(self) -> BackgroundWALSender:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    # -- Internals ---------------------------------------------------------

    def _run(self) -> None:
        """Background loop: drain → sleep → repeat → final drain on exit.

        Sleeps on ``drain_event.wait(poll_interval)``.  Woken early by
        :meth:`notify` (new records available) or :meth:`stop` (shutdown).
        After waking, checks ``stop_event`` to decide whether to continue
        or exit.

        The ``drain_event.clear()`` after each wait creates a small race
        window where a concurrent ``notify()`` call could be lost.  This
        is acceptable: the WAL guarantees durability, so a missed wake
        just delays sending by at most one poll interval.
        """
        while not self._stop_event.is_set():
            try:
                self.drain_once()
            except Exception:
                logger.exception("Error in WAL sender drain cycle")
            self._drain_event.wait(self._poll_interval)
            self._drain_event.clear()

        # Final drain — writer process should have exited, so lock files
        # are either removed (clean close) or stale (crash).
        try:
            self.drain_once()
        except Exception:
            logger.exception("Error in WAL sender final drain")


# Static mapping from WAL record type to its request class.
# Prefer this over dynamic getattr — type checkers and humans can
# verify correctness at a glance.
_RECORD_TYPE_TO_REQ: dict[str, type[BaseModel]] = {
    "call_start": tsi.CallStartReq,
    "call_end": tsi.CallEndReq,
    "obj_create": tsi.ObjCreateReq,
    "table_create": tsi.TableCreateReq,
    "file_create": tsi.FileCreateReq,
}


class TraceServerHandlers:
    """Maps WAL record types to trace server method calls."""

    def __init__(
        self,
        server: TraceServerClientInterface,
        on_success: Callable[[str, WALRecord], None] | None = None,
    ) -> None:
        self._server = server
        self._handlers: WALHandlers = {}
        for record_type, req_cls in _RECORD_TYPE_TO_REQ.items():
            method = getattr(server, record_type)

            def _handler(
                record: WALRecord,
                _m: Callable = method,
                _rc: type[BaseModel] = req_cls,
                _rt: str = record_type,
            ) -> None:
                # model_validate_json (not model_validate) so that bytes
                # fields like FileCreateReq.content are base64-decoded
                # correctly during the WAL round-trip.
                _m(_rc.model_validate_json(json.dumps(record["req"])))
                if on_success is not None:
                    on_success(_rt, record)

            self._handlers[record_type] = _handler

    def as_dict(self) -> WALHandlers:
        """Return the handlers as a dict for BackgroundWALSender."""
        return dict(self._handlers)


def build_trace_server_handlers(
    server: TraceServerClientInterface,
    on_success: Callable[[str, WALRecord], None] | None = None,
) -> WALHandlers:
    """Build WAL handlers that replay records to a trace server.

    Convenience wrapper around :class:`TraceServerHandlers`.
    """
    return TraceServerHandlers(server, on_success=on_success).as_dict()


def create_sender(
    wal_dir: str,
    server: TraceServerClientInterface,
    *,
    poll_interval: float = 1.0,
    on_success: Callable[[str, WALRecord], None] | None = None,
) -> BackgroundWALSender:
    """Create a WAL sender that runs in-process as a background thread.

    This is the in-process alternative to ``main()`` (which runs as a
    standalone process).  Use as a context manager::

        sender = create_sender(wal_dir, server)
        sender.start()
        # ... do work ...
        sender.stop()

    Or::

        with create_sender(wal_dir, server) as sender:
            ...

    Args:
        wal_dir: Path to the WAL directory (e.g. ``~/.weave/wal/entity/project``).
        server: Trace server to replay records to.
        poll_interval: Seconds between drain cycles.
        on_success: Optional callback invoked after a record is successfully
            sent.  Called with ``(record_type, record)``.
    """
    dir_mgr = FileWALDirectoryManager(wal_dir)
    handlers = build_trace_server_handlers(server, on_success=on_success)
    return BackgroundWALSender(
        dir_mgr,
        handlers,
        JSONLWALConsumer,
        poll_interval=poll_interval,
    )


# -- CLI entrypoint -------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    r"""Run the WAL sender as a standalone process.

    For in-process usage, see :func:`create_sender` instead.

    Usage::

        python -m weave.durability.wal_sender \
            --entity my-entity --project my-project
    """
    parser = argparse.ArgumentParser(
        description="Drain WAL files and send records to the trace server."
    )
    parser.add_argument("--entity", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--wal-dir",
        help="Override WAL directory (default: ~/.weave/wal/<entity>/<project>)",
    )
    parser.add_argument(
        "--trace-server-url",
        default=os.environ.get("WF_TRACE_SERVER_URL", "https://trace.wandb.ai"),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("WANDB_API_KEY"),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds between drain cycles (default: 1.0)",
    )
    args = parser.parse_args(argv)

    if not args.api_key:
        print("Error: --api-key or WANDB_API_KEY required", file=sys.stderr)
        sys.exit(1)

    wal_dir = args.wal_dir or os.path.join(
        os.path.expanduser("~"), ".weave", "wal", args.entity, args.project
    )

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # RemoteHTTPTraceServer is missing a few abstract methods that the
    # WAL sender doesn't use.  Suppress via Any intermediate.
    remote_cls: Any = RemoteHTTPTraceServer
    server: TraceServerClientInterface = remote_cls(
        args.trace_server_url, auth=("api", args.api_key)
    )
    sender = create_sender(wal_dir, server, poll_interval=args.poll_interval)

    stop = threading.Event()

    def _on_signal(signum: int, frame: object) -> None:
        logger.debug("Received signal %s, stopping…", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    logger.debug(
        "WAL sender started for %s/%s (dir=%s, poll=%.1fs)",
        args.entity,
        args.project,
        wal_dir,
        args.poll_interval,
    )

    sender.start()
    stop.wait()
    sender.stop()

    logger.debug("WAL sender stopped.")


if __name__ == "__main__":
    main()
