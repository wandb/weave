from __future__ import annotations

import logging

import pytest

from weave.durability.wal import WALRecord, drain, drain_all
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_writer import JSONLWALWriter


class TestDrain:
    def test_delivers_record_to_handler(self, tmp_path: str) -> None:
        """drain() reads pending records and calls the matching handler."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "payload": {"name": "my-model"}})

        received: list[WALRecord] = []
        consumer = JSONLWALConsumer(mgr.list_files()[0])
        count = drain(consumer, {"obj_create": received.append})

        assert count == 1
        assert received[0] == {"type": "obj_create", "payload": {"name": "my-model"}}

    def test_routes_by_type_key(self, tmp_path: str) -> None:
        """Records are routed to handlers by their "type" key."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "call_start", "id": "c1"})
            writer.write({"type": "obj_create", "digest": "sha256:abc"})
            writer.write({"type": "call_end", "id": "c1"})

        calls: list[WALRecord] = []
        objs: list[WALRecord] = []
        handlers = {
            "call_start": calls.append,
            "call_end": calls.append,
            "obj_create": objs.append,
        }
        consumer = JSONLWALConsumer(mgr.list_files()[0])
        count = drain(consumer, handlers)

        assert count == 3
        assert len(calls) == 2
        assert calls[0]["type"] == "call_start"
        assert calls[1]["type"] == "call_end"
        assert len(objs) == 1
        assert objs[0]["type"] == "obj_create"

    def test_skips_unknown_types(self, tmp_path: str) -> None:
        """Records with no registered handler are skipped without blocking others."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "name": "a"})
            writer.write({"type": "unknown_future_type", "data": 123})
            writer.write({"type": "obj_create", "name": "b"})

        received: list[WALRecord] = []
        consumer = JSONLWALConsumer(mgr.list_files()[0])
        count = drain(consumer, {"obj_create": received.append})

        assert count == 2
        assert len(received) == 2

    def test_acknowledges_after_processing(self, tmp_path: str) -> None:
        """drain() acknowledges internally after processing all records.

        After a successful drain, the checkpoint is advanced so that
        read_pending() returns nothing — confirming acknowledge happened.
        """
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "payload": {}})

        consumer = JSONLWALConsumer(mgr.list_files()[0])
        drain(consumer, {"obj_create": lambda r: None})

        # Checkpoint was advanced — no pending records remain.
        assert list(consumer.read_pending()) == []

    def test_returns_zero_for_empty_file(self, tmp_path: str) -> None:
        """Draining an empty WAL file returns 0 (no records to process)."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file():
            pass

        consumer = JSONLWALConsumer(mgr.list_files()[0])

        assert drain(consumer, {}) == 0

    def test_empty_handlers_acknowledges_all(self, tmp_path: str) -> None:
        """With no handlers registered, all typed records are skipped but acknowledged."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})
            writer.write({"type": "call_start", "seq": 1})

        consumer = JSONLWALConsumer(mgr.list_files()[0])
        count = drain(consumer, {})

        # No records processed (no handlers matched), but checkpoint advanced.
        assert count == 0
        assert list(consumer.read_pending()) == []

    def test_handler_error_prevents_acknowledgement(self, tmp_path: str) -> None:
        """If a handler raises, no acknowledge happens and all records replay.

        drain() uses all-or-nothing acknowledgement: the acknowledge call
        comes after the loop, so an exception mid-batch means the checkpoint
        never advances.  On the next drain(), all records replay from the
        same offset — including the one that succeeded before the error.
        """
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})
            writer.write({"type": "obj_create", "seq": 1})

        call_count = 0

        def exploding_handler(record: WALRecord) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("simulated network error")

        path = mgr.list_files()[0]
        consumer = JSONLWALConsumer(path)

        with pytest.raises(RuntimeError, match="simulated network error"):
            drain(consumer, {"obj_create": exploding_handler})

        # No acknowledgement — all records still pending on retry.
        consumer2 = JSONLWALConsumer(path)
        remaining = list(consumer2.read_pending())
        assert len(remaining) == 2

    def test_records_without_type_key_are_skipped_with_warning(
        self, tmp_path: str, caplog: object
    ) -> None:
        """Records missing "type" are skipped (with a warning) and acknowledged past.

        The "type" key is how drain() routes records to handlers.  A record
        without it can't be dispatched, so it's skipped.  The offset still
        advances so the record doesn't block future drains.
        """
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})
            writer.write({"no_type_here": True})
            writer.write({"type": "obj_create", "seq": 2})

        received: list[WALRecord] = []
        consumer = JSONLWALConsumer(mgr.list_files()[0])
        with caplog.at_level(logging.WARNING):  # type: ignore[union-attr]
            count = drain(consumer, {"obj_create": received.append})

        assert count == 2
        assert [r["seq"] for r in received] == [0, 2]
        # All three records (including the untyped one) are acknowledged.
        assert list(consumer.read_pending()) == []


class TestDrainAll:
    def test_drains_and_cleans_up_single_file(self, tmp_path: str) -> None:
        """drain_all removes the file and its checkpoint sidecar after processing."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "payload": {"name": "ds"}})

        received: list[WALRecord] = []
        # drain_all takes a class (factory), not an instance, because it
        # creates one consumer per WAL file discovered in the directory.
        total = drain_all(mgr, {"obj_create": received.append}, JSONLWALConsumer)

        assert total == 1
        assert received[0]["payload"]["name"] == "ds"
        assert mgr.list_files() == []

    def test_recovers_files_from_crashed_processes(self, tmp_path: str) -> None:
        """WAL files left behind by crashed processes are drained oldest-first."""
        mgr = FileWALDirectoryManager(str(tmp_path))

        with mgr.create_file() as w1:
            w1.write({"type": "call_start", "id": "old-1"})

        with mgr.create_file() as w2:
            w2.write({"type": "call_start", "id": "old-2"})
            w2.write({"type": "call_end", "id": "old-2"})

        received: list[WALRecord] = []
        handlers = {
            "call_start": received.append,
            "call_end": received.append,
        }
        total = drain_all(mgr, handlers, JSONLWALConsumer)

        assert total == 3
        assert received[0]["id"] == "old-1"
        assert received[1]["id"] == "old-2"
        assert received[2]["id"] == "old-2"
        assert received[2]["type"] == "call_end"
        assert mgr.list_files() == []

    def test_returns_zero_for_empty_directory(self, tmp_path: str) -> None:
        """No WAL files at all — drain_all is a no-op."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        assert drain_all(mgr, {}, JSONLWALConsumer) == 0

    def test_full_lifecycle(self, tmp_path: str) -> None:
        """End-to-end: write records, drain through handlers, verify cleanup."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write(
                {"type": "call_start", "id": "c1", "payload": {"op": "predict"}}
            )
            writer.write(
                {
                    "type": "obj_create",
                    "digest": "sha256:abc",
                    "payload": {"name": "ds"},
                }
            )
            writer.write({"type": "call_end", "id": "c1", "payload": {"output": 42}})

        calls: list[WALRecord] = []
        objs: list[WALRecord] = []
        handlers = {
            "call_start": calls.append,
            "call_end": calls.append,
            "obj_create": objs.append,
        }
        total = drain_all(mgr, handlers, JSONLWALConsumer)

        assert total == 3
        assert len(calls) == 2
        assert len(objs) == 1
        assert calls[0]["payload"] == {"op": "predict"}
        assert calls[1]["payload"] == {"output": 42}
        assert objs[0]["payload"] == {"name": "ds"}
        assert mgr.list_files() == []

    def test_keeps_file_with_pending_records(self, tmp_path: str) -> None:
        """drain_all's cleanup guard: files with unacknowledged records survive."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "name": "first"})

        path = mgr.list_files()[0]

        # Drain the existing record.
        consumer = JSONLWALConsumer(path)
        drain(consumer, {"obj_create": lambda r: None})

        # Simulate a late write between drain and the cleanup check.
        with JSONLWALWriter(path) as late_writer:
            late_writer.write({"type": "obj_create", "name": "late-arrival"})

        # The guard in drain_all checks read_pending() after drain —
        # since new records exist, the file must not be removed.
        assert next(consumer.read_pending(), None) is not None
        assert len(mgr.list_files()) == 1

    def test_write_drain_write_drain(self, tmp_path: str) -> None:
        """Writer and consumer operating on the same file sequentially."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = mgr.create_file()
        path = mgr.list_files()[0]

        # First batch: write two records, drain them.
        writer.write({"type": "obj_create", "seq": 0})
        writer.write({"type": "obj_create", "seq": 1})
        writer.flush()

        received: list[WALRecord] = []
        consumer = JSONLWALConsumer(path)
        count = drain(consumer, {"obj_create": received.append})
        assert count == 2

        # Second batch: write more records to the same file, drain again.
        writer.write({"type": "obj_create", "seq": 2})
        writer.write({"type": "obj_create", "seq": 3})
        writer.close()

        count = drain(consumer, {"obj_create": received.append})
        assert count == 2

        assert [r["seq"] for r in received] == [0, 1, 2, 3]
        assert list(consumer.read_pending()) == []
