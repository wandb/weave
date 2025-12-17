"""Tests for Claude plugin daemon."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWeaveDaemon:
    """Test the WeaveDaemon class."""

    def test_socket_path_generation(self):
        """Test socket path is generated correctly."""
        from weave.integrations.claude_plugin.core.socket_client import get_socket_path

        path = get_socket_path("test-session-123")
        assert path.name == "daemon-test-session-123.sock"
        assert ".cache/weave" in str(path)

    def test_daemon_client_not_running(self):
        """Test daemon client detects when daemon is not running."""
        from weave.integrations.claude_plugin.core.socket_client import DaemonClient

        client = DaemonClient("nonexistent-session")
        assert not client.is_daemon_running()

    def test_state_manager_with_new_fields(self):
        """Test state manager handles new daemon fields."""
        from weave.integrations.claude_plugin.core.state import (
            StateManager,
            create_session_data,
        )

        session_data = create_session_data(
            project="test/project",
            daemon_pid=12345,
            last_processed_line=100,
            transcript_path="/path/to/session.jsonl",
            trace_url="https://example.com/trace",
        )

        assert session_data["daemon_pid"] == 12345
        assert session_data["last_processed_line"] == 100
        assert session_data["transcript_path"] == "/path/to/session.jsonl"
        assert session_data["trace_url"] == "https://example.com/trace"


class TestDaemonClient:
    """Test the DaemonClient class."""

    def test_cleanup_stale_socket(self, tmp_path):
        """Test cleanup of stale socket files."""
        from weave.integrations.claude_plugin.core.socket_client import DaemonClient

        # Create a fake socket file
        with patch(
            "weave.integrations.claude_plugin.core.socket_client.SOCKET_DIR",
            tmp_path,
        ):
            client = DaemonClient("test-session")
            client.socket_path = tmp_path / "daemon-test-session.sock"
            client.socket_path.touch()

            assert client.socket_path.exists()
            client.cleanup_stale_socket()
            assert not client.socket_path.exists()

    def test_is_process_alive(self):
        """Test process liveness check."""
        import os

        from weave.integrations.claude_plugin.core.socket_client import DaemonClient

        client = DaemonClient("test")

        # Current process should be alive
        assert client.is_process_alive(os.getpid())

        # Non-existent PID should not be alive
        assert not client.is_process_alive(999999999)


class TestSubagentTracker:
    """Test SubagentTracker dataclass."""

    def test_subagent_tracker_is_tailing_false_when_no_call_id(self):
        """SubagentTracker.is_tailing returns False until subagent_call_id is set."""
        from datetime import datetime, timezone

        from weave.integrations.claude_plugin.core.daemon import SubagentTracker

        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-456",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="session-789",
        )

        assert tracker.is_tailing is False
        assert tracker.agent_id is None
        assert tracker.transcript_path is None

    def test_subagent_tracker_is_tailing_true_when_call_id_set(self):
        """SubagentTracker.is_tailing returns True once subagent_call_id is set."""
        from datetime import datetime, timezone
        from pathlib import Path

        from weave.integrations.claude_plugin.core.daemon import SubagentTracker

        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-456",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="session-789",
        )

        # Simulate finding the file
        tracker.agent_id = "abc12345"
        tracker.transcript_path = Path("/tmp/agent-abc12345.jsonl")
        tracker.subagent_call_id = "weave-call-xyz"

        assert tracker.is_tailing is True


class TestWeaveDaemonTrackerDicts:
    """Test WeaveDaemon tracker dictionaries."""

    def test_daemon_has_subagent_tracker_dicts(self):
        """WeaveDaemon has dictionaries for tracking subagents."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")

        assert hasattr(daemon, '_subagent_trackers')
        assert hasattr(daemon, '_subagent_by_agent_id')
        assert isinstance(daemon._subagent_trackers, dict)
        assert isinstance(daemon._subagent_by_agent_id, dict)


class TestTaskToolWithSubagentType:
    """Test Task tool with subagent_type creates tracker."""

    @pytest.mark.anyio
    async def test_task_tool_with_subagent_type_creates_tracker(self):
        """Task tool with subagent_type creates SubagentTracker."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon, SubagentTracker

        daemon = WeaveDaemon("test-session-123")
        daemon.weave_client = MagicMock()
        daemon.current_turn_call_id = "turn-call-456"
        daemon.session_call_id = "session-call-789"
        daemon.trace_id = "trace-abc"

        # Simulate assistant message with Task tool containing subagent_type
        obj = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-use-xyz",
                        "name": "Task",
                        "input": {
                            "prompt": "Search the codebase",
                            "subagent_type": "Explore",
                        }
                    }
                ]
            }
        }

        await daemon._handle_assistant_message(obj, line_num=10)

        # Verify tracker was created
        assert "tool-use-xyz" in daemon._subagent_trackers
        tracker = daemon._subagent_trackers["tool-use-xyz"]
        assert isinstance(tracker, SubagentTracker)
        assert tracker.tool_use_id == "tool-use-xyz"
        assert tracker.turn_call_id == "turn-call-456"
        assert tracker.parent_session_id == "test-session-123"
        assert tracker.is_tailing is False  # Not yet found file


class TestSessionsDirectoryHelper:
    """Test sessions directory helper method."""

    def test_daemon_get_sessions_directory(self):
        """WeaveDaemon can determine the sessions directory from transcript path."""
        from pathlib import Path

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.transcript_path = Path("/Users/test/.claude/projects/abc123/session-xyz.jsonl")

        sessions_dir = daemon._get_sessions_directory()

        assert sessions_dir == Path("/Users/test/.claude/projects/abc123")

    def test_daemon_get_sessions_directory_none_when_no_transcript(self):
        """WeaveDaemon returns None when no transcript path set."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.transcript_path = None

        sessions_dir = daemon._get_sessions_directory()

        assert sessions_dir is None


class TestScanForSubagentFiles:
    """Test _scan_for_subagent_files method."""

    @pytest.mark.anyio
    async def test_scan_for_subagent_files_finds_matching_file(self, tmp_path):
        """_scan_for_subagent_files finds and matches subagent files by sessionId."""
        from datetime import datetime, timezone
        import time

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon, SubagentTracker

        daemon = WeaveDaemon("parent-session-uuid")
        daemon.session_id = "parent-session-uuid"
        daemon.transcript_path = tmp_path / "session.jsonl"
        daemon.transcript_path.touch()

        # Create a pending tracker
        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-456",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="parent-session-uuid",
        )
        daemon._subagent_trackers["tool-123"] = tracker

        # Wait a tiny bit so file will be "after" detection
        time.sleep(0.01)

        # Create a subagent file with matching sessionId
        agent_file = tmp_path / "agent-abc123.jsonl"
        agent_file.write_text(json.dumps({
            "type": "assistant",
            "sessionId": "parent-session-uuid",
            "agentId": "abc123",
            "isSidechain": True,
            "message": {"content": [{"type": "text", "text": "Hello"}]}
        }) + "\n")

        # Mock _start_tailing_subagent to track if it gets called
        start_tailing_called = []
        async def mock_start_tailing(session, path):
            start_tailing_called.append((session.agent_id, path))
        daemon._start_tailing_subagent = mock_start_tailing

        await daemon._scan_for_subagent_files()

        assert len(start_tailing_called) == 1
        assert start_tailing_called[0][0] == "abc123"

    @pytest.mark.anyio
    async def test_scan_for_subagent_files_ignores_other_sessions(self, tmp_path):
        """_scan_for_subagent_files ignores files from other sessions."""
        from datetime import datetime, timezone

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon, SubagentTracker

        daemon = WeaveDaemon("parent-session-uuid")
        daemon.session_id = "parent-session-uuid"
        daemon.transcript_path = tmp_path / "session.jsonl"
        daemon.transcript_path.touch()

        # Create a pending tracker
        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-456",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="parent-session-uuid",
        )
        daemon._subagent_trackers["tool-123"] = tracker

        # Create a subagent file with DIFFERENT sessionId
        agent_file = tmp_path / "agent-other.jsonl"
        agent_file.write_text(json.dumps({
            "type": "assistant",
            "sessionId": "different-session-uuid",
            "agentId": "other",
            "isSidechain": True,
            "message": {"content": [{"type": "text", "text": "Hello"}]}
        }) + "\n")

        start_tailing_called = []
        async def mock_start_tailing(session, path):
            start_tailing_called.append((session.agent_id, path))
        daemon._start_tailing_subagent = mock_start_tailing

        await daemon._scan_for_subagent_files()

        # Should NOT have started tailing - wrong session
        assert len(start_tailing_called) == 0


