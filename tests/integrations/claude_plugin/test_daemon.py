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
