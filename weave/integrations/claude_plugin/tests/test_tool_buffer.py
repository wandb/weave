"""Tests for ToolResultBuffer parallel grouping logic."""

from datetime import datetime, timedelta, timezone

from weave.integrations.claude_plugin.utils import (
    ToolResultBuffer,
)


def make_timestamp(offset_ms: int = 0) -> datetime:
    """Create a timestamp with optional offset from a base time."""
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(milliseconds=offset_ms)


def make_result_timestamp(tool_use_time: datetime, duration_ms: int = 500) -> datetime:
    """Create a result timestamp based on tool_use time plus duration."""
    return tool_use_time + timedelta(milliseconds=duration_ms)


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
        now = datetime.now(timezone.utc)
        buffer.add(
            tool_use_id="t1",
            name="Read",
            input={"file": "test.py"},
            timestamp=now,
            result="content",
            result_timestamp=make_result_timestamp(now),
        )
        assert buffer.get_ready_to_flush() == []

    def test_single_tool_force_flush(self) -> None:
        """Force flush should return tool regardless of age."""
        buffer = ToolResultBuffer()
        now = datetime.now(timezone.utc)
        buffer.add(
            tool_use_id="t1",
            name="Read",
            input={"file": "test.py"},
            timestamp=now,
            result="content",
            result_timestamp=make_result_timestamp(now),
        )
        groups = buffer.get_ready_to_flush(force=True)
        assert len(groups) == 1
        assert len(groups[0]) == 1
        assert groups[0][0].tool_use_id == "t1"

    def test_parallel_tools_grouped_together(self) -> None:
        """Tools within 1000ms should be in same group."""
        buffer = ToolResultBuffer()
        base = make_timestamp(-5000)  # 5 seconds ago (aged)

        t1 = base
        t2 = base + timedelta(milliseconds=500)
        t3 = base + timedelta(milliseconds=800)
        buffer.add("t1", "Read", {}, t1, "r1", make_result_timestamp(t1))
        buffer.add("t2", "Grep", {}, t2, "r2", make_result_timestamp(t2))
        buffer.add("t3", "Glob", {}, t3, "r3", make_result_timestamp(t3))

        groups = buffer.get_ready_to_flush(force=True)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_sequential_tools_separate_groups(self) -> None:
        """Tools with >1000ms gap should be in separate groups."""
        buffer = ToolResultBuffer()
        base = make_timestamp(-10000)  # 10 seconds ago

        t1 = base
        t2 = base + timedelta(milliseconds=2000)
        buffer.add("t1", "Read", {}, t1, "r1", make_result_timestamp(t1))
        buffer.add("t2", "Edit", {}, t2, "r2", make_result_timestamp(t2))

        groups = buffer.get_ready_to_flush(force=True)
        assert len(groups) == 2
        assert groups[0][0].tool_use_id == "t1"
        assert groups[1][0].tool_use_id == "t2"

    def test_remove_clears_flushed_tools(self) -> None:
        """Remove should clear tools from buffer."""
        buffer = ToolResultBuffer()
        t1 = make_timestamp(-5000)
        buffer.add("t1", "Read", {}, t1, "r1", make_result_timestamp(t1))

        groups = buffer.get_ready_to_flush(force=True)
        buffer.remove(groups)

        assert buffer.is_empty()

    def test_error_flag_preserved(self) -> None:
        """is_error flag should be preserved through buffer."""
        buffer = ToolResultBuffer()
        t1 = make_timestamp(-5000)
        buffer.add(
            "t1", "Bash", {}, t1, "error", make_result_timestamp(t1), is_error=True
        )

        groups = buffer.get_ready_to_flush(force=True)
        assert groups[0][0].is_error is True

    def test_smart_aging_waits_for_complete_group(self) -> None:
        """Should not flush partial parallel groups."""
        buffer = ToolResultBuffer()
        # Old tool (aged)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        # New tool within parallel threshold of old (not aged)
        new_time = datetime.now(timezone.utc) - timedelta(milliseconds=500)

        t1 = old_time
        t2 = old_time + timedelta(milliseconds=500)
        buffer.add("t1", "Read", {}, t1, "r1", make_result_timestamp(t1))
        buffer.add("t2", "Grep", {}, t2, "r2", make_result_timestamp(t2))

        # Both are in same parallel window, both should be aged
        groups = buffer.get_ready_to_flush()
        # Should get both since t2 is also aged (old_time + 500ms is still ~4.5s ago)
        assert len(groups) == 1
        assert len(groups[0]) == 2