class TestStartTailingSubagent:
    """Test _start_tailing_subagent method."""

    @pytest.mark.anyio
    async def test_start_tailing_subagent_creates_weave_call(self, tmp_path):
        """_start_tailing_subagent creates Weave call and updates tracker."""
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon, SubagentTracker
        from weave.integrations.claude_plugin.session.session_parser import Session

        daemon = WeaveDaemon("parent-session-uuid")
        daemon.session_id = "parent-session-uuid"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-123"
        daemon.session_call_id = "session-call-456"
        daemon.current_turn_call_id = "turn-call-789"

        # Mock create_call to return a call with an id
        mock_call = MagicMock()
        mock_call.id = "subagent-call-xyz"
        daemon.weave_client.create_call.return_value = mock_call

        # Create a pending tracker
        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-call-789",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="parent-session-uuid",
        )
        daemon._subagent_trackers["tool-123"] = tracker

        # Create mock session
        session = MagicMock(spec=Session)
        session.session_id = "parent-session-uuid"
        session.agent_id = "abc123"
        session.turns = []
        session.first_user_prompt.return_value = "Search the codebase"

        agent_file = tmp_path / "agent-abc123.jsonl"
        agent_file.touch()

        # Mock _process_subagent_updates to avoid needing to implement it yet
        daemon._process_subagent_updates = AsyncMock()

        await daemon._start_tailing_subagent(session, agent_file)

        # Verify tracker was updated
        assert tracker.agent_id == "abc123"
        assert tracker.transcript_path == agent_file
        assert tracker.subagent_call_id == "subagent-call-xyz"
        assert tracker.is_tailing is True

        # Verify secondary index was populated
        assert daemon._subagent_by_agent_id["abc123"] is tracker

        # Verify Weave call was created
        daemon.weave_client.create_call.assert_called_once()
        call_kwargs = daemon.weave_client.create_call.call_args.kwargs
        assert call_kwargs["op"] == "claude_code.subagent"
        assert "abc123" in call_kwargs["inputs"]["agent_id"]


