"""Tests for diff_view fallback functions."""

import pytest


class TestBuildFileDiffsFromEditData:
    """Test _build_file_diffs_from_edit_data function."""

    def test_converts_edit_data_to_file_diffs_format(self):
        """Verify Edit tool data is converted to file_diffs format."""
        from weave.integrations.claude_plugin.views.diff_view import (
            _build_file_diffs_from_edit_data,
        )

        edit_data = [
            {
                "file_path": "test.py",
                "original_file": "print('hello')\n",
                "structured_patch": [
                    {
                        "oldStart": 1,
                        "oldLines": 1,
                        "newStart": 1,
                        "newLines": 1,
                        "lines": ["-print('hello')", "+print('world')"],
                    }
                ],
            }
        ]

        result = _build_file_diffs_from_edit_data(edit_data)

        assert len(result) == 1
        assert result[0]["path"] == "test.py"
        assert result[0]["lang"] == "python"
        assert result[0]["added"] == 1
        assert result[0]["removed"] == 1
        assert "diff_lines" in result[0]

    def test_aggregates_multiple_edits_to_same_file(self):
        """Verify multiple edits to same file are aggregated."""
        from weave.integrations.claude_plugin.views.diff_view import (
            _build_file_diffs_from_edit_data,
        )

        edit_data = [
            {
                "file_path": "test.py",
                "original_file": "a = 1\nb = 2\n",
                "structured_patch": [
                    {
                        "oldStart": 1,
                        "oldLines": 1,
                        "newStart": 1,
                        "newLines": 1,
                        "lines": ["-a = 1", "+a = 10"],
                    }
                ],
            },
            {
                "file_path": "test.py",
                "original_file": "a = 10\nb = 2\n",  # After first edit
                "structured_patch": [
                    {
                        "oldStart": 2,
                        "oldLines": 1,
                        "newStart": 2,
                        "newLines": 1,
                        "lines": ["-b = 2", "+b = 20"],
                    }
                ],
            },
        ]

        result = _build_file_diffs_from_edit_data(edit_data)

        # Should have one entry for the file
        assert len(result) == 1
        assert result[0]["path"] == "test.py"


class TestGenerateDiffHtmlFromEditDataForTurn:
    """Test generate_diff_html_from_edit_data_for_turn function."""

    def test_returns_none_when_no_raw_messages(self):
        """Verify None is returned when turn has no raw_messages."""
        from weave.integrations.claude_plugin.views.diff_view import (
            generate_diff_html_from_edit_data_for_turn,
        )
        from unittest.mock import MagicMock

        mock_turn = MagicMock()
        mock_turn.raw_messages = None

        result = generate_diff_html_from_edit_data_for_turn(
            turn=mock_turn,
            turn_number=1,
        )

        assert result is None

    def test_uses_diff_html_styles(self):
        """Verify output uses DIFF_HTML_STYLES (not ugly inline styles)."""
        from weave.integrations.claude_plugin.views.diff_view import (
            generate_diff_html_from_edit_data_for_turn,
            DIFF_HTML_STYLES,
        )
        from unittest.mock import MagicMock

        mock_turn = MagicMock()
        mock_turn.raw_messages = [
            {
                "toolUseResult": {
                    "filePath": "test.py",
                    "originalFile": "x = 1\n",
                    "structuredPatch": [
                        {
                            "oldStart": 1,
                            "oldLines": 1,
                            "newStart": 1,
                            "newLines": 1,
                            "lines": ["-x = 1", "+x = 2"],
                        }
                    ],
                }
            }
        ]
        mock_turn.all_tool_calls.return_value = []
        mock_turn.primary_model.return_value = "claude-3"

        result = generate_diff_html_from_edit_data_for_turn(
            turn=mock_turn,
            turn_number=1,
        )

        assert result is not None
        # Should use proper CSS, not inline styles
        assert "diff-view" in result
        assert 'style="background: #ffdddd"' not in result  # Ugly inline style
        assert "<!DOCTYPE html>" in result  # Full document


