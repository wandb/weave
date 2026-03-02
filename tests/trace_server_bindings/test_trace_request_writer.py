from __future__ import annotations

import json
import threading
from typing import Any

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.trace_request_writer import (
    JsonlRequestWriter,
    TraceRequestWriter,
)


def _read_records(log_file: str) -> list[dict]:
    with open(log_file, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


class TestJsonlRequestWriterSerialization:
    def test_pydantic_request_serialized(self, tmp_path):
        log_file = str(tmp_path / "trace.jsonl")
        writer = JsonlRequestWriter(log_file)

        req = tsi.ObjReadReq(
            project_id="entity/project", object_id="obj1", digest="abc123"
        )
        writer.write_request("obj_read", (req,), {})

        records = _read_records(log_file)
        assert len(records) == 1
        assert records[0]["method"] == "obj_read"
        assert "timestamp" in records[0]
        assert records[0]["args"][0]["project_id"] == "entity/project"
        assert records[0]["args"][0]["object_id"] == "obj1"

    def test_plain_string_args(self, tmp_path):
        log_file = str(tmp_path / "trace.jsonl")
        writer = JsonlRequestWriter(log_file)

        writer.write_request("ensure_project_exists", ("my_entity", "my_project"), {})

        records = _read_records(log_file)
        assert records[0]["args"] == ["my_entity", "my_project"]

    def test_no_args_omits_keys(self, tmp_path):
        log_file = str(tmp_path / "trace.jsonl")
        writer = JsonlRequestWriter(log_file)

        writer.write_request("server_info", (), {})

        records = _read_records(log_file)
        assert records[0]["method"] == "server_info"
        assert "args" not in records[0]
        assert "kwargs" not in records[0]

    def test_multiple_writes_append(self, tmp_path):
        log_file = str(tmp_path / "trace.jsonl")
        writer = JsonlRequestWriter(log_file)

        req1 = tsi.ObjReadReq(project_id="e/p", object_id="obj1", digest="d1")
        req2 = tsi.ObjReadReq(project_id="e/p", object_id="obj2", digest="d2")
        writer.write_request("obj_read", (req1,), {})
        writer.write_request("obj_read", (req2,), {})

        records = _read_records(log_file)
        assert len(records) == 2
        assert records[0]["args"][0]["object_id"] == "obj1"
        assert records[1]["args"][0]["object_id"] == "obj2"


class TestJsonlRequestWriterThreadSafety:
    def test_concurrent_writes_produce_valid_jsonl(self, tmp_path):
        log_file = str(tmp_path / "trace.jsonl")
        writer = JsonlRequestWriter(log_file)
        num_threads = 50

        def write(i: int) -> None:
            req = tsi.ObjReadReq(
                project_id="e/p", object_id=f"obj{i}", digest="abc"
            )
            writer.write_request("obj_read", (req,), {})

        threads = [
            threading.Thread(target=write, args=(i,))
            for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        records = _read_records(log_file)
        assert len(records) == num_threads
        for record in records:
            assert record["method"] == "obj_read"
            assert "timestamp" in record


class TestJsonlRequestWriterErrorResilience:
    @pytest.mark.disable_logging_error_check
    def test_unwritable_path_does_not_raise(self):
        writer = JsonlRequestWriter("/nonexistent/dir/trace.jsonl")
        # Should not raise
        writer.write_request("obj_read", (), {})


class TestTraceRequestWriterProtocol:
    def test_jsonl_writer_satisfies_protocol(self, tmp_path):
        log_file = str(tmp_path / "trace.jsonl")
        writer: TraceRequestWriter = JsonlRequestWriter(log_file)
        writer.write_request("test", (), {})

    def test_custom_writer_satisfies_protocol(self):
        """A minimal custom writer should satisfy the protocol."""
        calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        class InMemoryWriter:
            def write_request(
                self,
                method: str,
                args: tuple[Any, ...],
                kwargs: dict[str, Any],
            ) -> None:
                calls.append((method, args, kwargs))

        writer: TraceRequestWriter = InMemoryWriter()
        writer.write_request("test_method", ("arg1",), {"key": "val"})
        assert len(calls) == 1
        assert calls[0] == ("test_method", ("arg1",), {"key": "val"})