class TestProcessSubagentUpdates:
    """Test _process_subagent_updates method."""

    @pytest.mark.anyio
    async def test_process_subagent_updates_logs_tool_calls_once(self, tmp_path):
        """_process_subagent_updates logs tool calls only once, not duplicated on re-processing."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon, SubagentTracker

        daemon = WeaveDaemon("parent-session-uuid")
        daemon.session_id = "parent-session-uuid"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-123"
        daemon.session_call_id = "session-call-456"

        # Create a tracker in tailing state
        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-call-789",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="parent-session-uuid",
        )
        tracker.agent_id = "abc123"
        tracker.subagent_call_id = "subagent-call-xyz"

        # Create an agent file with tool calls
        agent_file = tmp_path / "agent-abc123.jsonl"
        agent_file.write_text(json.dumps({
            "type": "assistant",
            "sessionId": "parent-session-uuid",
            "agentId": "abc123",
            "isSidechain": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": {
                "id": "msg-1",
                "model": "claude-opus-4",
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-call-1",
                        "name": "Read",
                        "input": {"file_path": "/tmp/test.py"}
                    }
                ]
            }
        }) + "\n" + json.dumps({
            "type": "user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-call-1",
                        "content": "file contents"
                    }
                ]
            }
        }) + "\n")

        tracker.transcript_path = agent_file
        daemon._subagent_trackers["tool-123"] = tracker

        # Track weave.log_call invocations
        log_call_count = 0
        logged_tool_ids = []

        def mock_log_call(**kwargs):
            nonlocal log_call_count
            log_call_count += 1
            # Extract tool_use_id from attributes if present
            if "attributes" in kwargs:
                logged_tool_ids.append(kwargs.get("op", "unknown"))

        # Call _process_subagent_updates TWICE
        with patch("weave.integrations.claude_plugin.core.daemon.weave.log_call", side_effect=mock_log_call):
            await daemon._process_subagent_updates(tracker)
            first_call_count = log_call_count

            # Second call should not log duplicates
            await daemon._process_subagent_updates(tracker)
            second_call_count = log_call_count

        # Verify tool calls are only logged ONCE (not duplicated)
        assert first_call_count == 1, f"Expected 1 tool call logged on first processing, got {first_call_count}"
        assert second_call_count == 1, f"Expected still 1 tool call total after second processing, got {second_call_count}"

        # Verify the tracker tracked the tool ID
        assert "tool-call-1" in tracker.logged_tool_ids


class TestFileTailerIntegration:
    """Test file tailer loop integration with subagent scanning."""

    @pytest.mark.anyio
    async def test_file_tailer_calls_scan_for_subagent_files(self):
        """File tailer loop calls _scan_for_subagent_files."""
        from pathlib import Path

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.transcript_path = Path("/tmp/test.jsonl")
        daemon.running = True

        scan_calls = []
        process_calls = []

        async def mock_scan():
            scan_calls.append(1)

        async def mock_process():
            process_calls.append(1)
            # Stop after first iteration (after process is called)
            daemon.running = False

        daemon._scan_for_subagent_files = mock_scan
        daemon._process_session_file = mock_process

        await daemon._run_file_tailer()

        # The current implementation doesn't call scan yet, so this should fail
        assert len(scan_calls) == 1
        assert len(process_calls) == 1


class TestSubagentStopFastPath:
    """Test SubagentStop fast path when already tailing."""

    @pytest.mark.anyio
    async def test_subagent_stop_fast_path_when_tailing(self, tmp_path):
        """SubagentStop uses fast path when already tailing."""
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon, SubagentTracker

        daemon = WeaveDaemon("parent-session-uuid")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-123"
        daemon.session_call_id = "session-call-456"

        # Create agent file
        agent_file = tmp_path / "agent-abc123.jsonl"
        agent_file.write_text(json.dumps({
            "type": "assistant",
            "sessionId": "parent-session-uuid",
            "agentId": "abc123",
            "isSidechain": True,
            "uuid": "msg-1",
            "timestamp": "2025-01-01T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Done!"}],
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }
        }) + "\n")

        # Create tracker in tailing state
        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-456",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="parent-session-uuid",
        )
        tracker.agent_id = "abc123"
        tracker.transcript_path = agent_file
        tracker.subagent_call_id = "subagent-call-xyz"
        tracker.last_processed_line = 1

        daemon._subagent_trackers["tool-123"] = tracker
        daemon._subagent_by_agent_id["abc123"] = tracker

        # Mock process_subagent_updates
        daemon._process_subagent_updates = AsyncMock()

        payload = {
            "agent_transcript_path": str(agent_file),
            "agent_id": "abc123",
        }

        result = await daemon._handle_subagent_stop(payload)

        # Verify fast path was used
        assert result["status"] == "ok"
        daemon._process_subagent_updates.assert_called_once_with(tracker)
        daemon.weave_client.finish_call.assert_called_once()

        # Verify cleanup
        assert "tool-123" not in daemon._subagent_trackers
        assert "abc123" not in daemon._subagent_by_agent_id


class TestSubagentFileBackups:
    """Test file backup handling for subagents."""

    @pytest.mark.anyio
    async def test_subagent_stop_includes_file_snapshots(self, tmp_path):
        """SubagentStop should include file snapshots and diff view in output."""
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon, SubagentTracker

        daemon = WeaveDaemon("parent-session-uuid")
        daemon.session_id = "parent-session-uuid"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-123"
        daemon.session_call_id = "session-call-456"
        daemon.current_turn_call_id = "turn-789"

        # Create file-history directory structure
        file_history_dir = tmp_path / ".claude" / "file-history" / "parent-session-uuid"
        file_history_dir.mkdir(parents=True)

        # Create a backup file
        backup_file = file_history_dir / "abc123hash@v1"
        backup_file.write_text("# Original content\nprint('hello')")

        # Create agent file with file-history-snapshot
        agent_file = tmp_path / "agent-abc123.jsonl"
        agent_file.write_text(
            json.dumps({
                "type": "user",
                "sessionId": "parent-session-uuid",
                "agentId": "abc123",
                "isSidechain": True,
                "uuid": "user-msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "message": {"role": "user", "content": "Edit the file"}
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "sessionId": "parent-session-uuid",
                "agentId": "abc123",
                "isSidechain": True,
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "tool_use", "id": "tool-1", "name": "Edit", "input": {"file_path": "/tmp/test.py"}}
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 50}
                }
            }) + "\n" +
            json.dumps({
                "type": "file-history-snapshot",
                "snapshot": {
                    "messageId": "msg-1",
                    "trackedFileBackups": {
                        "/tmp/test.py": {
                            "backupFileName": "abc123hash@v1",
                            "version": 1,
                            "backupTime": "2025-01-01T10:00:01Z"
                        }
                    }
                }
            }) + "\n"
        )

        # Create tracker in tailing state
        tracker = SubagentTracker(
            tool_use_id="tool-123",
            turn_call_id="turn-789",
            detected_at=datetime.now(timezone.utc),
            parent_session_id="parent-session-uuid",
        )
        tracker.agent_id = "abc123"
        tracker.transcript_path = agent_file
        tracker.subagent_call_id = "subagent-call-xyz"
        tracker.last_processed_line = 3

        daemon._subagent_trackers["tool-123"] = tracker
        daemon._subagent_by_agent_id["abc123"] = tracker

        # Mock process_subagent_updates
        daemon._process_subagent_updates = AsyncMock()

        payload = {
            "agent_transcript_path": str(agent_file),
            "agent_id": "abc123",
        }

        # Patch FileBackup.load_content to use our tmp_path
        from weave.integrations.claude_plugin.session.session_parser import FileBackup
        original_load_content = FileBackup.load_content

        def patched_load_content(self, session_id, claude_dir=None):
            return original_load_content(self, session_id, claude_dir=tmp_path / ".claude")

        with patch.object(FileBackup, "load_content", patched_load_content):
            result = await daemon._handle_subagent_stop(payload)

        # Verify finish_call was called with file_snapshots in output
        assert result["status"] == "ok"
        daemon.weave_client.finish_call.assert_called_once()

        # Get the output from finish_call
        call_args = daemon.weave_client.finish_call.call_args
        output = call_args.kwargs.get("output") or call_args[1].get("output", {})

        # Should have file_snapshots as a list
        assert "file_snapshots" in output, f"Expected file_snapshots in output, got: {output.keys()}"
        file_snapshots = output["file_snapshots"]
        assert isinstance(file_snapshots, list), f"Expected list, got {type(file_snapshots)}"
        # Check that at least one Content object has the expected original_path
        original_paths = [c.metadata.get("original_path") for c in file_snapshots if hasattr(c, "metadata")]
        assert "/tmp/test.py" in original_paths, f"Expected /tmp/test.py in {original_paths}"


class TestParentTurnAggregatesSubagentFileBackups:
    """Test that parent turns aggregate file backups from subagents."""

    @pytest.mark.anyio
    async def test_finish_turn_includes_subagent_file_snapshots(self, tmp_path):
        """When finishing a turn, file snapshots from subagents should be included."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.session_id = "test-session-123"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-abc"
        daemon.session_call_id = "session-call-456"
        daemon.current_turn_call_id = "turn-call-789"
        daemon.turn_number = 1

        # Create a parent session file (no file edits directly in parent)
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session-123",
                "message": {"role": "user", "content": "Edit some files"},
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "tool_use", "id": "task-1", "name": "Task", "input": {"prompt": "Edit the file"}}
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
            }) + "\n"
        )
        daemon.transcript_path = session_file

        # Simulate that a subagent finished and stored file snapshots for this turn
        from weave.type_wrappers.Content.content import Content
        mock_content = MagicMock(spec=Content)
        daemon._subagent_file_snapshots = {
            "turn-call-789": {
                "/tmp/edited_by_subagent.py": mock_content,
            }
        }

        # Mock weave.log_call since _log_turn_tool_calls uses it directly
        with patch("weave.integrations.claude_plugin.core.daemon.weave.log_call"):
            await daemon._finish_current_turn()

        # Verify finish_call was called with file_snapshots from subagent
        daemon.weave_client.finish_call.assert_called_once()
        call_args = daemon.weave_client.finish_call.call_args
        output = call_args.kwargs.get("output") or call_args[1].get("output", {})

        assert "file_snapshots" in output, f"Expected file_snapshots in output, got: {output.keys()}"
        assert "/tmp/edited_by_subagent.py" in output["file_snapshots"]

        # Verify the subagent file snapshots were cleaned up
        assert "turn-call-789" not in daemon._subagent_file_snapshots


class TestCleanupStaleSubagentTrackers:
    """Test cleanup of stale subagent trackers."""

    @pytest.mark.anyio
    async def test_cleanup_stale_subagent_trackers(self):
        """Stale subagent trackers are cleaned up after timeout."""
        from datetime import datetime, timezone, timedelta

        from weave.integrations.claude_plugin.core.daemon import (
            WeaveDaemon,
            SubagentTracker,
            SUBAGENT_DETECTION_TIMEOUT,
        )

        daemon = WeaveDaemon("test-session")

        # Create a stale tracker (detected 15 seconds ago, beyond 10s timeout)
        stale_tracker = SubagentTracker(
            tool_use_id="stale-tool",
            turn_call_id="turn-456",
            detected_at=datetime.now(timezone.utc) - timedelta(seconds=15),
            parent_session_id="test-session",
        )
        daemon._subagent_trackers["stale-tool"] = stale_tracker

        # Create a fresh tracker (detected 2 seconds ago)
        fresh_tracker = SubagentTracker(
            tool_use_id="fresh-tool",
            turn_call_id="turn-789",
            detected_at=datetime.now(timezone.utc) - timedelta(seconds=2),
            parent_session_id="test-session",
        )
        daemon._subagent_trackers["fresh-tool"] = fresh_tracker

        daemon._cleanup_stale_subagent_trackers()

        # Stale tracker should be removed
        assert "stale-tool" not in daemon._subagent_trackers
        # Fresh tracker should remain
        assert "fresh-tool" in daemon._subagent_trackers


