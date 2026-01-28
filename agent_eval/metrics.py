"""Metrics extraction from agent execution artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExecutionMetrics:
    """Metrics extracted from agent execution."""
    
    # Timing
    duration_seconds: float = 0.0
    
    # Token usage (if available from trajectory)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Execution counts
    command_count: int = 0
    file_write_count: int = 0
    file_read_count: int = 0
    tool_call_count: int = 0
    
    # Turn/iteration counts
    turn_count: int = 0
    
    # Commands executed (for debugging)
    commands: list[str] = field(default_factory=list)
    
    # Raw events (for trajectory_contains checks)
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "duration_seconds": self.duration_seconds,
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.total_tokens,
            },
            "counts": {
                "commands": self.command_count,
                "file_writes": self.file_write_count,
                "file_reads": self.file_read_count,
                "tool_calls": self.tool_call_count,
                "turns": self.turn_count,
            },
            "commands_executed": self.commands[:50],  # Limit for readability
        }


def extract_metrics(artifacts_path: Path) -> ExecutionMetrics:
    """Extract metrics from artifacts directory.
    
    Args:
        artifacts_path: Path to artifacts directory containing:
            - metadata.json: Basic job metadata
            - stdout.log: Raw stdout (may contain JSON events)
            - trajectory.jsonl: Structured execution trace (if available)
    
    Returns:
        ExecutionMetrics with extracted data.
    """
    metrics = ExecutionMetrics()
    
    # Read basic metadata
    metadata_file = artifacts_path / "metadata.json"
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text())
            metrics.duration_seconds = metadata.get("duration_seconds", 0.0)
        except Exception:
            pass
    
    # Try to parse trajectory.jsonl first
    trajectory_file = artifacts_path / "trajectory.jsonl"
    if trajectory_file.exists():
        _parse_trajectory_jsonl(trajectory_file, metrics)
    else:
        # Fall back to parsing stdout.log for JSON events
        stdout_file = artifacts_path / "stdout.log"
        if stdout_file.exists():
            _parse_stdout_for_events(stdout_file, metrics)
    
    return metrics


def _parse_trajectory_jsonl(trajectory_file: Path, metrics: ExecutionMetrics) -> None:
    """Parse trajectory.jsonl file (Codex format)."""
    try:
        content = trajectory_file.read_text()
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                metrics.raw_events.append(event)
                _process_event(event, metrics)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass


def _parse_stdout_for_events(stdout_file: Path, metrics: ExecutionMetrics) -> None:
    """Parse stdout.log looking for JSON events."""
    try:
        content = stdout_file.read_text()
        for line in content.splitlines():
            if not line.strip():
                continue
            # Try to parse as JSON
            if line.strip().startswith("{"):
                try:
                    event = json.loads(line)
                    metrics.raw_events.append(event)
                    _process_event(event, metrics)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass


def _process_event(event: dict[str, Any], metrics: ExecutionMetrics) -> None:
    """Process a single event and update metrics."""
    event_type = event.get("type", "")
    
    # Handle Codex-style events
    if event_type in ("item.started", "item.completed"):
        item = event.get("item", {})
        item_type = item.get("type", "")
        
        if item_type == "command_execution":
            metrics.command_count += 1
            command = item.get("command", "")
            if command:
                metrics.commands.append(command)
        elif item_type == "file_write":
            metrics.file_write_count += 1
        elif item_type == "file_read":
            metrics.file_read_count += 1
        elif item_type in ("tool_call", "function_call"):
            metrics.tool_call_count += 1
    
    # Handle turn events (for token usage)
    elif event_type == "turn.completed":
        metrics.turn_count += 1
        usage = event.get("usage", {})
        metrics.input_tokens += usage.get("input_tokens", 0)
        metrics.output_tokens += usage.get("output_tokens", 0)
        metrics.total_tokens += usage.get("total_tokens", 0)
    
    # Handle OpenCode-style events
    elif event_type == "tool_use":
        metrics.tool_call_count += 1
        tool_name = event.get("name", "")
        if tool_name in ("bash", "shell", "execute"):
            metrics.command_count += 1
            command = event.get("input", {}).get("command", "")
            if command:
                metrics.commands.append(command)
        elif tool_name in ("write", "write_file"):
            metrics.file_write_count += 1
        elif tool_name in ("read", "read_file"):
            metrics.file_read_count += 1
    
    # Handle usage directly in event
    elif "usage" in event:
        usage = event["usage"]
        if isinstance(usage, dict):
            metrics.input_tokens += usage.get("input_tokens", 0)
            metrics.output_tokens += usage.get("output_tokens", 0)
            metrics.total_tokens += usage.get("total_tokens", 0)
    
    # Handle message events that might contain tool calls
    elif event_type == "message":
        content = event.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    _process_event({"type": "tool_use", **item}, metrics)


def trajectory_contains(artifacts_path: Path, pattern: str) -> bool:
    """Check if trajectory contains a pattern.
    
    This searches through:
    - Commands executed
    - Tool names
    - Raw event content
    
    Args:
        artifacts_path: Path to artifacts directory
        pattern: String pattern to search for
    
    Returns:
        True if pattern is found in trajectory
    """
    metrics = extract_metrics(artifacts_path)
    
    # Check commands
    pattern_lower = pattern.lower()
    for cmd in metrics.commands:
        if pattern_lower in cmd.lower():
            return True
    
    # Check raw events
    for event in metrics.raw_events:
        event_str = json.dumps(event).lower()
        if pattern_lower in event_str:
            return True
    
    # Also check stdout.log directly
    stdout_file = artifacts_path / "stdout.log"
    if stdout_file.exists():
        try:
            content = stdout_file.read_text().lower()
            if pattern_lower in content:
                return True
        except Exception:
            pass
    
    # Check stderr.log too
    stderr_file = artifacts_path / "stderr.log"
    if stderr_file.exists():
        try:
            content = stderr_file.read_text().lower()
            if pattern_lower in content:
                return True
        except Exception:
            pass
    
    return False
