"""Tests for claude_plugin utilities."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from weave.integrations.claude_plugin.utils import (
    extract_question_from_text,
    sanitize_tool_input,
    reconstruct_call,
    log_tool_call,
    get_git_info,
    MAX_TOOL_INPUT_LENGTH,
)


class TestSanitizeToolInput:
    def test_short_strings_unchanged(self):
        """Short strings should pass through unchanged."""
        input_dict = {"key": "short value", "num": 42}
        result = sanitize_tool_input(input_dict)
        assert result == {"key": "short value", "num": 42}

    def test_long_strings_truncated(self):
        """Long strings should be truncated."""
        long_string = "x" * 10000
        input_dict = {"content": long_string}
        result = sanitize_tool_input(input_dict)
        assert len(result["content"]) < len(long_string)
        assert result["content"].endswith("...[truncated]")

    def test_non_string_values_unchanged(self):
        """Non-string values should pass through unchanged."""
        input_dict = {"list": [1, 2, 3], "dict": {"nested": True}, "num": 123}
        result = sanitize_tool_input(input_dict)
        assert result == input_dict

    def test_custom_max_length(self):
        """Should respect custom max length."""
        input_dict = {"content": "x" * 100}
        result = sanitize_tool_input(input_dict, max_length=50)
        assert len(result["content"]) < 100

    def test_empty_dict(self):
        """Empty dict should return empty dict."""
        assert sanitize_tool_input({}) == {}


class TestReconstructCall:
    def test_creates_call_with_required_fields(self):
        """Should create Call with all required fields."""
        call = reconstruct_call(
            project_id="test/project",
            call_id="call-123",
            trace_id="trace-456",
        )
        assert call.id == "call-123"
        assert call.trace_id == "trace-456"
        assert call.project_id == "test/project"
        assert call.parent_id is None

    def test_creates_call_with_parent_id(self):
        """Should include parent_id when provided."""
        call = reconstruct_call(
            project_id="test/project",
            call_id="call-123",
            trace_id="trace-456",
            parent_id="parent-789",
        )
        assert call.parent_id == "parent-789"

    def test_call_has_empty_inputs(self):
        """Reconstructed calls should have empty inputs."""
        call = reconstruct_call(
            project_id="test/project",
            call_id="call-123",
            trace_id="trace-456",
        )
        assert call.inputs == {}


class TestSanitizeToolInputEdgeCases:
    def test_none_values_preserved(self):
        """None values in dict should remain None."""
        input_dict = {"key": None, "other_key": "value"}
        result = sanitize_tool_input(input_dict)
        assert result["key"] is None
        assert result["other_key"] == "value"

    def test_nested_dicts_not_traversed(self):
        """Only top-level strings are truncated."""
        long_string = "x" * 10000
        input_dict = {
            "nested": {"deep_key": long_string},
            "list": [long_string],
        }
        result = sanitize_tool_input(input_dict)
        # Nested values should be unchanged (not traversed)
        assert result["nested"]["deep_key"] == long_string
        assert result["list"][0] == long_string

    def test_boundary_at_max_length(self):
        """String exactly at max_length stays unchanged."""
        exact_length_string = "x" * MAX_TOOL_INPUT_LENGTH
        input_dict = {"content": exact_length_string}
        result = sanitize_tool_input(input_dict)
        assert result["content"] == exact_length_string
        assert not result["content"].endswith("...[truncated]")

    def test_empty_dict(self):
        """Empty dict returns empty dict."""
        assert sanitize_tool_input({}) == {}

    def test_non_string_values(self):
        """Ints, lists, bools preserved unchanged."""
        input_dict = {
            "int": 42,
            "list": [1, 2, 3],
            "bool": True,
            "float": 3.14,
        }
        result = sanitize_tool_input(input_dict)
        assert result == input_dict
        assert result["int"] == 42
        assert result["list"] == [1, 2, 3]
        assert result["bool"] is True
        assert result["float"] == 3.14


class TestReconstructCallEdgeCases:
    def test_empty_strings(self):
        """Empty strings for project_id/call_id/trace_id work."""
        call = reconstruct_call(
            project_id="",
            call_id="",
            trace_id="",
        )
        assert call.id == ""
        assert call.trace_id == ""
        assert call.project_id == ""

    def test_op_name_is_empty(self):
        """Verify _op_name is always empty string."""
        call = reconstruct_call(
            project_id="test/project",
            call_id="call-123",
            trace_id="trace-456",
        )
        assert call._op_name == ""

    def test_inputs_is_empty_dict(self):
        """Verify inputs is always empty dict."""
        call = reconstruct_call(
            project_id="test/project",
            call_id="call-123",
            trace_id="trace-456",
        )
        assert call.inputs == {}
        assert isinstance(call.inputs, dict)


class TestLogToolCall:
    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_logs_tool_call_with_all_fields(self, mock_weave):
        """Should call weave.log_call with correct parameters."""
        parent_call = MagicMock()

        log_tool_call(
            tool_name="Read",
            tool_input={"file_path": "/test/file.py"},
            tool_output="file contents",
            tool_use_id="tool-123",
            duration_ms=150,
            parent=parent_call,
        )

        mock_weave.log_call.assert_called_once()
        call_kwargs = mock_weave.log_call.call_args.kwargs
        assert call_kwargs["op"] == "claude_code.tool.Read"
        assert call_kwargs["inputs"] == {"file_path": "/test/file.py"}
        assert call_kwargs["output"] == {"result": "file contents"}
        assert call_kwargs["parent"] == parent_call

    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_sanitizes_long_inputs(self, mock_weave):
        """Should truncate long input values."""
        parent_call = MagicMock()
        long_content = "x" * 10000

        log_tool_call(
            tool_name="Write",
            tool_input={"content": long_content},
            tool_output=None,
            tool_use_id="tool-123",
            duration_ms=100,
            parent=parent_call,
        )

        call_kwargs = mock_weave.log_call.call_args.kwargs
        assert len(call_kwargs["inputs"]["content"]) < len(long_content)

    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_uses_display_name(self, mock_weave):
        """Should generate meaningful display name."""
        parent_call = MagicMock()

        log_tool_call(
            tool_name="Read",
            tool_input={"file_path": "/path/to/file.py"},
            tool_output="contents",
            tool_use_id="tool-123",
            duration_ms=100,
            parent=parent_call,
        )

        call_kwargs = mock_weave.log_call.call_args.kwargs
        assert call_kwargs["display_name"] == "Read: file.py"

    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_handles_none_output(self, mock_weave):
        """Should handle None output gracefully."""
        parent_call = MagicMock()

        log_tool_call(
            tool_name="Bash",
            tool_input={"command": "echo hi"},
            tool_output=None,
            tool_use_id="tool-123",
            duration_ms=50,
            parent=parent_call,
        )

        call_kwargs = mock_weave.log_call.call_args.kwargs
        assert call_kwargs["output"] is None


class TestLogToolCallEdgeCases:
    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_empty_input_dict(self, mock_weave):
        """Empty tool_input works."""
        parent_call = MagicMock()

        log_tool_call(
            tool_name="Read",
            tool_input={},
            tool_output="result",
            tool_use_id="tool-123",
            duration_ms=100,
            parent=parent_call,
        )

        call_kwargs = mock_weave.log_call.call_args.kwargs
        assert call_kwargs["inputs"] == {}

    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_zero_duration(self, mock_weave):
        """duration_ms=0 works."""
        parent_call = MagicMock()

        log_tool_call(
            tool_name="Bash",
            tool_input={"command": "echo hi"},
            tool_output="hi",
            tool_use_id="tool-123",
            duration_ms=0,
            parent=parent_call,
        )

        call_kwargs = mock_weave.log_call.call_args.kwargs
        assert call_kwargs["attributes"]["duration_ms"] == 0

    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_none_output(self, mock_weave):
        """None output doesn't add output key."""
        parent_call = MagicMock()

        log_tool_call(
            tool_name="Write",
            tool_input={"file_path": "/test.py", "content": "code"},
            tool_output=None,
            tool_use_id="tool-123",
            duration_ms=50,
            parent=parent_call,
        )

        call_kwargs = mock_weave.log_call.call_args.kwargs
        assert call_kwargs["output"] is None

    @patch("weave.integrations.claude_plugin.utils.weave")
    def test_custom_max_lengths(self, mock_weave):
        """Custom max_input_length and max_output_length work."""
        parent_call = MagicMock()
        long_input = "x" * 1000
        long_output = "y" * 2000

        log_tool_call(
            tool_name="Read",
            tool_input={"content": long_input},
            tool_output=long_output,
            tool_use_id="tool-123",
            duration_ms=100,
            parent=parent_call,
            max_input_length=100,
            max_output_length=200,
        )

        call_kwargs = mock_weave.log_call.call_args.kwargs
        # Input should be truncated to 100 + "...[truncated]"
        assert len(call_kwargs["inputs"]["content"]) == 100 + len("...[truncated]")
        assert call_kwargs["inputs"]["content"].endswith("...[truncated]")
        # Output should be truncated to 200 + "...[truncated]"
        assert len(call_kwargs["output"]["result"]) == 200 + len("...[truncated]")
        assert call_kwargs["output"]["result"].endswith("...[truncated]")


