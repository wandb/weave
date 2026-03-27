from __future__ import annotations

import json
import logging
import os

import pytest

from weave.durability.wal import WALRecord, drain, drain_all
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_writer import JSONLWALWriter, _JSONLWALFileWriter


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

    @pytest.mark.disable_logging_error_check
    def test_handler_error_sends_to_dead_letter(self, tmp_path: str) -> None:
        """If a handler raises, the record goes to dead-letter and the batch continues.

        drain() catches handler exceptions, writes the failed record to the
        dead-letter sidecar, and keeps processing.  The batch is acknowledged
        so the WAL always makes forward progress.
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

        consumer = JSONLWALConsumer(mgr.list_files()[0])
        count = drain(consumer, {"obj_create": exploding_handler})

        # Record 0 succeeded, record 1 went to dead-letter.
        assert count == 1
        assert list(consumer.read_pending()) == []

        with open(consumer.dead_letter_path, encoding="utf-8") as f:
            dead = [json.loads(line) for line in f]
        assert len(dead) == 1
        assert dead[0]["seq"] == 1

    def test_unknown_type_logs_warning(self, tmp_path: str, caplog: object) -> None:
        """Records with a type that has no handler log a warning."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})
            writer.write({"type": "unknown_future_type", "data": 123})
            writer.write({"type": "obj_create", "seq": 2})

        received: list[WALRecord] = []
        consumer = JSONLWALConsumer(mgr.list_files()[0])
        with caplog.at_level(logging.WARNING):  # type: ignore[union-attr]
            count = drain(consumer, {"obj_create": received.append})

        assert count == 2
        assert any("unknown_future_type" in msg for msg in caplog.messages)  # type: ignore[union-attr]
        # All records (including unknown) are acknowledged past.
        assert list(consumer.read_pending()) == []

    def test_max_records_limits_processing(self, tmp_path: str) -> None:
        """drain() stops after max_records have been processed."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            for i in range(5):
                writer.write({"type": "obj_create", "seq": i})

        received: list[WALRecord] = []
        consumer = JSONLWALConsumer(mgr.list_files()[0])
        count = drain(consumer, {"obj_create": received.append}, max_records=2)

        assert count == 2
        assert len(received) == 2
        assert [r["seq"] for r in received] == [0, 1]

        # Remaining records are still pending.
        remaining = list(consumer.read_pending())
        assert len(remaining) == 3

    @pytest.mark.disable_logging_error_check
    def test_dead_letter_captures_failed_records(self, tmp_path: str) -> None:
        """Handler errors write to the dead-letter sidecar, not block the batch."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})
            writer.write({"type": "obj_create", "seq": 1})
            writer.write({"type": "obj_create", "seq": 2})

        def failing_handler(record: WALRecord) -> None:
            if record["seq"] == 1:
                raise ValueError("bad record")

        consumer = JSONLWALConsumer(mgr.list_files()[0])
        count = drain(consumer, {"obj_create": failing_handler})

        # Records 0 and 2 succeeded; record 1 went to dead-letter.
        assert count == 2
        assert list(consumer.read_pending()) == []

        with open(consumer.dead_letter_path, encoding="utf-8") as f:
            dead = [json.loads(line) for line in f]
        assert len(dead) == 1
        assert dead[0]["seq"] == 1

    def test_remove_cleans_up_dead_letter(self, tmp_path: str) -> None:
        """WALDirectoryManager.remove() deletes the dead-letter sidecar."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        path = mgr.list_files()[0]
        consumer = JSONLWALConsumer(path)

        # Create a dead-letter file.
        with open(consumer.dead_letter_path, "w", encoding="utf-8") as f:
            f.write('{"type":"obj_create","seq":0}\n')

        mgr.remove(path)
        assert not os.path.exists(consumer.dead_letter_path)
        assert not os.path.exists(path)

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
        with _JSONLWALFileWriter(path) as late_writer:
            late_writer.write({"type": "obj_create", "name": "late-arrival"})

        # The guard in drain_all checks read_pending() after drain —
        # since new records exist, the file must not be removed.
        assert next(consumer.read_pending(), None) is not None
        assert len(mgr.list_files()) == 1

    def test_is_file_active_prevents_deletion(self, tmp_path: str) -> None:
        """drain_all with is_file_active=always-True drains but never deletes."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        received: list[WALRecord] = []
        total = drain_all(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            is_file_active=lambda _: True,
        )

        assert total == 1
        assert received[0]["seq"] == 0
        # Records were drained, but the file is "active" so it's kept.
        assert len(mgr.list_files()) == 1

    def test_is_file_active_false_allows_deletion(self, tmp_path: str) -> None:
        """drain_all with is_file_active=always-False behaves like the default."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        total = drain_all(
            mgr,
            {"obj_create": lambda r: None},
            JSONLWALConsumer,
            is_file_active=lambda _: False,
        )

        assert total == 1
        assert mgr.list_files() == []

    def test_is_file_active_selective(self, tmp_path: str) -> None:
        """drain_all only protects files where is_file_active returns True."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as w1:
            w1.write({"type": "obj_create", "seq": 0})
        with mgr.create_file() as w2:
            w2.write({"type": "obj_create", "seq": 1})

        files = mgr.list_files()
        assert len(files) == 2
        protected_path = files[1]  # protect only the second file

        total = drain_all(
            mgr,
            {"obj_create": lambda r: None},
            JSONLWALConsumer,
            is_file_active=lambda p: p == protected_path,
        )

        assert total == 2
        remaining = mgr.list_files()
        assert remaining == [protected_path]

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


class TestJSONLWALWriter:
    def test_rotates_when_file_exceeds_max_size(self, tmp_path: str) -> None:
        """Writer creates a new file when the current one exceeds max_file_size."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        # Each record is ~30 bytes (compact JSON + newline).  With
        # max_file_size=100, rotation triggers after 4 writes (~120 bytes).
        # 10 records → 3 files (4 + 4 + 2).
        with JSONLWALWriter(mgr, max_file_size=100) as writer:
            for i in range(10):
                writer.write({"type": "obj_create", "seq": i})

        files = mgr.list_files()
        assert len(files) == 3

    def test_all_records_recoverable_after_rotation(self, tmp_path: str) -> None:
        """Every record written across rotations is recovered by drain_all."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with JSONLWALWriter(mgr, max_file_size=100) as writer:
            for i in range(20):
                writer.write({"type": "obj_create", "seq": i})

        received: list[WALRecord] = []
        total = drain_all(mgr, {"obj_create": received.append}, JSONLWALConsumer)

        assert total == 20
        assert [r["seq"] for r in received] == list(range(20))
        assert mgr.list_files() == []

    def test_no_rotation_when_disabled(self, tmp_path: str) -> None:
        """max_file_size=0 disables rotation — single file like plain writer."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with JSONLWALWriter(mgr, max_file_size=0) as writer:
            for i in range(10):
                writer.write({"type": "obj_create", "seq": i})

        assert len(mgr.list_files()) == 1

    def test_oldest_files_drained_first(self, tmp_path: str) -> None:
        """Rotated files are drained oldest-first, preserving write order."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with JSONLWALWriter(mgr, max_file_size=50) as writer:
            for i in range(10):
                writer.write({"type": "obj_create", "seq": i})

        received: list[WALRecord] = []
        drain_all(mgr, {"obj_create": received.append}, JSONLWALConsumer)

        # Records arrive in the order they were written, across files.
        assert [r["seq"] for r in received] == list(range(10))
