"""Integration tests for daemon tool call handling.

These tests verify end-to-end behavior of tool buffering and parallel grouping.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from weave.integrations.claude_plugin.utils import (
    BufferedToolResult,
    ToolResultBuffer,
)


class TestDaemonToolBuffering:
    """Integration tests for daemon tool buffering behavior."""

    def test_parallel_tools_grouped_in_ui(self) -> None:
        """Verify parallel tools are grouped under a wrapper call."""
        buffer = ToolResultBuffer()
        base = datetime.now(timezone.utc) - timedelta(seconds=5)
        result_time = base + timedelta(milliseconds=500)  # Results arrive ~500ms after tool_use

        # Simulate 3 parallel Read calls (common pattern)
        buffer.add("t1", "Read", {"file": "a.py"}, base, "content a", result_time)
        buffer.add("t2", "Read", {"file": "b.py"}, base + timedelta(milliseconds=100), "content b", result_time + timedelta(milliseconds=100))
        buffer.add("t3", "Read", {"file": "c.py"}, base + timedelta(milliseconds=200), "content c", result_time + timedelta(milliseconds=200))

        groups = buffer.get_ready_to_flush(force=True)

        # Should be one group with all 3
        assert len(groups) == 1
        assert len(groups[0]) == 3

        # Verify all tools present
        names = [t.name for t in groups[0]]
        assert names == ["Read", "Read", "Read"]

    def test_error_tools_marked_correctly(self) -> None:
        """Verify is_error flag flows through buffer."""
        buffer = ToolResultBuffer()
        base = datetime.now(timezone.utc) - timedelta(seconds=5)
        result_time = base + timedelta(milliseconds=100)

        buffer.add("t1", "Bash", {"command": "exit 1"}, base, "error output", result_time, is_error=True)

        groups = buffer.get_ready_to_flush(force=True)

        assert groups[0][0].is_error is True
        assert groups[0][0].result == "error output"

    def test_mixed_parallel_and_sequential(self) -> None:
        """Verify mix of parallel and sequential tools grouped correctly."""
        buffer = ToolResultBuffer()
        base = datetime.now(timezone.utc) - timedelta(seconds=10)

        # Group 1: 2 parallel Reads
        buffer.add("t1", "Read", {}, base, "r1", base + timedelta(milliseconds=500))
        buffer.add("t2", "Read", {}, base + timedelta(milliseconds=200), "r2", base + timedelta(milliseconds=700))

        # Group 2: Single Edit (2 seconds later)
        buffer.add("t3", "Edit", {}, base + timedelta(seconds=2), "r3", base + timedelta(seconds=2, milliseconds=100))

        # Group 3: 2 parallel Bash (4 seconds later)
        buffer.add("t4", "Bash", {}, base + timedelta(seconds=4), "r4", base + timedelta(seconds=4, milliseconds=1000))
        buffer.add("t5", "Bash", {}, base + timedelta(seconds=4, milliseconds=100), "r5", base + timedelta(seconds=4, milliseconds=1100))

        groups = buffer.get_ready_to_flush(force=True)

        assert len(groups) == 3
        assert len(groups[0]) == 2  # Parallel Reads
        assert len(groups[1]) == 1  # Single Edit
        assert len(groups[2]) == 2  # Parallel Bash
