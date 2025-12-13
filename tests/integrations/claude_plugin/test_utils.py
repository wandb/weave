"""Tests for claude_plugin utilities."""

from unittest.mock import MagicMock, patch

import pytest

from weave.integrations.claude_plugin.utils import (
    sanitize_tool_input,
    reconstruct_call,
    log_tool_call,
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