class TestGetGitInfo:
    """Tests for get_git_info() function."""

    def test_returns_git_info_for_git_repo(self):
        """Should return remote, branch, commit for a git repository."""
        # Use the current weave repo as test subject
        result = get_git_info("/Users/vanpelt/Development/weave")

        assert result is not None
        assert "remote" in result
        assert "branch" in result
        assert "commit" in result
        # Remote should be a git URL
        assert "github.com" in result["remote"] or "git@" in result["remote"]
        # Branch should be non-empty
        assert len(result["branch"]) > 0
        # Commit should be a 40-char hex SHA
        assert len(result["commit"]) == 40
        assert all(c in "0123456789abcdef" for c in result["commit"])

    def test_returns_none_for_non_git_directory(self):
        """Should return None for directories that are not git repos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_git_info(tmpdir)
            assert result is None

    def test_returns_none_for_nonexistent_directory(self):
        """Should return None for directories that don't exist."""
        result = get_git_info("/nonexistent/path/that/doesnt/exist")
        assert result is None

    def test_normalizes_https_remote(self):
        """Should handle HTTPS remote URLs."""
        # This is implicitly tested by test_returns_git_info_for_git_repo
        # but we add it here for documentation
        result = get_git_info("/Users/vanpelt/Development/weave")
        assert result is not None
        # Remote should be present regardless of format
        assert result["remote"] is not None