class TestThinkingTraceCreation:
    """Test thinking trace creation in daemon."""

    @pytest.mark.anyio
    async def test_finish_turn_creates_thinking_trace_when_present(self, tmp_path):
        """When a turn has thinking content, a thinking trace is created as child of turn."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-abc"
        daemon.session_call_id = "session-call-456"
        daemon.current_turn_call_id = "turn-call-789"
        daemon.turn_number = 1

        # Create a session file with thinking content in assistant message
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session-123",
                "message": {
                    "role": "user",
                    "content": "What is 2 + 2?",
                },
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "Let me calculate: 2 + 2 = 4. This is basic arithmetic.",
                            "signature": "abc123",
                        },
                        {"type": "text", "text": "2 + 2 = 4"},
                    ],
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                },
            }) + "\n"
        )
        daemon.transcript_path = session_file

        # Track log_call invocations
        log_call_invocations = []
        with patch("weave.integrations.claude_plugin.core.daemon.weave.log_call") as mock_log_call:
            mock_log_call.side_effect = lambda **kwargs: log_call_invocations.append(kwargs)
            await daemon._finish_current_turn()

        # Verify thinking trace was created
        thinking_calls = [c for c in log_call_invocations if c.get("op") == "claude_code.thinking"]
        assert len(thinking_calls) == 1, f"Expected 1 thinking trace, got {len(thinking_calls)}"

        thinking_call = thinking_calls[0]
        assert thinking_call["inputs"]["content"] == "Let me calculate: 2 + 2 = 4. This is basic arithmetic."
        assert thinking_call["display_name"] == "Thinking..."
        # Verify usage data is included
        assert "output" in thinking_call
        assert "usage" in thinking_call["output"]
        assert thinking_call["output"]["usage"]["input_tokens"] == 100
        assert thinking_call["output"]["usage"]["output_tokens"] == 10

    @pytest.mark.anyio
    async def test_finish_turn_no_thinking_trace_when_absent(self, tmp_path):
        """When a turn has no thinking content, no thinking trace is created."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-abc"
        daemon.session_call_id = "session-call-456"
        daemon.current_turn_call_id = "turn-call-789"
        daemon.turn_number = 1

        # Create a session file WITHOUT thinking content
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session-123",
                "message": {
                    "role": "user",
                    "content": "Hello",
                },
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {"type": "text", "text": "Hi there!"},
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            }) + "\n"
        )
        daemon.transcript_path = session_file

        # Track log_call invocations
        log_call_invocations = []
        with patch("weave.integrations.claude_plugin.core.daemon.weave.log_call") as mock_log_call:
            mock_log_call.side_effect = lambda **kwargs: log_call_invocations.append(kwargs)
            await daemon._finish_current_turn()

        # Verify NO thinking trace was created
        thinking_calls = [c for c in log_call_invocations if c.get("op") == "claude_code.thinking"]
        assert len(thinking_calls) == 0, f"Expected 0 thinking traces, got {len(thinking_calls)}"

    @pytest.mark.anyio
    async def test_multiple_assistant_messages_aggregates_thinking(self, tmp_path):
        """Multiple assistant messages with thinking should aggregate thinking content."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.trace_id = "trace-abc"
        daemon.session_call_id = "session-call-456"
        daemon.current_turn_call_id = "turn-call-789"
        daemon.turn_number = 1

        # Create a session file with multiple assistant messages with thinking
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session-123",
                "message": {"role": "user", "content": "Help me"},
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {"type": "thinking", "thinking": "First thought", "signature": "sig1"},
                        {"type": "text", "text": "First response"},
                    ],
                    "usage": {"input_tokens": 50, "output_tokens": 5},
                },
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "uuid": "msg-3",
                "timestamp": "2025-01-01T10:00:02Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {"type": "thinking", "thinking": "Second thought", "signature": "sig2"},
                        {"type": "text", "text": "Second response"},
                    ],
                    "usage": {"input_tokens": 60, "output_tokens": 6},
                },
            }) + "\n"
        )
        daemon.transcript_path = session_file

        log_call_invocations = []
        with patch("weave.integrations.claude_plugin.core.daemon.weave.log_call") as mock_log_call:
            mock_log_call.side_effect = lambda **kwargs: log_call_invocations.append(kwargs)
            await daemon._finish_current_turn()

        # Should create ONE thinking trace with aggregated content
        thinking_calls = [c for c in log_call_invocations if c.get("op") == "claude_code.thinking"]
        assert len(thinking_calls) == 1, f"Expected 1 aggregated thinking trace, got {len(thinking_calls)}"

        thinking_call = thinking_calls[0]
        # Content should include both thinking blocks
        assert "First thought" in thinking_call["inputs"]["content"]
        assert "Second thought" in thinking_call["inputs"]["content"]


class TestCleanupIntegration:
    """Test cleanup integration in file tailer loop."""

    @pytest.mark.anyio
    async def test_file_tailer_calls_cleanup(self):
        """File tailer loop calls _cleanup_stale_subagent_trackers."""
        from pathlib import Path

        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.transcript_path = Path("/tmp/test.jsonl")
        daemon.running = True

        cleanup_calls = []

        def mock_cleanup():
            cleanup_calls.append(1)

        async def mock_process():
            # Stop daemon after first iteration
            daemon.running = False

        async def noop():
            pass

        daemon._cleanup_stale_subagent_trackers = mock_cleanup
        daemon._process_session_file = mock_process
        daemon._scan_for_subagent_files = noop

        await daemon._run_file_tailer()

        assert len(cleanup_calls) == 1


class TestTurnCreationWithProcessor:
    """Test that daemon uses SessionProcessor for turn creation."""

    @pytest.mark.anyio
    async def test_handle_user_message_uses_processor(self):
        """_handle_user_message should use processor.create_turn_call()."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.session_id = "test-session-123"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-call-456"
        daemon.trace_id = "trace-abc"
        daemon.turn_number = 0

        # Initialize processor
        from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
        daemon.processor = SessionProcessor(
            client=daemon.weave_client,
            project="test/project",
            source="plugin",
        )

        # Mock the processor's create_turn_call method
        mock_turn_call = MagicMock()
        mock_turn_call.id = "turn-call-789"
        daemon.processor.create_turn_call = MagicMock(return_value=mock_turn_call)

        # Simulate a user message
        obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Write a Python function to add two numbers",
            },
        }

        await daemon._handle_user_message(obj, line_num=1)

        # Verify processor.create_turn_call was called
        daemon.processor.create_turn_call.assert_called_once()
        call_args = daemon.processor.create_turn_call.call_args

        # Verify the arguments
        assert call_args.kwargs["turn_number"] == 1
        assert "Write a Python function" in call_args.kwargs["user_message"]
        assert call_args.kwargs.get("images") is None or call_args.kwargs["images"] == []
        assert call_args.kwargs.get("is_compacted") is False

        # Verify turn call ID was stored
        assert daemon.current_turn_call_id == "turn-call-789"
        assert daemon.turn_number == 1

    @pytest.mark.anyio
    async def test_handle_user_message_with_images(self):
        """_handle_user_message should pass images to processor."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.session_id = "test-session-123"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-call-456"
        daemon.trace_id = "trace-abc"
        daemon.turn_number = 0

        # Initialize processor
        from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
        daemon.processor = SessionProcessor(
            client=daemon.weave_client,
            project="test/project",
            source="plugin",
        )

        # Mock the processor's create_turn_call method
        mock_turn_call = MagicMock()
        mock_turn_call.id = "turn-call-789"
        daemon.processor.create_turn_call = MagicMock(return_value=mock_turn_call)

        # Simulate a user message with an image
        obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                        },
                    },
                ],
            },
        }

        await daemon._handle_user_message(obj, line_num=1)

        # Verify processor.create_turn_call was called with images
        daemon.processor.create_turn_call.assert_called_once()
        call_args = daemon.processor.create_turn_call.call_args

        # Verify images were passed
        assert "images" in call_args.kwargs
        assert len(call_args.kwargs["images"]) == 1

    @pytest.mark.anyio
    async def test_handle_user_message_with_pending_question(self):
        """_handle_user_message should pass pending question context to processor."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.session_id = "test-session-123"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-call-456"
        daemon.trace_id = "trace-abc"
        daemon.turn_number = 0
        daemon._pending_question = "What file should I edit?"

        # Initialize processor
        from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
        daemon.processor = SessionProcessor(
            client=daemon.weave_client,
            project="test/project",
            source="plugin",
        )

        # Mock the processor's create_turn_call method
        mock_turn_call = MagicMock()
        mock_turn_call.id = "turn-call-789"
        daemon.processor.create_turn_call = MagicMock(return_value=mock_turn_call)

        # Simulate a user message
        obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Edit main.py please",
            },
        }

        await daemon._handle_user_message(obj, line_num=1)

        # Verify processor.create_turn_call was called with pending question
        daemon.processor.create_turn_call.assert_called_once()
        call_args = daemon.processor.create_turn_call.call_args

        # Verify pending question was passed
        assert call_args.kwargs["pending_question"] == "What file should I edit?"
        # Verify it was cleared
        assert daemon._pending_question is None

    @pytest.mark.anyio
    async def test_handle_user_message_with_compaction(self):
        """_handle_user_message should detect and mark compaction turns."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.session_id = "test-session-123"
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-call-456"
        daemon.trace_id = "trace-abc"
        daemon.turn_number = 5
        daemon.compaction_count = 0

        # Initialize processor
        from weave.integrations.claude_plugin.session.session_processor import SessionProcessor
        daemon.processor = SessionProcessor(
            client=daemon.weave_client,
            project="test/project",
            source="plugin",
        )

        # Mock the processor's create_turn_call method
        mock_turn_call = MagicMock()
        mock_turn_call.id = "turn-call-789"
        daemon.processor.create_turn_call = MagicMock(return_value=mock_turn_call)

        # Simulate a compaction message
        obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "This session is being continued from a previous conversation...",
            },
        }

        await daemon._handle_user_message(obj, line_num=1)

        # Verify processor.create_turn_call was called with is_compacted=True
        daemon.processor.create_turn_call.assert_called_once()
        call_args = daemon.processor.create_turn_call.call_args

        # Verify compaction was detected
        assert call_args.kwargs["is_compacted"] is True
        assert daemon.compaction_count == 1


class TestSessionContinuationDetection:
    """Test session continuation detection in WeaveDaemon."""

    @pytest.mark.anyio
    async def test_check_session_continuation_returns_true_when_session_ended(self):
        """Test that _check_session_continuation returns True when session_ended flag is set."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        with patch.object(WeaveDaemon, "_load_state", return_value=True):
            daemon = WeaveDaemon("test-session-123")
            daemon.session_call_id = "old-session-call-id"
            daemon.weave_client = MagicMock()

            # Set up state with session_ended=True
            with StateManager() as state:
                state.save_session("test-session-123", {
                    "session_call_id": "old-session-call-id",
                    "trace_id": "trace-123",
                    "session_ended": True,
                })

            # Check continuation detection
            result = await daemon._check_session_continuation()
            assert result is True

            # Cleanup
            with StateManager() as state:
                state.delete_session("test-session-123")

    @pytest.mark.anyio
    async def test_check_session_continuation_returns_false_when_session_not_ended(self):
        """Test that _check_session_continuation returns False when session is not ended."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        with patch.object(WeaveDaemon, "_load_state", return_value=True):
            daemon = WeaveDaemon("test-session-456")
            daemon.session_call_id = "session-call-id"
            daemon.weave_client = MagicMock()
            # API returns call without ended_at
            mock_call = MagicMock()
            mock_call.ended_at = None
            daemon.weave_client.get_call.return_value = mock_call

            # Set up state with session_ended=False
            with StateManager() as state:
                state.save_session("test-session-456", {
                    "session_call_id": "session-call-id",
                    "trace_id": "trace-456",
                    "session_ended": False,
                })

            # Check continuation detection
            result = await daemon._check_session_continuation()
            assert result is False

            # Cleanup
            with StateManager() as state:
                state.delete_session("test-session-456")

    @pytest.mark.anyio
    async def test_check_session_continuation_uses_api_fallback(self):
        """Test that _check_session_continuation falls back to API when state flag is False."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        with patch.object(WeaveDaemon, "_load_state", return_value=True):
            daemon = WeaveDaemon("test-session-789")
            daemon.session_call_id = "session-call-id"
            daemon.weave_client = MagicMock()

            # API returns call WITH ended_at set
            mock_call = MagicMock()
            mock_call.ended_at = "2024-01-01T00:00:00Z"
            daemon.weave_client.get_call.return_value = mock_call

            # Set up state with session_ended=False (not set)
            with StateManager() as state:
                state.save_session("test-session-789", {
                    "session_call_id": "session-call-id",
                    "trace_id": "trace-789",
                    "session_ended": False,
                })

            # Check continuation detection - should use API fallback
            result = await daemon._check_session_continuation()
            assert result is True

            # Verify API was called
            daemon.weave_client.get_call.assert_called_once_with(
                "session-call-id", columns=["ended_at"]
            )

            # Cleanup
            with StateManager() as state:
                state.delete_session("test-session-789")


