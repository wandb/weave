"""Tests for offline mode functionality."""

import gzip
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import weave
from weave.trace_server_bindings.offline_trace_server import OfflineTraceServer
from weave.trace.offline_sync import OfflineDataSyncer
from weave.trace_server import trace_server_interface as tsi


def test_offline_trace_server_init():
    """Test OfflineTraceServer initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        server = OfflineTraceServer(offline_dir=Path(tmpdir))
        assert server.offline_dir == Path(tmpdir)
        assert server.compress is True
        assert server.max_file_size_bytes == 100 * 1024 * 1024


def test_offline_trace_server_ensure_project():
    """Test project creation in offline mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        server = OfflineTraceServer(offline_dir=Path(tmpdir))
        result = server.ensure_project_exists("test_entity", "test_project")
        
        assert result.project_name == "test_project"
        
        # Check that project directory was created
        project_dir = Path(tmpdir) / "test_entity" / "test_project"
        assert project_dir.exists()
        
        # Check metadata was written
        metadata_files = list((project_dir / "metadata").glob("*.jsonl*"))
        assert len(metadata_files) > 0


def test_offline_trace_server_call_logging():
    """Test logging call start and end in offline mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        server = OfflineTraceServer(offline_dir=Path(tmpdir), compress=False)
        
        # Create a call start request
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="test_entity/test_project",
                id="call_123",
                trace_id="trace_456",
                op_name="test_op",
                inputs={"x": 1, "y": 2},
                started_at="2024-01-01T00:00:00Z",
            )
        )
        
        # Log call start
        result = server.call_start(call_start_req)
        assert result.id == "call_123"
        assert result.trace_id == "trace_456"
        
        # Create a call end request
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id="test_entity/test_project",
                id="call_123",
                ended_at="2024-01-01T00:00:10Z",
                output={"result": 3},
            )
        )
        
        # Log call end
        server.call_end(call_end_req)
        
        # Check that data was written to files
        calls_dir = Path(tmpdir) / "test_entity" / "test_project" / "calls"
        assert calls_dir.exists()
        
        call_files = list(calls_dir.glob("*.jsonl"))
        assert len(call_files) > 0
        
        # Read and verify the logged data
        with open(call_files[0], "r") as f:
            lines = f.readlines()
            assert len(lines) == 2  # One for start, one for end
            
            start_record = json.loads(lines[0])
            assert start_record["type"] == "call_start"
            assert start_record["data"]["id"] == "call_123"
            assert start_record["data"]["inputs"] == {"x": 1, "y": 2}
            
            end_record = json.loads(lines[1])
            assert end_record["type"] == "call_end"
            assert end_record["data"]["id"] == "call_123"
            assert end_record["data"]["output"] == {"result": 3}


def test_offline_trace_server_compression():
    """Test that files are compressed when compression is enabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        server = OfflineTraceServer(offline_dir=Path(tmpdir), compress=True)
        
        # Log a call
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="test_entity/test_project",
                id="call_123",
                trace_id="trace_456",
                op_name="test_op",
                inputs={"data": "test"},
                started_at="2024-01-01T00:00:00Z",
            )
        )
        
        server.call_start(call_start_req)
        server.close()  # Close to flush the file
        
        # Check that compressed file was created
        calls_dir = Path(tmpdir) / "test_entity" / "test_project" / "calls"
        compressed_files = list(calls_dir.glob("*.jsonl.gz"))
        assert len(compressed_files) > 0
        
        # Verify we can read the compressed file
        with gzip.open(compressed_files[0], "rt") as f:
            data = json.loads(f.readline())
            assert data["type"] == "call_start"


