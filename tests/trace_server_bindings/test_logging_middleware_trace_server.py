from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.logging_middleware_trace_server import (
    LoggingMiddlewareTraceServer,
)


@pytest.fixture
def mock_server():
    return MagicMock()


@pytest.fixture
def log_file(tmp_path):
    return str(tmp_path / "trace.jsonl")


@pytest.fixture
def middleware(mock_server, log_file):
    return LoggingMiddlewareTraceServer(mock_server, log_file)


def _read_records(log_file: str) -> list[dict]:
    with open(log_file, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


class TestLoggingMiddlewarePydanticRequest:
    def test_logs_method_name_and_args(self, middleware, mock_server, log_file):
        req = tsi.ObjReadReq(
            project_id="entity/project", object_id="obj1", digest="abc123"
        )
        middleware.obj_read(req)

        mock_server.obj_read.assert_called_once_with(req)

        records = _read_records(log_file)
        assert len(records) == 1
        assert records[0]["method"] == "obj_read"
        assert "timestamp" in records[0]
        assert records[0]["args"][0]["project_id"] == "entity/project"
        assert records[0]["args"][0]["object_id"] == "obj1"

    def test_logs_call_start(self, middleware, mock_server, log_file):
        req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="entity/project",
                id="call-id",
                op_name="my_op",
                trace_id="trace-1",
                parent_id=None,
                started_at="2024-01-01T00:00:00Z",
                attributes={},
                inputs={"x": 1},
            )
        )
        middleware.call_start(req)

        mock_server.call_start.assert_called_once_with(req)
        records = _read_records(log_file)
        assert len(records) == 1
        assert records[0]["method"] == "call_start"
        assert records[0]["args"][0]["start"]["op_name"] == "my_op"

    def test_multiple_calls_append(self, middleware, mock_server, log_file):
        req1 = tsi.ObjReadReq(
            project_id="e/p", object_id="obj1", digest="d1"
        )
        req2 = tsi.ObjReadReq(
            project_id="e/p", object_id="obj2", digest="d2"
        )
        middleware.obj_read(req1)
        middleware.obj_read(req2)

        records = _read_records(log_file)
        assert len(records) == 2
        assert records[0]["args"][0]["object_id"] == "obj1"
        assert records[1]["args"][0]["object_id"] == "obj2"


class TestLoggingMiddlewareNoArgsMethods:
    def test_server_info_no_args_key(self, middleware, log_file):
        middleware.server_info()

        records = _read_records(log_file)
        assert len(records) == 1
        assert records[0]["method"] == "server_info"
        assert "args" not in records[0]
        assert "kwargs" not in records[0]


class TestLoggingMiddlewareDelegation:
    def test_delegates_to_underlying_server(self, middleware, mock_server):
        req = tsi.ObjReadReq(
            project_id="e/p", object_id="obj1", digest="abc"
        )
        mock_server.obj_read.return_value = "fake_response"

        result = middleware.obj_read(req)

        assert result == "fake_response"
        mock_server.obj_read.assert_called_once_with(req)

    def test_delegates_server_info(self, middleware, mock_server):
        mock_server.server_info.return_value = "info"
        result = middleware.server_info()
        assert result == "info"


class TestLoggingMiddlewareThreadSafety:
    def test_concurrent_writes_produce_valid_jsonl(
        self, mock_server, log_file
    ):
        middleware = LoggingMiddlewareTraceServer(mock_server, log_file)
        num_threads = 50

        def call_method(i: int) -> None:
            req = tsi.ObjReadReq(
                project_id="e/p", object_id=f"obj{i}", digest="abc"
            )
            middleware.obj_read(req)

        threads = [
            threading.Thread(target=call_method, args=(i,))
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


class TestLoggingMiddlewareErrorResilience:
    @pytest.mark.disable_logging_error_check
    def test_unwritable_path_does_not_break_delegation(self, mock_server):
        middleware = LoggingMiddlewareTraceServer(
            mock_server, "/nonexistent/dir/trace.jsonl"
        )
        mock_server.obj_read.return_value = "result"

        req = tsi.ObjReadReq(
            project_id="e/p", object_id="obj1", digest="abc"
        )
        result = middleware.obj_read(req)

        assert result == "result"
        mock_server.obj_read.assert_called_once_with(req)


class TestLoggingMiddlewareFromEnv:
    def test_from_env_reads_setting(self, monkeypatch, mock_server, tmp_path):
        log_path = str(tmp_path / "trace.jsonl")
        monkeypatch.setenv("WEAVE_TRACE_LOG_FILE_PATH", log_path)

        mw = LoggingMiddlewareTraceServer.from_env(mock_server)
        assert mw._log_file_path == log_path

    def test_from_env_raises_when_not_set(self, monkeypatch, mock_server):
        monkeypatch.delenv("WEAVE_TRACE_LOG_FILE_PATH", raising=False)
        # Also clear any context var that might be set
        monkeypatch.setattr(
            "weave.trace.settings._context_vars",
            {
                **__import__("weave.trace.settings", fromlist=["_context_vars"])._context_vars,
            },
        )
        with pytest.raises(ValueError, match="trace_log_file_path must be set"):
            LoggingMiddlewareTraceServer.from_env(mock_server)
