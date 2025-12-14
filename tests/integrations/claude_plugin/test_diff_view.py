"""Tests for diff_view fallback functions."""

import pytest


class TestBuildFileDiffsFromEditData:
    """Test _build_file_diffs_from_edit_data function."""

    def test_converts_edit_data_to_file_diffs_format(self):
        """Verify Edit tool data is converted to file_diffs format."""
        from weave.integrations.claude_plugin.diff_view import (
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
        from weave.integrations.claude_plugin.diff_view import (
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
        from weave.integrations.claude_plugin.diff_view import (
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
        from weave.integrations.claude_plugin.diff_view import (
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
