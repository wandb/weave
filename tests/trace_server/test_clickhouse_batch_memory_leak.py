"""Tests verifying no memory leak in ClickHouse batch error paths.

These tests ensure that _call_batch and _file_batch are properly cleared
when ClickHouse insert operations fail, preventing unbounded memory growth.
"""

import base64
import datetime
from unittest.mock import MagicMock, patch

import pytest

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import trace_server_interface as tsi


class ClickHouseConnectionError(Exception):
    """Simulates a ClickHouse connection/network error."""

    pass


def _make_project_id() -> str:
    """Create a valid base64-encoded project ID."""
    return base64.b64encode(b"test_entity/test_project").decode("utf-8")


def _make_call_start_req(project_id: str, op_name: str) -> tsi.CallStartReq:
    """Create a CallStartReq for testing."""
    return tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            op_name=op_name,
            started_at=datetime.datetime.now(datetime.timezone.utc),
            attributes={},
            inputs={"test_input": "value"},
        )
    )


@pytest.mark.disable_logging_error_check
def test_call_batch_clears_on_insert_failure():
    """Verify _call_batch is cleared even when insert fails with non-InsertTooLarge error.

    This prevents memory leaks from accumulated batch data when ClickHouse
    experiences connection errors, timeouts, or other failures.
    """
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.side_effect = ClickHouseConnectionError("Connection refused")

    project_id = _make_project_id()

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")

        # Make multiple failing calls
        for i in range(5):
            try:
                req = _make_call_start_req(project_id, f"test_op_{i}")
                server.call_start(req)
            except ClickHouseConnectionError:
                pass

        # Batch should be empty - no accumulated data from failed inserts
        assert len(server._call_batch) == 0, (
            f"Memory leak: _call_batch retained {len(server._call_batch)} rows "
            f"after failed inserts. Batch should be cleared on any exception."
        )


@pytest.mark.disable_logging_error_check
def test_file_batch_clears_on_insert_failure():
    """Verify _file_batch is cleared even when insert fails."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.side_effect = ClickHouseConnectionError("Connection refused")

    with patch.object(
        chts.ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = chts.ClickHouseTraceServer(host="test_host")

        # Add a file chunk and try to flush
        file_chunk = MagicMock()
        file_chunk.model_dump.return_value = {
            "project_id": "test",
            "digest": "digest_0",
            "n_chunks": 1,
            "chunk_index": 0,
            "b64_data": "dGVzdA==",
        }
        server._file_batch.append(file_chunk)

        try:
            server._flush_file_chunks()
        except ClickHouseConnectionError:
            pass

        # Batch should be empty after failed flush
        assert len(server._file_batch) == 0, (
            f"Memory leak: _file_batch retained {len(server._file_batch)} items "
            f"after failed insert. Batch should be cleared on any exception."
        )