class TestCreateContinuationSession:
    """Test continuation session creation in WeaveDaemon."""

    @pytest.mark.anyio
    async def test_continuation_display_name_has_prefix(self):
        """Test that continuation session has 'Continued: ' prefix in display name.

        The display name is generated from the new prompt, not the original session.
        """
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        with patch.object(WeaveDaemon, "_load_state", return_value=True):
            daemon = WeaveDaemon("test-continuation-session")
            daemon.session_call_id = "old-call-id"
            daemon.weave_client = MagicMock()
            daemon.processor = MagicMock()

            # Mock the processor to return a new call
            mock_new_call = MagicMock()
            mock_new_call.id = "new-call-id"
            mock_new_call.trace_id = "new-trace-id"
            mock_new_call.ui_url = "https://example.com/new"
            daemon.processor.create_session_call.return_value = (mock_new_call, "Continued: New Task Name")

            # Set up state (no display_name needed)
            with StateManager() as state:
                state.save_session("test-continuation-session", {
                    "session_call_id": "old-call-id",
                    "trace_id": "old-trace-id",
                    "session_ended": True,
                    "continuation_count": 0,
                })

            # Create continuation session
            result = await daemon._create_continuation_session_call({
                "prompt": "Now let's work on a new task",
                "cwd": "/test/path",
            })

            # Verify result
            assert result["status"] == "ok"
            assert daemon.session_call_id == "new-call-id"
            assert daemon.trace_id == "new-trace-id"

            # Verify create_session_call was called with continuation parameters
            daemon.processor.create_session_call.assert_called_once()
            call_kwargs = daemon.processor.create_session_call.call_args.kwargs
            # Display name should start with "Continued: " and be generated from the new prompt
            assert call_kwargs["display_name"].startswith("Continued: ")
            assert call_kwargs["continuation_of"] == "old-call-id"

            # Verify state was updated
            with StateManager() as state:
                session_data = state.get_session("test-continuation-session")
                assert session_data["session_call_id"] == "new-call-id"
                assert session_data["session_ended"] is False
                assert session_data["continuation_count"] == 1
                # display_name should not be stored in state anymore
                assert "display_name" not in session_data or session_data.get("display_name") is None
                state.delete_session("test-continuation-session")


