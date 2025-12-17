"""Constants for Claude Code plugin configuration.

Centralizes magic numbers and configuration values that were previously
scattered across multiple files.
"""

from __future__ import annotations


class ToolCallLimits:
    """Limits for tool call input/output truncation."""
    MAX_INPUT_LENGTH = 5000
    MAX_OUTPUT_LENGTH = 10000


class PromptLimits:
    """Limits for prompt/summary truncation."""
    MAX_PROMPT_LENGTH = 2000
    MAX_SUMMARY_LENGTH = 500


class DaemonConfig:
    """Daemon timing configuration."""
    INACTIVITY_TIMEOUT_SECONDS = 600
    SUBAGENT_DETECTION_TIMEOUT_SECONDS = 10
    STARTUP_TIMEOUT_SECONDS = 3.0
    POLL_INTERVAL_SECONDS = 0.5


class ParallelGrouping:
    """Configuration for parallel tool call detection."""
    # Tools within this gap (ms) are considered parallel
    THRESHOLD_MS = 1000
    # Wait this long (ms) before logging to allow parallel tools to arrive
    TOOL_AGE_THRESHOLD_MS = 2000


class DiffViewConfig:
    """Configuration for diff HTML generation."""
    LARGE_DIFF_THRESHOLD_LINES = 100
    MAX_PREVIEW_LINES = 100
