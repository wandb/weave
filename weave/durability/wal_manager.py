from __future__ import annotations

import atexit
import logging
import os
from collections.abc import Callable

from pydantic import BaseModel

from weave.durability.wal import WALRecord, WALRecordType, WALWriter
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_sender import BackgroundWALSender, create_sender
from weave.durability.wal_writer import JSONLWALWriter
from weave.trace_server_bindings.client_interface import TraceServerClientInterface

logger = logging.getLogger(__name__)


class WALManager:
    """Owns the lifecycle of a project-scoped Write-Ahead Log.

    Manages the writer (appends records to disk) and optionally a sender
    (background thread that drains records to the trace server).

    Use :meth:`with_sender` to create a manager that also starts a
    background sender thread for draining records to a server.

    Shutdown order (handled by :meth:`close`):
        1. Close the writer — flushes buffered writes, releases lock file.
        2. Stop the sender (if any) — performs a final drain, cleans up
           consumed files.
    """

    def __init__(self, entity: str, project: str) -> None:
        self.wal_dir = os.path.join(
            os.path.expanduser("~"),
            ".weave",
            "wal",
            entity,
            project,
        )
        dir_mgr = FileWALDirectoryManager(self.wal_dir)
        self._writer: WALWriter | None = JSONLWALWriter(dir_mgr)
        self._sender: BackgroundWALSender | None = None

    @classmethod
    def with_sender(
        cls,
        entity: str,
        project: str,
        server: TraceServerClientInterface,
        *,
        on_send: Callable[[str, WALRecord], None] | None = None,
    ) -> WALManager:
        """Create a WAL manager with a background sender thread.

        The sender drains WAL records to *server* on a polling interval.
        An atexit handler is registered to ensure clean shutdown.

        Args:
            on_send: Optional callback invoked after a record is successfully
                sent to the server.  Called with ``(record_type, record)``.
        """
        mgr = cls(entity, project)
        mgr._sender = create_sender(mgr.wal_dir, server, on_success=on_send)
        mgr._sender.start()
        atexit.register(mgr.close)
        return mgr

    def write(self, record_type: WALRecordType, req: BaseModel) -> None:
        """Write a request to the WAL.  Never raises."""
        if self._writer is None:
            return
        try:
            self._writer.write(
                {"type": record_type, "req": req.model_dump(mode="json")}
            )
            logger.debug("WAL write: %s -> %s", record_type, self.wal_dir)
        except Exception:
            logger.warning("Failed to write %s to WAL", record_type, exc_info=True)

    def flush(self) -> None:
        """Flush the WAL to disk."""
        if self._writer is not None:
            self._writer.flush()

    def close(self) -> None:
        """Close the writer then stop the sender.

        Safe to call multiple times.  Order matters: the writer must close
        first so its lock file is removed, allowing the sender's final drain
        to clean up the fully-consumed WAL file.
        """
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self._sender is not None:
            self._sender.stop()
            self._sender = None