class TestHandleUserMessage:
    """Test _handle_user_message method - critical for turn creation."""

    @pytest.mark.anyio
    async def test_creates_turn_call_for_user_text(self):
        """User message with text should create a turn call."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.processor = MagicMock()
        mock_turn_call = MagicMock()
        mock_turn_call.id = "turn-456"
        daemon.processor.create_turn_call.return_value = mock_turn_call

        obj = {
            "type": "user",
            "message": {"role": "user", "content": "Help me write a function"},
            "timestamp": "2025-01-01T10:00:00Z",
        }

        await daemon._handle_user_message(obj, line_num=1)

        assert daemon.turn_number == 1
        assert daemon.current_turn_call_id == "turn-456"
        daemon.processor.create_turn_call.assert_called_once()

    @pytest.mark.anyio
    async def test_skips_empty_content(self):
        """User message with empty text should not create a turn."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"
        daemon.processor = MagicMock()

        obj = {
            "type": "user",
            "message": {"role": "user", "content": ""},
        }

        await daemon._handle_user_message(obj, line_num=1)

        assert daemon.turn_number == 0
        daemon.processor.create_turn_call.assert_not_called()

    @pytest.mark.anyio
    async def test_skips_system_messages(self):
        """System messages (Caveat:, XML tags) should not create turns."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"
        daemon.processor = MagicMock()

        obj = {
            "type": "user",
            "message": {"role": "user", "content": "Caveat: This is a system note"},
        }

        await daemon._handle_user_message(obj, line_num=1)

        assert daemon.turn_number == 0
        daemon.processor.create_turn_call.assert_not_called()

    @pytest.mark.anyio
    async def test_detects_compaction_message(self):
        """Compaction messages should increment compaction count."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.processor = MagicMock()
        mock_turn_call = MagicMock()
        mock_turn_call.id = "turn-456"
        daemon.processor.create_turn_call.return_value = mock_turn_call

        obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "This session is being continued from a previous conversation that ran out of context."
            },
        }

        await daemon._handle_user_message(obj, line_num=1)

        assert daemon.compaction_count == 1
        # Should still create a turn
        daemon.processor.create_turn_call.assert_called_once()

    @pytest.mark.anyio
    async def test_buffers_tool_results(self):
        """Tool results should be buffered for parallel grouping."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from datetime import datetime, timezone

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"
        daemon.processor = MagicMock()

        # Set up a pending tool call
        daemon._pending_tool_calls["tool-123"] = (
            "Read",
            {"file_path": "/tmp/test.py"},
            datetime.now(timezone.utc),
        )

        obj = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool-123", "content": "file contents"}
                ],
            },
        }

        await daemon._handle_user_message(obj, line_num=1)

        # Tool should be removed from pending and added to buffer
        assert "tool-123" not in daemon._pending_tool_calls
        assert not daemon._tool_buffer.is_empty()


class TestHandleAssistantMessage:
    """Test _handle_assistant_message method - critical for tool tracking."""

    @pytest.mark.anyio
    async def test_tracks_pending_tool_calls(self):
        """Assistant message with tool_use should track pending calls."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"

        obj = {
            "type": "assistant",
            "timestamp": "2025-01-01T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tool-789", "name": "Read", "input": {"file_path": "/tmp/test.py"}}
                ],
            },
        }

        await daemon._handle_assistant_message(obj, line_num=1)

        assert "tool-789" in daemon._pending_tool_calls
        name, inputs, _ = daemon._pending_tool_calls["tool-789"]
        assert name == "Read"
        assert inputs == {"file_path": "/tmp/test.py"}

    @pytest.mark.anyio
    async def test_detects_subagent_task(self):
        """Task with subagent_type should create tracker, not pending tool."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.session_id = "test-session"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"

        obj = {
            "type": "assistant",
            "timestamp": "2025-01-01T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "task-123",
                        "name": "Task",
                        "input": {"prompt": "Do something", "subagent_type": "Explore"},
                    }
                ],
            },
        }

        await daemon._handle_assistant_message(obj, line_num=1)

        # Should NOT be in pending tool calls
        assert "task-123" not in daemon._pending_tool_calls
        # Should be tracked as subagent
        assert "task-123" in daemon._subagent_trackers
        tracker = daemon._subagent_trackers["task-123"]
        assert tracker.subagent_type == "Explore"

    @pytest.mark.anyio
    async def test_handles_enter_plan_mode(self):
        """EnterPlanMode tool should create pending inline parent."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"

        obj = {
            "type": "assistant",
            "timestamp": "2025-01-01T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "plan-123", "name": "EnterPlanMode", "input": {}}
                ],
            },
        }

        await daemon._handle_assistant_message(obj, line_num=1)

        assert daemon._pending_inline_parent is not None
        assert daemon._pending_inline_parent.tool_use_id == "plan-123"
        assert not daemon._pending_inline_parent.is_active

    @pytest.mark.anyio
    async def test_handles_skill_tool(self):
        """Skill tool should be tracked for expansion detection."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"

        obj = {
            "type": "assistant",
            "timestamp": "2025-01-01T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "skill-123", "name": "Skill", "input": {"skill": "test-skill"}}
                ],
            },
        }

        await daemon._handle_assistant_message(obj, line_num=1)

        assert "skill-123" in daemon._pending_skill_calls
        skill_name, _ = daemon._pending_skill_calls["skill-123"]
        assert skill_name == "test-skill"

    @pytest.mark.anyio
    async def test_handles_ask_user_question(self):
        """AskUserQuestion tool should create question call."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        mock_call = MagicMock()
        mock_call.id = "question-call-456"
        daemon.weave_client.create_call.return_value = mock_call
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"

        obj = {
            "type": "assistant",
            "timestamp": "2025-01-01T10:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "question-123",
                        "name": "AskUserQuestion",
                        "input": {"questions": [{"question": "What should I do?", "options": []}]},
                    }
                ],
            },
        }

        await daemon._handle_assistant_message(obj, line_num=1)

        # Should have created a question call
        daemon.weave_client.create_call.assert_called_once()
        assert "question-123" in daemon._pending_question_calls


