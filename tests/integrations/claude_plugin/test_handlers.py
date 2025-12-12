"""Tests for Claude Code hook handlers."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from weave.type_wrappers.Content.content import Content


# Small 1x1 red PNG image as base64
TINY_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


def create_session_jsonl(messages: list[dict], filename: str | None = None) -> Path:
    """Create a temporary JSONL session file from message dicts.

    Args:
        messages: List of message dicts to write
        filename: Optional custom filename (useful for agent-*.jsonl files)
    """
    if filename:
        # Create in temp dir with specific filename
        tmp_dir = tempfile.mkdtemp()
        path = Path(tmp_dir) / filename
        with open(path, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")
        return path
    else:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for msg in messages:
            tmp.write(json.dumps(msg) + "\n")
        tmp.close()
        return Path(tmp.name)


class TestHandlerImageExtraction:
    """Tests for extracting images in handlers.

    Note: These tests are for the legacy handlers.py architecture.
    The new daemon architecture (daemon.py) handles image extraction
    by tailing the session file, which correctly captures images
    after they appear in the transcript.
    """

    @pytest.mark.skip(reason="Legacy handlers.py replaced by daemon architecture - images now captured by daemon.py")
    def test_turn_inputs_include_images_from_transcript(self):
        """Turn inputs should include images extracted from the transcript."""
        # Create a session file with an image in the user message
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session-123",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image?"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": TINY_PNG_BASE64,
                            },
                        },
                    ],
                },
            },
        ])

        try:
            # Mock the weave client and state
            mock_client = MagicMock()
            mock_client.entity = "test-entity"
            mock_client._project_id.return_value = "test-entity/test-project"

            mock_session_call = MagicMock()
            mock_session_call.id = "session-call-id"
            mock_session_call.trace_id = "trace-id"
            mock_session_call.ui_url = "https://wandb.ai/test/r/call/session-call-id"

            mock_turn_call = MagicMock()
            mock_turn_call.id = "turn-call-id"

            mock_client.create_call.side_effect = [mock_session_call, mock_turn_call]

            # Import and call the handler
            with patch("weave.integrations.claude_plugin.handlers.weave") as mock_weave, \
                 patch("weave.integrations.claude_plugin.handlers.require_weave_client") as mock_require_client, \
                 patch("weave.integrations.claude_plugin.handlers.StateManager") as mock_state_manager:

                mock_weave.init = MagicMock()
                mock_require_client.return_value = mock_client

                # Setup state manager mock
                mock_state = MagicMock()
                mock_state.get_session.return_value = None  # First call, no existing state
                mock_state_manager.return_value.__enter__ = MagicMock(return_value=mock_state)
                mock_state_manager.return_value.__exit__ = MagicMock(return_value=False)

                from weave.integrations.claude_plugin.handlers import handle_user_prompt_submit

                payload = {
                    "session_id": "test-session-123",
                    "transcript_path": str(session_jsonl),
                    "prompt": "What's in this image?",
                    "cwd": "/test/dir",
                }

                result = handle_user_prompt_submit(payload, "test-entity/test-project")

            # Verify the turn call was created with images in inputs
            turn_call_args = mock_client.create_call.call_args_list[1]
            turn_inputs = turn_call_args.kwargs.get("inputs", {})

            # The turn inputs should have images
            assert "images" in turn_inputs, "Turn inputs should include 'images' key"
            assert len(turn_inputs["images"]) == 1, "Should have one image"
            assert isinstance(turn_inputs["images"][0], Content), "Image should be a Content object"
            assert turn_inputs["images"][0].mimetype == "image/png"

        finally:
            session_jsonl.unlink()

    @pytest.mark.skip(reason="Legacy handlers.py replaced by daemon architecture - images now captured by daemon.py")
    def test_turn_inputs_empty_images_when_no_images_in_transcript(self):
        """Turn inputs should have empty images list when transcript has no images."""
        session_jsonl = create_session_jsonl([
            {
                "type": "user",
                "uuid": "msg-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "sessionId": "test-session-456",
                "message": {
                    "role": "user",
                    "content": "Just a text message",
                },
            },
        ])

        try:
            mock_client = MagicMock()
            mock_client.entity = "test-entity"
            mock_client._project_id.return_value = "test-entity/test-project"

            mock_session_call = MagicMock()
            mock_session_call.id = "session-call-id"
            mock_session_call.trace_id = "trace-id"
            mock_session_call.ui_url = "https://wandb.ai/test/r/call/session-call-id"

            mock_turn_call = MagicMock()
            mock_turn_call.id = "turn-call-id"

            mock_client.create_call.side_effect = [mock_session_call, mock_turn_call]

            with patch("weave.integrations.claude_plugin.handlers.weave") as mock_weave, \
                 patch("weave.integrations.claude_plugin.handlers.require_weave_client") as mock_require_client, \
                 patch("weave.integrations.claude_plugin.handlers.StateManager") as mock_state_manager:

                mock_weave.init = MagicMock()
                mock_require_client.return_value = mock_client

                mock_state = MagicMock()
                mock_state.get_session.return_value = None
                mock_state_manager.return_value.__enter__ = MagicMock(return_value=mock_state)
                mock_state_manager.return_value.__exit__ = MagicMock(return_value=False)

                from weave.integrations.claude_plugin.handlers import handle_user_prompt_submit

                payload = {
                    "session_id": "test-session-456",
                    "transcript_path": str(session_jsonl),
                    "prompt": "Just a text message",
                    "cwd": "/test/dir",
                }

                result = handle_user_prompt_submit(payload, "test-entity/test-project")

            turn_call_args = mock_client.create_call.call_args_list[1]
            turn_inputs = turn_call_args.kwargs.get("inputs", {})

            # Should have images key but empty list
            assert "images" in turn_inputs, "Turn inputs should include 'images' key"
            assert turn_inputs["images"] == [], "Images should be empty list"

        finally:
            session_jsonl.unlink()


class TestSubagentStopHandler:
    """Tests for SubagentStop hook handler."""

    def test_subagent_stop_creates_trace_under_parent_session(self):
        """SubagentStop should create a subagent trace as child of parent session."""
        parent_session_id = "parent-session-uuid"
        agent_id = "abc12345"

        # Create an agent session file with the parent session reference
        agent_jsonl = create_session_jsonl(
            [
                {
                    "type": "assistant",
                    "uuid": "agent-msg-1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "sessionId": parent_session_id,  # Points to parent
                    "agentId": agent_id,
                    "isSidechain": True,
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [
                            {"type": "text", "text": "I'll search the codebase."},
                            {
                                "type": "tool_use",
                                "id": "tool-1",
                                "name": "Grep",
                                "input": {"pattern": "TODO", "path": "/src"},
                            },
                        ],
                        "usage": {"input_tokens": 100, "output_tokens": 50},
                    },
                },
                {
                    "type": "user",
                    "uuid": "agent-msg-2",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "sessionId": parent_session_id,
                    "agentId": agent_id,
                    "isSidechain": True,
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "tool-1",
                                "content": "Found 3 TODOs",
                            }
                        ],
                    },
                },
                {
                    "type": "assistant",
                    "uuid": "agent-msg-3",
                    "timestamp": "2025-01-01T10:00:02Z",
                    "sessionId": parent_session_id,
                    "agentId": agent_id,
                    "isSidechain": True,
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Found 3 TODOs in the codebase."}],
                        "usage": {"input_tokens": 50, "output_tokens": 20},
                    },
                },
            ],
            filename=f"agent-{agent_id}.jsonl",
        )

        try:
            mock_client = MagicMock()
            mock_client.entity = "test-entity"
            mock_client._project_id.return_value = "test-entity/test-project"

            mock_subagent_call = MagicMock()
            mock_subagent_call.id = "subagent-call-id"

            mock_client.create_call.return_value = mock_subagent_call

            with patch("weave.integrations.claude_plugin.handlers.weave") as mock_weave, \
                 patch("weave.integrations.claude_plugin.handlers.require_weave_client") as mock_require_client, \
                 patch("weave.integrations.claude_plugin.handlers.StateManager") as mock_state_manager:

                mock_weave.init = MagicMock()
                mock_weave.log_call = MagicMock()
                mock_require_client.return_value = mock_client

                # Parent session state exists
                mock_state = MagicMock()
                mock_state.get_session.return_value = {
                    "session_call_id": "parent-session-call-id",
                    "trace_id": "parent-trace-id",
                    "entity": "test-entity",
                    "project": "test-entity/test-project",
                }
                mock_state_manager.return_value.__enter__ = MagicMock(return_value=mock_state)
                mock_state_manager.return_value.__exit__ = MagicMock(return_value=False)

                from weave.integrations.claude_plugin.handlers import handle_subagent_stop

                payload = {
                    "session_id": parent_session_id,
                    "transcript_path": str(agent_jsonl),
                    "hook_event_name": "SubagentStop",
                }

                result = handle_subagent_stop(payload, "test-entity/test-project")

            # Verify a subagent call was created
            assert mock_client.create_call.called, "Should create a call for the subagent"

            # Check the subagent call was created with correct parent linkage
            subagent_call_args = mock_client.create_call.call_args
            assert subagent_call_args.kwargs.get("op") == "claude_code.subagent"

            # Verify tool calls were logged
            assert mock_weave.log_call.called, "Should log tool calls from the subagent"

        finally:
            agent_jsonl.unlink()
            agent_jsonl.parent.rmdir()

    def test_subagent_stop_without_parent_state_logs_warning(self):
        """SubagentStop with no parent session state should log warning and return."""
        parent_session_id = "unknown-parent-session"
        agent_id = "xyz98765"

        agent_jsonl = create_session_jsonl(
            [
                {
                    "type": "assistant",
                    "uuid": "agent-msg-1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "sessionId": parent_session_id,
                    "agentId": agent_id,
                    "isSidechain": True,
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4-20250514",
                        "content": [{"type": "text", "text": "Test message."}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    },
                },
            ],
            filename=f"agent-{agent_id}.jsonl",
        )

        try:
            mock_client = MagicMock()

            with patch("weave.integrations.claude_plugin.handlers.weave") as mock_weave, \
                 patch("weave.integrations.claude_plugin.handlers.require_weave_client") as mock_require_client, \
                 patch("weave.integrations.claude_plugin.handlers.StateManager") as mock_state_manager:

                mock_weave.init = MagicMock()
                mock_require_client.return_value = mock_client

                # Parent session state does NOT exist
                mock_state = MagicMock()
                mock_state.get_session.return_value = None
                mock_state_manager.return_value.__enter__ = MagicMock(return_value=mock_state)
                mock_state_manager.return_value.__exit__ = MagicMock(return_value=False)

                from weave.integrations.claude_plugin.handlers import handle_subagent_stop

                payload = {
                    "session_id": parent_session_id,
                    "transcript_path": str(agent_jsonl),
                    "hook_event_name": "SubagentStop",
                }

                result = handle_subagent_stop(payload, "test-entity/test-project")

            # Should not create any calls when parent state is missing
            assert not mock_client.create_call.called, "Should not create calls without parent state"
            assert result is None

        finally:
            agent_jsonl.unlink()
            agent_jsonl.parent.rmdir()
