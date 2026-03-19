from __future__ import annotations

import json
import logging
import os
import shutil

import pytest

from weave.durability.wal_consumer import JSONLWALConsumer


def _checkpoint_path(wal_path: str) -> str:
    """Derive the expected checkpoint sidecar path from a WAL file path."""
    base, _ = os.path.splitext(wal_path)
    return base + ".checkpoint"


class TestJSONLWALConsumer:
    def test_read_pending_empty_file(self, tmp_path: str) -> None:
        """An empty WAL file yields no entries rather than erroring."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        open(path, "w", encoding="utf-8").close()

        consumer = JSONLWALConsumer(path)

        assert list(consumer.read_pending()) == []

    def test_read_pending_returns_all_records(self, tmp_path: str) -> None:
        """Without acknowledge(), read_pending() yields every record from offset 0."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for i in range(3):
                f.write(json.dumps({"seq": i}) + "\n")

        consumer = JSONLWALConsumer(path)
        entries = list(consumer.read_pending())

        assert len(entries) == 3
        for i, entry in enumerate(entries):
            assert entry.record == {"seq": i}

    def test_acknowledge_then_read_pending_skips_processed(self, tmp_path: str) -> None:
        """After acknowledge(offset), read_pending() only returns records past that offset."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"seq": 0}) + "\n")
            f.write(json.dumps({"seq": 1}) + "\n")
            f.write(json.dumps({"seq": 2}) + "\n")

        consumer = JSONLWALConsumer(path)
        entries = list(consumer.read_pending())

        # Acknowledge only the first record.
        consumer.acknowledge(entries[0].end_offset)

        remaining = list(consumer.read_pending())
        assert len(remaining) == 2
        assert remaining[0].record == {"seq": 1}
        assert remaining[1].record == {"seq": 2}

    def test_acknowledge_all_then_read_pending_is_empty(self, tmp_path: str) -> None:
        """After acknowledging the last record, read_pending() yields nothing."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"a": 1}) + "\n")

        consumer = JSONLWALConsumer(path)
        entries = list(consumer.read_pending())

        # The checkpoint is a single byte offset — acknowledging the last
        # entry's end_offset means "everything before this byte is done."
        consumer.acknowledge(entries[-1].end_offset)

        assert list(consumer.read_pending()) == []

    def test_checkpoint_survives_new_instance(self, tmp_path: str) -> None:
        """A new consumer instance resumes from the previously acknowledged offset.

        To simulate a real process restart (no shared in-process state), the
        WAL and checkpoint files are copied to new paths before creating the
        second consumer.  This catches bugs where recovery depends on cached
        global state (e.g., a module-level dict keyed by path).
        """
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"seq": 0}) + "\n")
            f.write(json.dumps({"seq": 1}) + "\n")

        # First consumer acknowledges the first record.
        consumer1 = JSONLWALConsumer(path)
        entries = list(consumer1.read_pending())
        consumer1.acknowledge(entries[0].end_offset)

        # Copy files to new paths to eliminate any in-process state leakage.
        path2 = os.path.join(str(tmp_path), "restart.jsonl")
        shutil.copy2(path, path2)
        shutil.copy2(_checkpoint_path(path), _checkpoint_path(path2))

        # Second consumer on the copied files — no shared state with consumer1.
        consumer2 = JSONLWALConsumer(path2)
        remaining = list(consumer2.read_pending())

        assert len(remaining) == 1
        assert remaining[0].record == {"seq": 1}

    @pytest.mark.parametrize(
        ("good_before", "good_after"),
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        ids=["only-corrupt", "trailing-corrupt", "mid-file-corrupt", "leading-corrupt"],
    )
    def test_corrupt_line_is_skipped(
        self,
        tmp_path: str,
        caplog: object,
        good_before: int,
        good_after: int,
    ) -> None:
        """Corrupt lines are skipped; valid records before and after are yielded."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "wb") as f:
            for i in range(good_before):
                f.write(json.dumps({"seq": i}).encode("utf-8") + b"\n")
            f.write(b"not valid json\n")
            for i in range(good_after):
                f.write(json.dumps({"seq": good_before + i}).encode("utf-8") + b"\n")

        consumer = JSONLWALConsumer(path)
        with caplog.at_level(logging.WARNING):  # type: ignore[union-attr]
            entries = list(consumer.read_pending())

        assert len(entries) == good_before + good_after
        for i, entry in enumerate(entries):
            assert entry.record == {"seq": i}
        assert "Skipping corrupt WAL line" in caplog.text  # type: ignore[union-attr]

    def test_end_offsets_are_correct(self, tmp_path: str) -> None:
        """end_offset equals the byte position immediately after each record's newline."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        # Use different-length records so offset arithmetic is non-trivial.
        line1 = json.dumps({"a": 1}) + "\n"
        line2 = json.dumps({"longer_key": "longer_value"}) + "\n"
        assert len(line1.encode("utf-8")) != len(line2.encode("utf-8"))
        with open(path, "wb") as f:
            f.write(line1.encode("utf-8"))
            f.write(line2.encode("utf-8"))

        consumer = JSONLWALConsumer(path)
        entries = list(consumer.read_pending())

        assert entries[0].end_offset == len(line1.encode("utf-8"))
        assert entries[1].end_offset == len(line1.encode("utf-8")) + len(
            line2.encode("utf-8")
        )

    def test_acknowledge_is_atomic(self, tmp_path: str) -> None:
        """acknowledge() uses write-to-temp + rename; no temp files left behind."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"a": 1}) + "\n")

        consumer = JSONLWALConsumer(path)
        entry = next(consumer.read_pending())
        consumer.acknowledge(entry.end_offset)

        # The checkpoint sidecar should exist and no temp files should remain.
        assert os.path.exists(_checkpoint_path(path))
        assert os.path.exists(path)
        temp_files = [f for f in os.listdir(str(tmp_path)) if f.startswith("tmp")]
        assert temp_files == []

    def test_read_pending_nested_and_unicode(self, tmp_path: str) -> None:
        """Nested structures and unicode survive the JSON roundtrip."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        record = {"nested": {"list": [1, 2]}, "emoji": "\U0001f600"}
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        consumer = JSONLWALConsumer(path)

        assert next(consumer.read_pending()).record == record

    def test_corrupt_checkpoint_resets_to_zero(self, tmp_path: str) -> None:
        """A corrupt checkpoint file is treated as offset 0 (replay all)."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"a": 1}) + "\n")
            f.write(json.dumps({"b": 2}) + "\n")

        # First, do a valid acknowledge so a real checkpoint exists.
        consumer = JSONLWALConsumer(path)
        entries = list(consumer.read_pending())
        consumer.acknowledge(entries[0].end_offset)
        assert len(list(consumer.read_pending())) == 1  # checkpoint works
        consumer.close()

        # Now corrupt the checkpoint sidecar.
        with open(_checkpoint_path(path), "w", encoding="utf-8") as f:
            f.write("not-a-number")

        consumer2 = JSONLWALConsumer(path)
        entries2 = list(consumer2.read_pending())

        # All records replayed from the start.
        assert len(entries2) == 2
        assert entries2[0].record == {"a": 1}

    def test_missing_wal_file_yields_nothing(self, tmp_path: str) -> None:
        """read_pending() on a non-existent file yields nothing instead of raising."""
        path = os.path.join(str(tmp_path), "gone.jsonl")

        consumer = JSONLWALConsumer(path)

        assert list(consumer.read_pending()) == []

    def test_checkpoint_past_eof_yields_nothing(self, tmp_path: str) -> None:
        """If the file is truncated after a checkpoint, read_pending() yields nothing."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"a": 1}) + "\n")

        # Acknowledge, then truncate the file (simulating filesystem recovery).
        consumer = JSONLWALConsumer(path)
        entries = list(consumer.read_pending())
        consumer.acknowledge(entries[0].end_offset)
        consumer.close()

        with open(path, "wb") as f:
            f.truncate(0)

        # Checkpoint points past EOF — readline returns empty, no records.
        consumer2 = JSONLWALConsumer(path)
        assert list(consumer2.read_pending()) == []