class TestGenerateSessionDiffHtmlWithEditDataFallback:
    """Test generate_session_diff_html Edit data fallback.

    When file-history backups are unavailable (e.g., edits made by subagents),
    the function should fall back to extracting Edit tool data from raw_messages.
    """

    def test_returns_html_when_subagent_has_edit_data_but_no_backups(self):
        """Verify session diff is generated from subagent Edit data when no backups exist."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import MagicMock
        import json

        from weave.integrations.claude_plugin.views.diff_view import generate_session_diff_html

        with TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)

            # Create main session with no file_backups
            main_session = MagicMock()
            main_session.session_id = "test-session-123"
            main_session.turns = [MagicMock()]
            main_session.turns[0].file_backups = []  # No file-history backups
            main_session.turns[0].raw_messages = []  # No Edit calls in main session

            # Create subagent session file with Edit tool data
            # Note: subagent sessionId must match parent session for filtering
            agent_data = [
                {
                    "type": "user",
                    "uuid": "u1",
                    "timestamp": "2025-01-01T10:00:00Z",
                    "sessionId": "test-session-123",  # Same as parent session
                    "message": {"role": "user", "content": "Fix the bug"},
                },
                {
                    "type": "assistant",
                    "uuid": "a1",
                    "timestamp": "2025-01-01T10:00:01Z",
                    "toolUseResult": {
                        "filePath": "/path/to/file.py",
                        "originalFile": "def foo():\n    return 1\n",
                        "structuredPatch": [
                            {
                                "oldStart": 2,
                                "oldLines": 1,
                                "newStart": 2,
                                "newLines": 1,
                                "lines": ["-    return 1", "+    return 42"],
                            }
                        ],
                    },
                    "message": {
                        "role": "assistant",
                        "model": "claude-sonnet-4",
                        "content": [{"type": "text", "text": "Fixed"}],
                        "usage": {"input_tokens": 100, "output_tokens": 10},
                    },
                },
            ]

            agent_file = sessions_dir / "agent-abc123.jsonl"
            with open(agent_file, "w") as f:
                for msg in agent_data:
                    f.write(json.dumps(msg) + "\n")

            # Generate session diff
            result = generate_session_diff_html(
                main_session,
                cwd="/path/to",
                sessions_dir=sessions_dir,
                project="test/project",
            )

            # Should have generated HTML from subagent Edit data
            assert result is not None
            assert "Session File Changes" in result
            # Path should be relative to cwd (/path/to -> file.py)
            assert "file.py" in result
            assert "diff-view" in result

    def test_returns_none_when_no_backups_and_no_edit_data(self):
        """Verify None is returned when neither backups nor Edit data exist."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import MagicMock

        from weave.integrations.claude_plugin.views.diff_view import generate_session_diff_html

        with TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)

            # Create main session with no file_backups and no Edit calls
            main_session = MagicMock()
            main_session.session_id = "test-session-456"
            main_session.turns = [MagicMock()]
            main_session.turns[0].file_backups = []
            main_session.turns[0].raw_messages = []

            # No subagent files

            result = generate_session_diff_html(
                main_session,
                cwd="/path/to",
                sessions_dir=sessions_dir,
                project="test/project",
            )

            assert result is None

    def test_aggregates_edit_data_from_multiple_subagents(self):
        """Verify Edit data is collected from all subagent sessions."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import MagicMock
        import json

        from weave.integrations.claude_plugin.views.diff_view import generate_session_diff_html

        with TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir)

            main_session = MagicMock()
            main_session.session_id = "test-session-789"
            main_session.turns = [MagicMock()]
            main_session.turns[0].file_backups = []
            main_session.turns[0].raw_messages = []

            # Create two subagent files with different edits
            # Note: subagent sessionId must match parent session for filtering
            for agent_id, file_path in [("abc", "file_a.py"), ("def", "file_b.py")]:
                agent_data = [
                    {
                        "type": "user",
                        "uuid": "u1",
                        "timestamp": "2025-01-01T10:00:00Z",
                        "sessionId": "test-session-789",  # Same as parent session
                        "message": {"role": "user", "content": "Edit"},
                    },
                    {
                        "type": "assistant",
                        "uuid": "a1",
                        "timestamp": "2025-01-01T10:00:01Z",
                        "toolUseResult": {
                            "filePath": f"/path/to/{file_path}",
                            "originalFile": "x = 1\n",
                            "structuredPatch": [
                                {
                                    "oldStart": 1,
                                    "oldLines": 1,
                                    "newStart": 1,
                                    "newLines": 1,
                                    "lines": ["-x = 1", "+x = 99"],
                                }
                            ],
                        },
                        "message": {
                            "role": "assistant",
                            "model": "claude-sonnet-4",
                            "content": [{"type": "text", "text": "Done"}],
                            "usage": {"input_tokens": 50, "output_tokens": 5},
                        },
                    },
                ]
                agent_file = sessions_dir / f"agent-{agent_id}.jsonl"
                with open(agent_file, "w") as f:
                    for msg in agent_data:
                        f.write(json.dumps(msg) + "\n")

            result = generate_session_diff_html(
                main_session,
                cwd="/path/to",
                sessions_dir=sessions_dir,
                project="test/project",
            )

            assert result is not None
            # Should contain diffs from both subagents
            assert "file_a.py" in result
            assert "file_b.py" in result
