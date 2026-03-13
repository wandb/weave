"""Write-Ahead Log (WAL) protocols for durable request persistence.

This module defines the core interfaces for a file-based WAL system that makes
API calls durable across process crashes and network failures.

The WAL sits between the caller and the transport layer.  Instead of holding
requests in an in-memory queue (which is lost on crash), requests are persisted
to disk before being considered "queued."  A background consumer reads from
disk and forwards requests to their destination.

Architecture overview:

    Caller
      │
      ▼
    WALWriter  ──►  ~/.weave/wal/{project_id}/{file}
      │
      │           WALDirectoryManager
      │             │ create_file() → WALWriter
      │             │ list_files()  → paths for WALConsumer
      ▼             ▼
    WALConsumer (reads + checkpoints) ──►  handler dispatch (drain)

Three protocols, fully orthogonal:

    WALWriter           — append records to a file with fsync durability
    WALConsumer         — read unprocessed records + track progress
    WALDirectoryManager — create, discover, and clean up per-process WAL files

The directory manager creates writers (create_file) and discovers file paths
(list_files) that the caller passes to consumers for draining.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Opaque dict — the WAL layer is format-agnostic.  Schema defined by callers.
WALRecord = dict

# Processes a single WAL record.  Must be idempotent — drain() replays the
# entire batch on failure (at-least-once delivery).
WALHandler = Callable[[WALRecord], None]
WALHandlers = dict[str, WALHandler]  # keyed by record "type"


@dataclass(frozen=True, slots=True)
class WALEntry:
    """A record read back from the WAL, paired with its position.

    Attributes:
        record: The deserialized WAL record.
        end_offset: Byte position immediately after this record in the file.
            Pass this to WALConsumer.acknowledge() after successful processing.
    """

    record: WALRecord
    end_offset: int


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class WALWriter(Protocol):
    """Appends records to a single WAL file on disk.

    This is the durability boundary.  Records are written to the OS page cache
    immediately (surviving process crashes) and fsynced to disk either
    automatically (every batch_size writes) or explicitly via flush().

    Composition:
        - Each process creates exactly one writer via WALDirectoryManager.
        - Each writer owns its own file — no cross-process locking needed.
        - The consumer reads the same file via WALConsumer, but only from
          already-written offsets, so there are no read/write conflicts.

    Implementation guidance:
        - Open the file in append mode.
        - Serialize each record as a single JSON line (no embedded newlines).
        - write() appends to the file and may fsync depending on batch_size.
        - flush() forces an fsync of all buffered writes.
        - close() calls flush() then closes the file handle.

    Not thread-safe.  If a background drain thread runs in the same
    process, callers must synchronize write() calls or use a dedicated
    writer per thread.
    """

    def write(self, record: WALRecord) -> int:
        """Append a record to the WAL file.

        The record is written to the OS page cache immediately (safe against
        process crashes).  It is fsynced to disk either when the internal
        batch fills up, or when flush()/close() is called.

        Args:
            record: An opaque dict to persist.  Must be JSON-serializable.

        Returns:
            Byte offset immediately after the written record.
        """
        ...

    def flush(self) -> None:
        """Force all buffered writes to disk (fsync).

        After flush() returns, all records written so far are durable against
        both process crashes and power failures.
        """
        ...

    def close(self) -> None:
        """Flush and close the underlying file.

        Calls flush() to ensure all records are durable, then closes the file
        handle.  After close(), no further writes are accepted.  The file
        remains on disk for the consumer to finish draining.
        """
        ...


@runtime_checkable
class WALConsumer(Protocol):
    """Reads unprocessed records from a WAL file and tracks progress.

    Combines reading and checkpointing into a single interface.  Internally
    manages a byte offset (persisted to a sidecar file) so that after a crash,
    read_pending() automatically resumes from where it left off.

    Composition:
        - The caller creates one consumer per WAL file path (from
          WALDirectoryManager.list_files()).
        - read_pending() returns all records not yet acknowledged.
        - After successfully sending a batch, the caller calls
          acknowledge(offset) with the end_offset of the last processed entry.
        - On the next call to read_pending() (or after a restart), only records
          after the acknowledged offset are returned.

    Implementation guidance:
        - On init, take a path to the WAL file.
        - Derive the checkpoint sidecar path (e.g., .checkpoint extension).
        - read_pending(): load checkpoint offset, seek to it, parse records,
          skip corrupt/truncated trailing entries, yield WALEntry values.
        - acknowledge(): atomically persist the offset (write temp + rename).
    """

    def read_pending(self) -> Iterator[WALEntry]:
        """Yield records not yet acknowledged, one at a time.

        Internally loads the checkpoint, reads from that offset forward, and
        yields results lazily.  Truncated trailing lines (from a crash
        mid-write) are silently skipped.

        Yields:
            Records with their end offsets, in file order.
        """
        ...

    def acknowledge(self, offset: int) -> None:
        """Mark all records up to the given offset as processed.

        The offset is persisted atomically so that a crash after acknowledge()
        but before the next read_pending() won't re-process those records.

        Args:
            offset: Byte offset from WALEntry.end_offset — the position
                immediately after the last successfully processed record.
        """
        ...


@runtime_checkable
class WALDirectoryManager(Protocol):
    """Manages the directory of per-process WAL files for a project.

    Each process writes to its own WAL file to avoid cross-process locking.
    On startup, the current process needs to discover and drain WAL files left
    behind by previous (possibly crashed) processes.  The directory manager
    handles file discovery, creation, and cleanup.

    Composition:
        - On init, the directory manager is created for the project.
        - create_file() returns a WALWriter for the current process.
        - list_files() returns paths to all WAL files so the caller can
          create a WALConsumer for each one.
        - After a WAL file is fully consumed, remove() cleans up the file
          and its checkpoint sidecar.

    Implementation guidance:
        - WAL directory path: ~/.weave/wal/{project_id}/
        - File naming: use unique names (e.g., timestamp + UUID) to avoid
          collisions across processes.
        - list_files() should return paths sorted oldest-first so the consumer
          drains old files before the current one.
        - remove() should delete both the WAL file and its checkpoint sidecar.
        - create_file() should create the directory if it doesn't exist.
    """

    def create_file(self) -> WALWriter:
        """Create a new WAL file for the current process.

        Returns:
            A writer bound to the new file.
        """
        ...

    def list_files(self) -> list[str]:
        """List all WAL files in the project directory.

        Returns:
            Absolute paths to WAL files, sorted oldest-first.
        """
        ...

    def remove(self, path: str) -> None:
        """Delete a fully-consumed WAL file and its checkpoint sidecar.

        Args:
            path: Absolute path to the WAL file to remove.
        """
        ...


# ---------------------------------------------------------------------------
# Composition functions
#
# These wire the protocols together.  They are the glue between the WAL
# primitives and the caller's dispatch logic.
# ---------------------------------------------------------------------------


def drain(consumer: WALConsumer, handlers: WALHandlers) -> int:
    """Process one batch of pending records from a single WAL file.

    Reads all unacknowledged records, dispatches each to the handler matching
    its "type" key, then acknowledges the batch.  Records with unknown types
    are skipped.

    Acknowledgement is all-or-nothing: if a handler raises, the exception
    propagates, acknowledge() is never called, and the entire batch replays
    on the next drain().  This provides at-least-once delivery — handlers
    must be idempotent.

    Args:
        consumer: A consumer bound to a specific WAL file.
        handlers: Maps record type strings to handler callables.

    Returns:
        The number of records successfully processed.
    """
    last_offset = 0
    processed = 0
    for entry in consumer.read_pending():
        record_type = entry.record.get("type")
        if record_type is None:
            logger.warning(
                "Skipping WAL record without 'type' key at offset %d",
                entry.end_offset,
            )
            last_offset = entry.end_offset
            continue
        handler = handlers.get(record_type)
        if handler is not None:
            handler(entry.record)
            processed += 1
        last_offset = entry.end_offset
    if last_offset:
        consumer.acknowledge(last_offset)
    return processed


def drain_all(
    directory_manager: WALDirectoryManager,
    handlers: WALHandlers,
    consumer_factory: Callable[[str], WALConsumer],
) -> int:
    """Drain every WAL file in the directory.  Remove fully-consumed files.

    Iterates all WAL files (oldest first), creates a consumer for each,
    drains it, and removes the file once fully consumed.  A file is only
    removed if read_pending() returns no more records after draining.

    IMPORTANT: Only call drain_all on files whose writers are closed.
    If a writer is still open on a file that drain_all removes, subsequent
    writes go to an unlinked inode and are silently lost.  In practice
    this means drain_all is for crash recovery (processing files left by
    *other* processes), not for draining the current process's active file.

    Note: there is a narrow race between drain() completing and the
    emptiness check — a concurrent writer could append records in that
    window.  In the current single-threaded design this is safe (Python's
    GIL serializes the operations).  If a background drain thread is
    added, the writer must be closed before a file becomes eligible
    for removal.

    Args:
        directory_manager: Manages the WAL directory for a project.
        handlers: Maps record type strings to handler callables.
        consumer_factory: Creates a WALConsumer for a given file path.
            Typically the JSONLWALConsumer class.

    Returns:
        Total number of records processed across all files.
    """
    total = 0
    for path in directory_manager.list_files():
        consumer = consumer_factory(path)
        total += drain(consumer, handlers)
        # Check if fully consumed — any remaining records means we shouldn't
        # delete yet (e.g., writer is still appending in the same process).
        if next(consumer.read_pending(), None) is None:
            directory_manager.remove(path)
    return total