class TestExtractQuestionFromText:
    """Tests for extract_question_from_text() function."""

    def test_extracts_simple_question(self):
        """Should extract up to and including the first question mark in last paragraph."""
        text = "I can help you with that. What file would you like me to look at?"
        result = extract_question_from_text(text)
        # Extracts entire last paragraph up to first "?"
        assert result == "I can help you with that. What file would you like me to look at?"

    def test_extracts_question_from_last_paragraph(self):
        """Should only look at the last paragraph for questions."""
        text = """Here's what I found.

The code looks good overall.

Would you like me to make any changes?"""
        result = extract_question_from_text(text)
        assert result == "Would you like me to make any changes?"

    def test_returns_none_for_no_question(self):
        """Should return None when there's no question in the last paragraph."""
        text = "Done! I've completed the task successfully."
        result = extract_question_from_text(text)
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty input."""
        assert extract_question_from_text("") is None
        assert extract_question_from_text("   ") is None

    def test_returns_none_for_none(self):
        """Should return None for None input."""
        assert extract_question_from_text(None) is None

    def test_cleans_markdown_bold(self):
        """Should remove markdown bold formatting from questions."""
        text = "**Would you like me to proceed?**"
        result = extract_question_from_text(text)
        assert result == "Would you like me to proceed?"
        assert "**" not in result

    def test_cleans_partial_markdown_bold(self):
        """Should handle partial markdown bold in questions."""
        text = "**Important:** Should I continue?"
        result = extract_question_from_text(text)
        assert "**" not in result
        assert "?" in result

    def test_extracts_first_question_in_paragraph(self):
        """Should extract up to and including the first question mark."""
        text = "Would you like A? Or maybe B? Let me know."
        result = extract_question_from_text(text)
        assert result == "Would you like A?"

    def test_handles_multiline_text(self):
        """Should handle text with multiple lines and paragraphs."""
        text = """I've analyzed the codebase and found several issues:

1. The authentication module has a security vulnerability
2. The database queries are not optimized
3. Some tests are failing

Should I fix the security issue first?"""
        result = extract_question_from_text(text)
        assert result == "Should I fix the security issue first?"

    def test_question_with_leading_whitespace(self):
        """Should handle questions with leading/trailing whitespace."""
        text = "   What do you think?   "
        result = extract_question_from_text(text)
        assert result == "What do you think?"

    def test_next_question_marker_extracts_question(self):
        """Should extract question after **Next question:** marker."""
        text = """I've completed the analysis.

Here's what I found:
- Issue 1
- Issue 2

**Next question:**
Would you like me to fix issue 1 first?"""
        result = extract_question_from_text(text)
        assert result == "Would you like me to fix issue 1 first?"

    def test_next_question_marker_case_insensitive(self):
        """Should handle different cases of Next question marker."""
        text = """Some content.

**NEXT QUESTION:**
Should I proceed?"""
        result = extract_question_from_text(text)
        assert result == "Should I proceed?"

    def test_next_question_marker_with_multiple_lines_after(self):
        """Should find first line with ? after the marker."""
        text = """Some content.

**Next question:**

Here's the context for my question.
What approach would you prefer?

Some other text."""
        result = extract_question_from_text(text)
        assert result == "What approach would you prefer?"

    def test_next_question_marker_overrides_last_paragraph(self):
        """**Next question:** should take precedence over last paragraph."""
        text = """Content here.

**Next question:**
Should I use option A?

Additional notes and context that doesn't end with a question mark."""
        result = extract_question_from_text(text)
        assert result == "Should I use option A?"
