from __future__ import annotations

import json
import os

import pytest

from weave.durability.wal_writer import JSONLWALWriter


class TestJSONLWALWriter:
    def test_write_single_record(self, tmp_path: str) -> None:
        """A single write produces exactly one valid JSON line on disk."""
        path = os.path.join(str(tmp_path), "test.jsonl")

        with JSONLWALWriter(path) as writer:
            writer.write({"type": "call_start", "id": "abc"})

        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 1
        assert json.loads(lines[0]) == {"type": "call_start", "id": "abc"}

    def test_write_multiple_records_preserves_order(self, tmp_path: str) -> None:
        """File order matches write order so the consumer replays correctly."""
        path = os.path.join(str(tmp_path), "test.jsonl")

        with JSONLWALWriter(path) as writer:
            for i in range(5):
                writer.write({"seq": i})

        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 5
        for i, line in enumerate(lines):
            assert json.loads(line) == {"seq": i}

    def test_write_returns_end_offset(self, tmp_path: str) -> None:
        """Returned offset is monotonically increasing and matches file size."""
        path = os.path.join(str(tmp_path), "test.jsonl")

        with JSONLWALWriter(path) as writer:
            offset1 = writer.write({"a": 1})
            offset2 = writer.write({"b": 2})

        assert offset1 > 0
        assert offset2 > offset1
        assert offset2 == os.path.getsize(path)

    def test_write_is_durable_on_disk(self, tmp_path: str) -> None:
        """Data is readable from disk before the writer is closed."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        writer = JSONLWALWriter(path)
        writer.write({"durable": True})

        # Read without closing the writer — file.flush() already pushed to page cache.
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.readline())

        assert data == {"durable": True}
        writer.close()

    def test_write_nested_content(self, tmp_path: str) -> None:
        """Arbitrarily nested payloads round-trip faithfully."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        record = {"nested": {"list": [1, 2, 3], "deep": {"key": "value"}}}

        with JSONLWALWriter(path) as writer:
            writer.write(record)

        with open(path, encoding="utf-8") as f:
            assert json.loads(f.readline()) == record

    def test_write_unicode_content(self, tmp_path: str) -> None:
        """Unicode in payloads survives without encoding corruption."""
        path = os.path.join(str(tmp_path), "test.jsonl")

        with JSONLWALWriter(path) as writer:
            writer.write({"emoji": "\U0001f600", "cjk": "\u4e16\u754c"})

        with open(path, encoding="utf-8") as f:
            data = json.loads(f.readline())

        assert data["emoji"] == "\U0001f600"
        assert data["cjk"] == "\u4e16\u754c"

    def test_flush_forces_fsync(self, tmp_path: str) -> None:
        """flush() forces os.fsync() even with a large batch size."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        writer = JSONLWALWriter(path, fsync_batch_size=100)
        writer.write({"buffered": True})
        writer.flush()

        with open(path, encoding="utf-8") as f:
            assert json.loads(f.readline()) == {"buffered": True}
        writer.close()

    def test_fsync_batch_size_controls_frequency(self, tmp_path: str) -> None:
        """With fsync_batch_size=3, os.fsync() triggers every 3rd write."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        writer = JSONLWALWriter(path, fsync_batch_size=3)

        # Write 5 records: fsync fires after write 3, not after 4 or 5.
        for i in range(5):
            writer.write({"seq": i})

        # All 5 are readable (file.flush() happens every write).
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 5

        # Internal counter: 2 unsynced (writes 4 and 5 since last fsync at 3).
        assert writer._unsynced == 2

        writer.close()

    def test_close_flushes_partial_batch(self, tmp_path: str) -> None:
        """close() flushes remaining records even if the batch hasn't filled."""
        path = os.path.join(str(tmp_path), "test.jsonl")

        with JSONLWALWriter(path, fsync_batch_size=100) as writer:
            writer.write({"partial": 1})
            writer.write({"partial": 2})

        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 2

    def test_embedded_newlines_in_values(self, tmp_path: str) -> None:
        """Newlines inside string values are escaped and don't split the JSONL line."""
        path = os.path.join(str(tmp_path), "test.jsonl")
        record = {"text": "line1\nline2\nline3"}

        with JSONLWALWriter(path) as writer:
            writer.write(record)

        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        # Still one JSONL line despite embedded newlines in the value.
        assert len(lines) == 1
        assert json.loads(lines[0]) == record

    def test_context_manager_closes_on_exit(self, tmp_path: str) -> None:
        """Writer used as context manager flushes, closes, and rejects further writes."""
        path = os.path.join(str(tmp_path), "test.jsonl")

        with JSONLWALWriter(path) as writer:
            writer.write({"ctx": True})

        # Data is flushed and readable after exiting the with block.
        with open(path, encoding="utf-8") as f:
            assert json.loads(f.readline()) == {"ctx": True}

        # Further writes raise because the file is closed.
        with pytest.raises(ValueError):
            writer.write({"after": True})
