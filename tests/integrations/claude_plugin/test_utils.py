"""Tests for claude_plugin utilities."""

import pytest

from weave.integrations.claude_plugin.utils import (
    sanitize_tool_input,
    reconstruct_call,
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