class TestToolBuffering:
    """Test tool result buffering for parallel grouping."""

    def test_tool_buffer_detects_parallel_calls(self):
        """Tools with close timestamps should be grouped as parallel."""
        from weave.integrations.claude_plugin.utils import ToolResultBuffer
        from datetime import datetime, timezone, timedelta

        buffer = ToolResultBuffer()
        base_time = datetime.now(timezone.utc)

        # Add tools with same timestamp (parallel)
        buffer.add("tool-1", "Read", {"file": "a.py"}, base_time, "content a", False)
        buffer.add("tool-2", "Read", {"file": "b.py"}, base_time, "content b", False)
        buffer.add("tool-3", "Read", {"file": "c.py"}, base_time + timedelta(milliseconds=100), "content c", False)

        # Force flush
        groups = buffer.get_ready_to_flush(force=True)

        # All should be in one parallel group
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_tool_buffer_separates_sequential_calls(self):
        """Tools with distant timestamps should be separate."""
        from weave.integrations.claude_plugin.utils import ToolResultBuffer
        from datetime import datetime, timezone, timedelta

        buffer = ToolResultBuffer()
        base_time = datetime.now(timezone.utc)

        # Add first tool
        buffer.add("tool-1", "Read", {"file": "a.py"}, base_time, "content a", False)

        # Add second tool 2 seconds later (beyond threshold)
        buffer.add("tool-2", "Read", {"file": "b.py"}, base_time + timedelta(seconds=2), "content b", False)

        # Force flush
        groups = buffer.get_ready_to_flush(force=True)

        # Should be two separate groups
        assert len(groups) == 2


class TestFinishCurrentTurn:
    """Test _finish_current_turn method."""

    @pytest.mark.anyio
    async def test_finish_turn_with_no_tool_calls(self, tmp_path):
        """Turn with no tool calls should still complete properly."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"
        daemon.turn_number = 1

        # Create minimal session file
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "message": {"role": "user", "content": "Hello"},
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi there!"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            }) + "\n"
        )
        daemon.transcript_path = session_file

        await daemon._finish_current_turn()

        daemon.weave_client.finish_call.assert_called_once()
        assert daemon.current_turn_call_id is None

    @pytest.mark.anyio
    async def test_finish_turn_interrupted(self, tmp_path):
        """Interrupted turn should be marked as such."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"
        daemon.turn_number = 1

        # Create minimal session file
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "message": {"role": "user", "content": "Hello"},
            }) + "\n"
        )
        daemon.transcript_path = session_file

        await daemon._finish_current_turn(interrupted=True)

        # Check that finish_call was called with interrupted info
        daemon.weave_client.finish_call.assert_called_once()
        call_args = daemon.weave_client.finish_call.call_args
        output = call_args.kwargs.get("output") or call_args[1].get("output", {})
        assert output.get("interrupted") is True


class TestLoadState:
    """Test _load_state method for restoring daemon state."""

    def test_load_state_returns_false_when_no_session(self):
        """Should return False when no session state exists."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        # Ensure no session exists
        with StateManager() as state:
            state.delete_session("nonexistent-session")

        daemon = WeaveDaemon("nonexistent-session")
        result = daemon._load_state()

        assert result is False

    def test_load_state_restores_all_fields(self, tmp_path):
        """Should restore all state fields from session data."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        session_id = "test-load-state-session"
        transcript_path = str(tmp_path / "session.jsonl")

        # Create session state
        with StateManager() as state:
            state.save_session(session_id, {
                "project": "test/project",
                "transcript_path": transcript_path,
                "last_processed_line": 42,
                "session_call_id": "call-123",
                "trace_id": "trace-456",
                "trace_url": "https://weave.wandb.ai/trace/456",
                "turn_call_id": "turn-789",
                "turn_number": 3,
                "total_tool_calls": 10,
                "tool_counts": {"Read": 5, "Edit": 3},
                "pending_question": "What do you prefer?",
                "compaction_count": 2,
            })

        try:
            daemon = WeaveDaemon(session_id)
            result = daemon._load_state()

            assert result is True
            assert daemon.project == "test/project"
            assert daemon.transcript_path == Path(transcript_path)
            assert daemon.last_processed_line == 42
            assert daemon.session_call_id == "call-123"
            assert daemon.trace_id == "trace-456"
            assert daemon.trace_url == "https://weave.wandb.ai/trace/456"
            assert daemon.current_turn_call_id == "turn-789"
            assert daemon.turn_number == 3
            assert daemon.total_tool_calls == 10
            assert daemon.tool_counts == {"Read": 5, "Edit": 3}
            assert daemon._pending_question == "What do you prefer?"
            assert daemon.compaction_count == 2
        finally:
            with StateManager() as state:
                state.delete_session(session_id)


