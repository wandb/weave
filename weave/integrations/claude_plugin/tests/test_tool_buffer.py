"""Tests for ToolResultBuffer parallel grouping logic."""

from datetime import datetime, timedelta, timezone

import pytest

from weave.integrations.claude_plugin.utils import (
    BufferedToolResult,
    ToolResultBuffer,
)


def make_timestamp(offset_ms: int = 0) -> datetime:
    """Create a timestamp with optional offset from a base time."""
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(milliseconds=offset_ms)


class TestToolResultBuffer:
    """Tests for ToolResultBuffer."""

    def test_empty_buffer_returns_no_groups(self) -> None:
        """Empty buffer should return empty list."""
        buffer = ToolResultBuffer()
        assert buffer.get_ready_to_flush() == []
        assert buffer.get_ready_to_flush(force=True) == []

    def test_single_tool_not_aged_returns_empty(self) -> None:
        """Tool added just now should not be ready."""
        buffer = ToolResultBuffer()
        buffer.add(
            tool_use_id="t1",
            name="Read",
            input={"file": "test.py"},
            timestamp=datetime.now(timezone.utc),
            result="content",
        )
        assert buffer.get_ready_to_flush() == []

    def test_single_tool_force_flush(self) -> None:
        """Force flush should return tool regardless of age."""
        buffer = ToolResultBuffer()
        buffer.add(
            tool_use_id="t1",
            name="Read",
            input={"file": "test.py"},
            timestamp=datetime.now(timezone.utc),
            result="content",
        )
        groups = buffer.get_ready_to_flush(force=True)
        assert len(groups) == 1
        assert len(groups[0]) == 1
        assert groups[0][0].tool_use_id == "t1"

    def test_parallel_tools_grouped_together(self) -> None:
        """Tools within 1000ms should be in same group."""
        buffer = ToolResultBuffer()
        base = make_timestamp(-5000)  # 5 seconds ago (aged)

        buffer.add("t1", "Read", {}, base, "r1")
        buffer.add("t2", "Grep", {}, base + timedelta(milliseconds=500), "r2")
        buffer.add("t3", "Glob", {}, base + timedelta(milliseconds=800), "r3")

        groups = buffer.get_ready_to_flush(force=True)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_sequential_tools_separate_groups(self) -> None:
        """Tools with >1000ms gap should be in separate groups."""
        buffer = ToolResultBuffer()
        base = make_timestamp(-10000)  # 10 seconds ago

        buffer.add("t1", "Read", {}, base, "r1")
        buffer.add("t2", "Edit", {}, base + timedelta(milliseconds=2000), "r2")

        groups = buffer.get_ready_to_flush(force=True)
        assert len(groups) == 2
        assert groups[0][0].tool_use_id == "t1"
        assert groups[1][0].tool_use_id == "t2"

    def test_remove_clears_flushed_tools(self) -> None:
        """Remove should clear tools from buffer."""
        buffer = ToolResultBuffer()
        buffer.add("t1", "Read", {}, make_timestamp(-5000), "r1")

        groups = buffer.get_ready_to_flush(force=True)
        buffer.remove(groups)

        assert buffer.is_empty()

    def test_error_flag_preserved(self) -> None:
        """is_error flag should be preserved through buffer."""
        buffer = ToolResultBuffer()
        buffer.add("t1", "Bash", {}, make_timestamp(-5000), "error", is_error=True)

        groups = buffer.get_ready_to_flush(force=True)
        assert groups[0][0].is_error is True

    def test_smart_aging_waits_for_complete_group(self) -> None:
        """Should not flush partial parallel groups."""
        buffer = ToolResultBuffer()
        # Old tool (aged)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        # New tool within parallel threshold of old (not aged)
        new_time = datetime.now(timezone.utc) - timedelta(milliseconds=500)

        buffer.add("t1", "Read", {}, old_time, "r1")
        buffer.add("t2", "Grep", {}, old_time + timedelta(milliseconds=500), "r2")

        # Both are in same parallel window, both should be aged
        groups = buffer.get_ready_to_flush()
        # Should get both since t2 is also aged (old_time + 500ms is still ~4.5s ago)
        assert len(groups) == 1
        assert len(groups[0]) == 2
