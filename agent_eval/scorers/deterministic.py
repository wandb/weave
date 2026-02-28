"""Deterministic scorer for file and command checks."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .base import CheckResult, ScoreResult, Scorer

if TYPE_CHECKING:
    from ..config.schema import DeterministicCheck, DeterministicScorerConfig


class DeterministicScorer(Scorer):
    """Scorer that performs deterministic checks on artifacts."""

    def __init__(self, config: DeterministicScorerConfig):
        self.config = config

    @property
    def name(self) -> str:
        return "deterministic"

    async def score(self, artifacts_path: Path) -> ScoreResult:
        """Run all deterministic checks."""
        start_time = time.time()
        checks: list[CheckResult] = []

        workspace = artifacts_path / "workspace"
        trajectory = artifacts_path / "trajectory.jsonl"

        for check in self.config.checks:
            result = self._run_check(check, workspace, trajectory)
            checks.append(result)

        duration_ms = int((time.time() - start_time) * 1000)
        passed_count = sum(1 for c in checks if c.passed)
        total_count = len(checks)

        return ScoreResult(
            overall_pass=passed_count == total_count,
            score=(passed_count / total_count * 100) if total_count > 0 else 100,
            checks=checks,
            metadata={
                "scorer": self.name,
                "version": "1.0",
                "duration_ms": duration_ms,
                "checks_passed": passed_count,
                "checks_total": total_count,
            },
        )

    def _run_check(
        self,
        check: DeterministicCheck,
        workspace: Path,
        trajectory: Path,
    ) -> CheckResult:
        """Run a single check."""
        from ..config.schema import CheckType

        check_id = f"{check.type.value}_{check.path or check.pattern or 'unknown'}"
        check_id = re.sub(r"[^\w]", "_", check_id)[:50]

        try:
            if check.type == CheckType.FILE_EXISTS:
                return self._check_file_exists(check_id, check.path, workspace)
            elif check.type == CheckType.FILE_CONTAINS:
                return self._check_file_contains(
                    check_id, check.path, check.pattern, workspace
                )
            elif check.type == CheckType.TRAJECTORY_CONTAINS:
                return self._check_trajectory_contains(
                    check_id, check.pattern, trajectory
                )
            elif check.type == CheckType.COMMAND_EXECUTED:
                return self._check_command_executed(
                    check_id, check.pattern, trajectory
                )
            else:
                return CheckResult(
                    id=check_id,
                    passed=False,
                    notes=f"Unknown check type: {check.type}",
                )
        except Exception as e:
            return CheckResult(
                id=check_id,
                passed=False,
                notes=f"Check error: {e}",
            )

    def _check_file_exists(
        self, check_id: str, path: str | None, workspace: Path
    ) -> CheckResult:
        """Check if a file exists."""
        if not path:
            return CheckResult(id=check_id, passed=False, notes="No path specified")

        file_path = workspace / path
        exists = file_path.exists()

        return CheckResult(
            id=check_id,
            passed=exists,
            notes="" if exists else f"File not found: {path}",
            details={"path": path, "absolute_path": str(file_path)},
        )

    def _check_file_contains(
        self,
        check_id: str,
        path: str | None,
        pattern: str | None,
        workspace: Path,
    ) -> CheckResult:
        """Check if a file contains a pattern."""
        if not path:
            return CheckResult(id=check_id, passed=False, notes="No path specified")
        if not pattern:
            return CheckResult(id=check_id, passed=False, notes="No pattern specified")

        file_path = workspace / path
        if not file_path.exists():
            return CheckResult(
                id=check_id,
                passed=False,
                notes=f"File not found: {path}",
            )

        content = file_path.read_text()
        matches = bool(re.search(pattern, content))

        return CheckResult(
            id=check_id,
            passed=matches,
            notes="" if matches else f"Pattern not found in {path}",
            details={"path": path, "pattern": pattern},
        )

    def _check_trajectory_contains(
        self,
        check_id: str,
        pattern: str | None,
        trajectory: Path,
    ) -> CheckResult:
        """Check if trajectory/logs contain a pattern.
        
        Searches in:
        - trajectory.jsonl (if exists)
        - stdout.log
        - stderr.log
        """
        if not pattern:
            return CheckResult(id=check_id, passed=False, notes="No pattern specified")

        # Check trajectory.jsonl first
        if trajectory.exists():
            content = trajectory.read_text()
            if re.search(pattern, content, re.IGNORECASE):
                return CheckResult(
                    id=check_id,
                    passed=True,
                    notes="",
                    details={"pattern": pattern, "found_in": "trajectory.jsonl"},
                )
        
        # Check stdout.log
        artifacts_dir = trajectory.parent
        stdout_file = artifacts_dir / "stdout.log"
        if stdout_file.exists():
            content = stdout_file.read_text()
            if re.search(pattern, content, re.IGNORECASE):
                return CheckResult(
                    id=check_id,
                    passed=True,
                    notes="",
                    details={"pattern": pattern, "found_in": "stdout.log"},
                )
        
        # Check stderr.log
        stderr_file = artifacts_dir / "stderr.log"
        if stderr_file.exists():
            content = stderr_file.read_text()
            if re.search(pattern, content, re.IGNORECASE):
                return CheckResult(
                    id=check_id,
                    passed=True,
                    notes="",
                    details={"pattern": pattern, "found_in": "stderr.log"},
                )

        return CheckResult(
            id=check_id,
            passed=False,
            notes=f"Pattern '{pattern}' not found in trajectory or logs",
            details={"pattern": pattern},
        )

    def _check_command_executed(
        self,
        check_id: str,
        pattern: str | None,
        trajectory: Path,
    ) -> CheckResult:
        """Check if a command matching pattern was executed."""
        if not pattern:
            return CheckResult(id=check_id, passed=False, notes="No pattern specified")

        if not trajectory.exists():
            return CheckResult(
                id=check_id,
                passed=False,
                notes="Trajectory file not found",
            )

        # Parse trajectory JSONL and look for command events
        found = False
        for line in trajectory.read_text().splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                # Check various command event formats
                cmd = self._extract_command(event)
                if cmd and re.search(pattern, cmd):
                    found = True
                    break
            except json.JSONDecodeError:
                continue

        return CheckResult(
            id=check_id,
            passed=found,
            notes="" if found else f"Command matching '{pattern}' not found",
            details={"pattern": pattern},
        )

    def _extract_command(self, event: dict) -> str | None:
        """Extract command string from various event formats."""
        # Codex format
        if event.get("type") in ("item.started", "item.completed"):
            item = event.get("item", {})
            if item.get("type") == "command_execution":
                return item.get("command")

        # Generic format
        if "command" in event:
            return event["command"]

        # Tool call format
        if event.get("type") == "tool_call":
            if event.get("tool") in ("bash", "shell", "execute"):
                return event.get("input", {}).get("command")

        return None
