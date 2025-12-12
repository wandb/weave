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
        from weave.integrations.claude_plugin.socket_client import get_socket_path

        path = get_socket_path("test-session-123")
        assert path.name == "daemon-test-session-123.sock"
        assert ".cache/weave" in str(path)

    def test_daemon_client_not_running(self):
        """Test daemon client detects when daemon is not running."""
        from weave.integrations.claude_plugin.socket_client import DaemonClient

        client = DaemonClient("nonexistent-session")
        assert not client.is_daemon_running()

    def test_state_manager_with_new_fields(self):
        """Test state manager handles new daemon fields."""
        from weave.integrations.claude_plugin.state import (
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
        from weave.integrations.claude_plugin.socket_client import DaemonClient

        # Create a fake socket file
        with patch(
            "weave.integrations.claude_plugin.socket_client.SOCKET_DIR",
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

        from weave.integrations.claude_plugin.socket_client import DaemonClient

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

        from weave.integrations.claude_plugin.daemon import SubagentTracker

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

        from weave.integrations.claude_plugin.daemon import SubagentTracker

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
        from weave.integrations.claude_plugin.daemon import WeaveDaemon

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
        from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker

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

        from weave.integrations.claude_plugin.daemon import WeaveDaemon

        daemon = WeaveDaemon("test-session-123")
        daemon.transcript_path = Path("/Users/test/.claude/projects/abc123/session-xyz.jsonl")

        sessions_dir = daemon._get_sessions_directory()

        assert sessions_dir == Path("/Users/test/.claude/projects/abc123")

    def test_daemon_get_sessions_directory_none_when_no_transcript(self):
        """WeaveDaemon returns None when no transcript path set."""
        from weave.integrations.claude_plugin.daemon import WeaveDaemon

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

        from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker

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

        from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker

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

        from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker
        from weave.integrations.claude_plugin.session_parser import Session

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

        from weave.integrations.claude_plugin.daemon import WeaveDaemon, SubagentTracker

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
            "type": "tool_result",
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
        with patch("weave.integrations.claude_plugin.daemon.weave.log_call", side_effect=mock_log_call):
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