class TestSaveState:
    """Test _save_state method for persisting daemon state."""

    def test_save_state_persists_all_fields(self, tmp_path):
        """Should persist all daemon state fields."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        session_id = "test-save-state-session"

        # Create initial session state
        with StateManager() as state:
            state.save_session(session_id, {"project": "test/project"})

        try:
            daemon = WeaveDaemon(session_id)
            daemon.session_call_id = "session-call-abc"
            daemon.trace_id = "trace-xyz"
            daemon.trace_url = "https://weave.wandb.ai/trace/xyz"
            daemon.current_turn_call_id = "turn-123"
            daemon.turn_number = 5
            daemon.total_tool_calls = 15
            daemon.tool_counts = {"Bash": 8, "Read": 7}
            daemon.last_processed_line = 100
            daemon._pending_question = "Which option?"
            daemon.compaction_count = 3

            daemon._save_state()

            # Verify state was saved
            with StateManager() as state:
                saved = state.get_session(session_id)

            assert saved["session_call_id"] == "session-call-abc"
            assert saved["trace_id"] == "trace-xyz"
            assert saved["trace_url"] == "https://weave.wandb.ai/trace/xyz"
            assert saved["turn_call_id"] == "turn-123"
            assert saved["turn_number"] == 5
            assert saved["total_tool_calls"] == 15
            assert saved["tool_counts"] == {"Bash": 8, "Read": 7}
            assert saved["last_processed_line"] == 100
            assert saved["pending_question"] == "Which option?"
            assert saved["compaction_count"] == 3
        finally:
            with StateManager() as state:
                state.delete_session(session_id)


class TestGetSessionsDirectory:
    """Test _get_sessions_directory helper method."""

    def test_returns_none_when_no_transcript_path(self):
        """Should return None when transcript_path is not set."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.transcript_path = None

        result = daemon._get_sessions_directory()
        assert result is None

    def test_returns_parent_directory(self, tmp_path):
        """Should return the parent directory of transcript_path."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.transcript_path = tmp_path / "sessions" / "session.jsonl"

        result = daemon._get_sessions_directory()
        assert result == tmp_path / "sessions"


class TestHandleSessionStart:
    """Test _handle_session_start async handler."""

    @pytest.mark.anyio
    async def test_updates_transcript_path(self, tmp_path):
        """Should update transcript_path from payload."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.trace_url = "https://example.com/trace"

        transcript_path = str(tmp_path / "session.jsonl")
        payload = {"transcript_path": transcript_path}

        result = await daemon._handle_session_start(payload)

        assert result["status"] == "ok"
        assert daemon.transcript_path == Path(transcript_path)
        assert result["trace_url"] == "https://example.com/trace"
        assert result["session_id"] == "test-session"

    @pytest.mark.anyio
    async def test_returns_ok_without_transcript_path(self):
        """Should return ok even without transcript_path in payload."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        payload = {}

        result = await daemon._handle_session_start(payload)

        assert result["status"] == "ok"


class TestHandleStop:
    """Test _handle_stop async handler."""

    @pytest.mark.anyio
    async def test_finishes_current_turn(self, tmp_path):
        """Should finish current turn when Stop is received."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.current_turn_call_id = "turn-456"
        daemon.turn_number = 1

        # Create minimal transcript
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "message": {"role": "user", "content": "Hello"},
            }) + "\n"
        )
        daemon.transcript_path = session_file

        with patch.object(daemon, "_save_state"):
            result = await daemon._handle_stop({})

        assert result["status"] == "ok"
        # Turn should be finished
        daemon.weave_client.finish_call.assert_called()

    @pytest.mark.anyio
    async def test_flushes_buffered_tool_results(self):
        """Should flush buffered tool results on Stop."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.transcript_path = None  # No file to process

        # Add a mock tool buffer
        daemon._tool_buffer = MagicMock()

        with patch.object(daemon, "_save_state"):
            with patch.object(daemon, "_flush_buffered_tool_results") as mock_flush:
                result = await daemon._handle_stop({})

                mock_flush.assert_called_once_with(force=True)
                assert result["status"] == "ok"


class TestHandleFeedback:
    """Test _handle_feedback async handler."""

    @pytest.mark.anyio
    async def test_returns_error_without_session(self):
        """Should return error when no active session."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = None
        daemon.session_call_id = None

        result = await daemon._handle_feedback({"emoji": "👍"})

        assert result["status"] == "error"
        assert "no active session" in result["message"].lower()

    @pytest.mark.anyio
    async def test_adds_emoji_reaction(self):
        """Should add emoji reaction to session call."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"

        mock_call = MagicMock()
        mock_call.feedback = MagicMock()
        daemon.weave_client.get_call.return_value = mock_call

        result = await daemon._handle_feedback({"emoji": "🎉"})

        assert result["status"] == "ok"
        mock_call.feedback.add_reaction.assert_called_once_with("🎉", creator="user")

    @pytest.mark.anyio
    async def test_adds_note(self):
        """Should add note to session call."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"

        mock_call = MagicMock()
        mock_call.feedback = MagicMock()
        daemon.weave_client.get_call.return_value = mock_call

        result = await daemon._handle_feedback({"note": "Great session!"})

        assert result["status"] == "ok"
        mock_call.feedback.add_note.assert_called_once_with("Great session!", creator="user")

    @pytest.mark.anyio
    async def test_adds_both_emoji_and_note(self):
        """Should add both emoji and note when provided."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"

        mock_call = MagicMock()
        mock_call.feedback = MagicMock()
        daemon.weave_client.get_call.return_value = mock_call

        result = await daemon._handle_feedback({"emoji": "👍", "note": "Helpful"})

        assert result["status"] == "ok"
        mock_call.feedback.add_reaction.assert_called_once_with("👍", creator="user")
        mock_call.feedback.add_note.assert_called_once_with("Helpful", creator="user")

    @pytest.mark.anyio
    @pytest.mark.disable_logging_error_check
    async def test_handles_feedback_error(self):
        """Should return error when feedback fails."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"
        daemon.weave_client.get_call.side_effect = Exception("API error")

        result = await daemon._handle_feedback({"emoji": "👍"})

        assert result["status"] == "error"
        assert "API error" in result["message"]


class TestHandleSessionEnd:
    """Test _handle_session_end async handler."""

    @pytest.mark.anyio
    async def test_finishes_session_call(self):
        """Should finish session call on SessionEnd."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.transcript_path = None  # No file to process

        with patch.object(daemon, "_save_state"):
            result = await daemon._handle_session_end({})

        assert result["status"] == "ok"
        assert daemon.running is False  # Should trigger shutdown
        daemon.weave_client.finish_call.assert_called()

    @pytest.mark.anyio
    async def test_saves_session_ended_flag(self, tmp_path):
        """Should save session_ended flag in state."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon
        from weave.integrations.claude_plugin.core.state import StateManager

        session_id = "test-session-end-flag"
        daemon = WeaveDaemon(session_id)
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.transcript_path = None

        # Create initial state
        with StateManager() as state:
            state.save_session(session_id, {"project": "test/project"})

        try:
            result = await daemon._handle_session_end({})

            assert result["status"] == "ok"

            # Check that session_ended flag was set
            with StateManager() as state:
                session_data = state.get_session(session_id)
                assert session_data.get("session_ended") is True
        finally:
            with StateManager() as state:
                state.delete_session(session_id)


class TestProcessSessionFile:
    """Test _process_session_file async method."""

    @pytest.mark.anyio
    async def test_processes_user_and_assistant_messages(self, tmp_path):
        """Should process user and assistant messages from file."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.last_processed_line = 0

        # Create session file with user and assistant messages
        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Hello"},
            }) + "\n" +
            json.dumps({
                "type": "assistant",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "sessionId": "test-session",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi!"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            }) + "\n"
        )
        daemon.transcript_path = session_file

        with patch.object(daemon, "_save_state"):
            with patch.object(daemon, "_handle_user_message") as mock_user:
                with patch.object(daemon, "_handle_assistant_message") as mock_assistant:
                    mock_user.return_value = None
                    mock_assistant.return_value = None
                    await daemon._process_session_file()

        # Should have processed 2 lines
        assert daemon.last_processed_line == 2
        # Handlers should have been called
        mock_user.assert_called_once()
        mock_assistant.assert_called_once()

    @pytest.mark.anyio
    async def test_returns_early_without_transcript_path(self):
        """Should return early when no transcript path."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.transcript_path = None
        daemon.last_processed_line = 0

        await daemon._process_session_file()

        # Should not error, just return
        assert daemon.last_processed_line == 0

    @pytest.mark.anyio
    async def test_skips_already_processed_lines(self, tmp_path):
        """Should skip already processed lines."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.weave_client._project_id.return_value = "test-project"
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.last_processed_line = 1  # Already processed first line

        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "First"},
            }) + "\n" +
            json.dumps({
                "type": "user",
                "uuid": "msg-2",
                "timestamp": "2025-01-01T10:00:01Z",
                "sessionId": "test-session",
                "message": {"role": "user", "content": "Second"},
            }) + "\n"
        )
        daemon.transcript_path = session_file

        with patch.object(daemon, "_save_state"):
            with patch.object(daemon, "_handle_user_message") as mock_handler:
                mock_handler.return_value = None
                await daemon._process_session_file()

        # Should only process line 2 (skip line 1)
        assert daemon.last_processed_line == 2
        # Handler should be called once (only for line 2)
        mock_handler.assert_called_once()

    @pytest.mark.anyio
    async def test_handles_invalid_json_gracefully(self, tmp_path):
        """Should skip invalid JSON lines gracefully."""
        from weave.integrations.claude_plugin.core.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session")
        daemon.weave_client = MagicMock()
        daemon.session_call_id = "session-123"
        daemon.trace_id = "trace-abc"
        daemon.last_processed_line = 0

        session_file = tmp_path / "session.jsonl"
        session_file.write_text(
            "not valid json\n" +
            json.dumps({
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "message": {"role": "user", "content": "Hello"},
            }) + "\n"
        )
        daemon.transcript_path = session_file

        with patch.object(daemon, "_save_state"):
            # Should not raise
            await daemon._process_session_file()

        # Should have processed 2 lines (even though first was invalid)
        assert daemon.last_processed_line == 2