def test_offline_trace_server_file_rotation():
    """Test that new files are created when size limit is reached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set a very small file size limit
        server = OfflineTraceServer(
            offline_dir=Path(tmpdir), 
            compress=False,
            max_file_size_mb=0.001  # 1KB
        )
        
        # Log many calls to exceed file size
        for i in range(100):
            call_start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="test_entity/test_project",
                    id=f"call_{i}",
                    trace_id=f"trace_{i}",
                    op_name="test_op",
                    inputs={"data": "x" * 100},  # Large input
                    started_at="2024-01-01T00:00:00Z",
                )
            )
            server.call_start(call_start_req)
        
        server.close()
        
        # Check that multiple files were created
        calls_dir = Path(tmpdir) / "test_entity" / "test_project" / "calls"
        call_files = list(calls_dir.glob("*.jsonl"))
        assert len(call_files) > 1  # Should have rotated to new files


def test_offline_data_syncer():
    """Test syncing offline data to remote server."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some offline data
        offline_server = OfflineTraceServer(offline_dir=Path(tmpdir), compress=False)
        
        # Log some calls
        for i in range(3):
            call_start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id="test_entity/test_project",
                    id=f"call_{i}",
                    trace_id=f"trace_{i}",
                    op_name="test_op",
                    inputs={"index": i},
                    started_at="2024-01-01T00:00:00Z",
                )
            )
            offline_server.call_start(call_start_req)
            
            call_end_req = tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id="test_entity/test_project",
                    id=f"call_{i}",
                    ended_at="2024-01-01T00:00:10Z",
                    output={"result": i * 2},
                )
            )
            offline_server.call_end(call_end_req)
        
        offline_server.close()
        
        # Create a mock remote server
        mock_remote_server = MagicMock(spec=tsi.TraceServerInterface)
        mock_remote_server.ensure_project_exists.return_value = tsi.EnsureProjectExistsRes(
            project_name="test_project"
        )
        mock_remote_server.call_start.return_value = tsi.CallStartRes(
            id="call_id", trace_id="trace_id"
        )
        mock_remote_server.call_end.return_value = tsi.CallEndRes()
        
        # Sync the data
        syncer = OfflineDataSyncer(mock_remote_server, Path(tmpdir))
        results = syncer.sync_project("test_entity", "test_project")
        
        # Check that sync was successful
        assert results["calls"][0] == 6  # 3 starts + 3 ends
        assert results["calls"][1] == 0  # No errors
        
        # Verify remote server was called
        assert mock_remote_server.ensure_project_exists.called
        assert mock_remote_server.call_start.call_count == 3
        assert mock_remote_server.call_end.call_count == 3
        
        # Check that files were marked as synced
        calls_dir = Path(tmpdir) / "test_entity" / "test_project" / "calls"
        synced_files = list(calls_dir.glob("*.synced.jsonl"))
        assert len(synced_files) > 0


@pytest.mark.asyncio
async def test_weave_init_offline_mode():
    """Test initializing weave in offline mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize in offline mode
        client = weave.init("test_project", offline=True, offline_dir=tmpdir)
        
        # Create a simple op
        @weave.op
        def add(x: int, y: int) -> int:
            return x + y
        
        # Call the op
        result = add(2, 3)
        assert result == 5
        
        # Finish to flush data
        weave.finish()
        
        # Check that data was written to offline storage
        calls_dir = Path(tmpdir) / "offline" / "test_project" / "calls"
        assert calls_dir.exists()
        
        call_files = list(calls_dir.glob("*.jsonl*"))
        assert len(call_files) > 0


def test_sync_offline_data_function():
    """Test the sync_offline_data function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some offline data
        offline_server = OfflineTraceServer(offline_dir=Path(tmpdir), compress=False)
        
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id="test_entity/test_project",
                id="call_123",
                trace_id="trace_456",
                op_name="test_op",
                inputs={"x": 1},
                started_at="2024-01-01T00:00:00Z",
            )
        )
        offline_server.call_start(call_start_req)
        offline_server.close()
        
        # Mock the remote server creation
        with patch("weave.trace.weave_init.init_weave_get_server") as mock_get_server:
            mock_remote = MagicMock(spec=tsi.TraceServerInterface)
            mock_remote.ensure_project_exists.return_value = tsi.EnsureProjectExistsRes(
                project_name="test_project"
            )
            mock_remote.call_start.return_value = tsi.CallStartRes(
                id="call_id", trace_id="trace_id"
            )
            mock_get_server.return_value = mock_remote
            
            # Sync the data
            from weave.trace.weave_init import sync_offline_data
            results = sync_offline_data(
                offline_dir=tmpdir,
                project_name="test_entity/test_project"
            )
            
            # Check results
            assert "test_entity/test_project" in results
            assert results["test_entity/test_project"]["calls"][0] > 0