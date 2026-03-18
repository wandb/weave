"""Tests for the WAL tee trace server middleware."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from weave.durability.wal_tee_trace_server import WALTeeTraceServer, _req_to_dict
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture
def mock_server():
    """A mock trace server that records calls."""
    server = MagicMock()
    server.call_start.return_value = tsi.CallStartRes(
        id="call-1", trace_id="trace-1"
    )
    server.call_end.return_value = tsi.CallEndRes()
    server.call_update.return_value = tsi.CallUpdateRes()
    server.call_start_batch.return_value = tsi.CallCreateBatchRes(res=[])
    server.obj_create.return_value = tsi.ObjCreateRes(digest="abc123")
    server.table_create.return_value = tsi.TableCreateRes(digest="tbl123")
    server.table_update.return_value = tsi.TableUpdateRes(digest="tbl456")
    server.file_create.return_value = tsi.FileCreateRes(digest="file123")
    server.feedback_create.return_value = tsi.FeedbackCreateRes(
        id="fb1",
        created_at="2024-01-01T00:00:00Z",
        wb_user_id="user1",
        payload={"key": "value"},
    )
    server.feedback_replace.return_value = tsi.FeedbackReplaceRes(
        id="fb2",
        created_at="2024-01-01T00:00:00Z",
        wb_user_id="user1",
        payload={"key": "value"},
    )
    server.cost_create.return_value = tsi.CostCreateRes(ids=[("gpt-4", "id1")])
    return server


@pytest.fixture
def wal_writer():
    """A mock WAL writer that records written records."""
    writer = MagicMock()

    def capture_write(record):
        return len(json.dumps(record))

    writer.write.side_effect = capture_write
    return writer


@pytest.fixture
def tee(mock_server, wal_writer):
    return WALTeeTraceServer(mock_server, wal_writer)


class TestWALTeeBasics:
    def test_call_start_tees_to_wal(self, tee, mock_server, wal_writer):
        req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="entity/project",
                id="call-1",
                op_name="my_op",
                trace_id="trace-1",
                started_at="2024-01-01T00:00:00Z",
                attributes={},
                inputs={"x": 1},
            )
        )
        result = tee.call_start(req)

        # Verify delegate was called
        mock_server.call_start.assert_called_once_with(req)
        assert isinstance(result, tsi.CallStartRes)

        # Verify WAL was written
        wal_writer.write.assert_called_once()
        record = wal_writer.write.call_args[0][0]
        assert record["type"] == "call_start"
        assert record["req"]["start"]["project_id"] == "entity/project"
        assert record["req"]["start"]["op_name"] == "my_op"

    def test_call_end_tees_to_wal(self, tee, mock_server, wal_writer):
        req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id="entity/project",
                id="call-1",
                ended_at="2024-01-01T00:01:00Z",
                output={"result": 42},
                summary={},
            )
        )
        result = tee.call_end(req)

        mock_server.call_end.assert_called_once_with(req)
        assert isinstance(result, tsi.CallEndRes)

        record = wal_writer.write.call_args[0][0]
        assert record["type"] == "call_end"
        assert record["req"]["end"]["id"] == "call-1"

    def test_obj_create_tees_to_wal(self, tee, mock_server, wal_writer):
        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="entity/project",
                object_id="my-obj",
                val={"data": [1, 2, 3]},
            )
        )
        result = tee.obj_create(req)

        mock_server.obj_create.assert_called_once_with(req)
        assert result.digest == "abc123"

        record = wal_writer.write.call_args[0][0]
        assert record["type"] == "obj_create"
        assert record["req"]["obj"]["object_id"] == "my-obj"
        assert record["req"]["obj"]["val"] == {"data": [1, 2, 3]}

    def test_file_create_tees_to_wal_with_bytes(self, tee, mock_server, wal_writer):
        req = tsi.FileCreateReq(
            project_id="entity/project",
            name="test.txt",
            content=b"hello world",
        )
        result = tee.file_create(req)

        mock_server.file_create.assert_called_once_with(req)
        assert result.digest == "file123"

        record = wal_writer.write.call_args[0][0]
        assert record["type"] == "file_create"
        assert record["req"]["project_id"] == "entity/project"
        # bytes should be base64-encoded
        assert isinstance(record["req"]["content"], str)

    def test_table_create_tees_to_wal(self, tee, mock_server, wal_writer):
        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id="entity/project",
                rows=[{"digest": "d1", "val": {"a": 1}}],
            )
        )
        result = tee.table_create(req)

        mock_server.table_create.assert_called_once_with(req)
        assert result.digest == "tbl123"

        record = wal_writer.write.call_args[0][0]
        assert record["type"] == "table_create"

    def test_feedback_create_tees_to_wal(self, tee, mock_server, wal_writer):
        req = tsi.FeedbackCreateReq(
            project_id="entity/project",
            weave_ref="weave:///entity/project/call/call-1",
            feedback_type="reaction",
            payload={"emoji": "thumbsup"},
        )
        result = tee.feedback_create(req)

        mock_server.feedback_create.assert_called_once_with(req)
        assert result.id == "fb1"

        record = wal_writer.write.call_args[0][0]
        assert record["type"] == "feedback_create"
        assert record["req"]["project_id"] == "entity/project"

    def test_cost_create_tees_to_wal(self, tee, mock_server, wal_writer):
        req = tsi.CostCreateReq(
            project_id="entity/project",
            costs={
                "gpt-4": tsi.CostCreateInput(
                    prompt_token_cost=0.03,
                    completion_token_cost=0.06,
                    prompt_token_cost_unit="USD/1k tokens",
                    completion_token_cost_unit="USD/1k tokens",
                ),
            },
        )
        result = tee.cost_create(req)

        mock_server.cost_create.assert_called_once_with(req)
        record = wal_writer.write.call_args[0][0]
        assert record["type"] == "cost_create"


class TestWALTeeErrorHandling:
    @pytest.mark.disable_logging_error_check
    def test_wal_failure_does_not_block_write(self, mock_server, caplog):
        """If WAL write fails, the request should still go through."""
        wal_writer = MagicMock()
        wal_writer.write.side_effect = OSError("disk full")
        tee = WALTeeTraceServer(mock_server, wal_writer)

        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="entity/project",
                object_id="my-obj",
                val={"data": 1},
            )
        )
        with caplog.at_level(logging.ERROR, logger="weave.durability.wal_tee_trace_server"):
            result = tee.obj_create(req)

        # The delegate should still have been called
        mock_server.obj_create.assert_called_once_with(req)
        assert result.digest == "abc123"
        assert "Failed to write obj_create to WAL" in caplog.text

    def test_delegate_failure_propagates(self, wal_writer):
        """If the delegate fails, the exception should propagate."""
        server = MagicMock()
        server.call_start.side_effect = RuntimeError("server down")
        tee = WALTeeTraceServer(server, wal_writer)

        req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="entity/project",
                id="call-1",
                op_name="my_op",
                trace_id="trace-1",
                started_at="2024-01-01T00:00:00Z",
                attributes={},
                inputs={},
            )
        )
        with pytest.raises(RuntimeError, match="server down"):
            tee.call_start(req)

        # WAL should still have been written before the error
        wal_writer.write.assert_called_once()


class TestWALTeeDelegation:
    def test_read_methods_pass_through(self, tee, mock_server, wal_writer):
        """Read methods should delegate without touching the WAL."""
        mock_server.obj_read.return_value = "obj_read_result"

        req = tsi.ObjReadReq(
            project_id="entity/project",
            object_id="my-obj",
            digest="abc",
        )
        result = tee.obj_read(req)

        mock_server.obj_read.assert_called_once_with(req)
        assert result == "obj_read_result"
        wal_writer.write.assert_not_called()

    def test_close_closes_both(self, tee, mock_server, wal_writer):
        """close() should close both the WAL writer and the delegate."""
        tee.close()
        wal_writer.close.assert_called_once()
        mock_server.close.assert_called_once()


class TestWALTeeRecordFormat:
    def test_record_is_json_serializable(self, tee, wal_writer):
        """WAL records must be fully JSON-serializable."""
        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="entity/project",
                object_id="my-obj",
                val={"nested": {"deep": [1, 2, 3]}},
            )
        )
        tee.obj_create(req)

        record = wal_writer.write.call_args[0][0]
        # Should not raise
        serialized = json.dumps(record)
        deserialized = json.loads(serialized)
        assert deserialized["type"] == "obj_create"
        assert deserialized["req"]["obj"]["val"] == {"nested": {"deep": [1, 2, 3]}}

    def test_bytes_content_serializable(self, tee, wal_writer):
        """Bytes fields should be serialized to base64 strings."""
        req = tsi.FileCreateReq(
            project_id="entity/project",
            name="binary.bin",
            content=b"\x00\x01\x02\xff",
        )
        tee.file_create(req)

        record = wal_writer.write.call_args[0][0]
        # Must not raise on json.dumps
        json.dumps(record)
        # Content should be base64-encoded
        assert isinstance(record["req"]["content"], str)


class TestAllInterceptedMethods:
    """Verify every intercepted write method tees to WAL and delegates."""

    @pytest.mark.parametrize(
        "method_name",
        [
            "call_start",
            "call_end",
            "call_start_batch",
            "call_update",
            "calls_complete",
            "call_start_v2",
            "call_end_v2",
            "obj_create",
            "table_create",
            "table_update",
            "file_create",
            "feedback_create",
            "feedback_create_batch",
            "feedback_replace",
            "cost_create",
        ],
    )
    def test_method_tees_and_delegates(self, method_name, wal_writer):
        server = MagicMock()
        sentinel = MagicMock(name="response")
        getattr(server, method_name).return_value = sentinel
        tee = WALTeeTraceServer(server, wal_writer)

        fake_req = MagicMock(spec=BaseModel)
        fake_req.model_dump.return_value = {"fake": "data"}

        result = getattr(tee, method_name)(fake_req)

        # Delegate was called
        getattr(server, method_name).assert_called_once_with(fake_req)
        assert result is sentinel

        # WAL was written with correct type
        wal_writer.write.assert_called_once()
        record = wal_writer.write.call_args[0][0]
        assert record["type"] == method_name
        assert record["req"] == {"fake": "data"}


class TestReqToDict:
    def test_simple_model(self):
        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id="e/p",
                object_id="obj",
                val={"x": 1},
            )
        )
        d = _req_to_dict(req)
        assert d["obj"]["project_id"] == "e/p"
        assert d["obj"]["val"] == {"x": 1}

    def test_bytes_are_base64_encoded(self):
        req = tsi.FileCreateReq(
            project_id="e/p",
            name="f.bin",
            content=b"\xff\xfe",
        )
        d = _req_to_dict(req)
        # Should not raise
        json.dumps(d)
        assert isinstance(d["content"], str)
