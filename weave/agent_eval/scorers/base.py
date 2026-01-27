"""Base scorer protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    """Result of a single check."""

    id: str
    passed: bool
    notes: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreResult:
    """Result from a scorer."""

    overall_pass: bool
    score: float  # 0-100
    checks: list[CheckResult]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_pass": self.overall_pass,
            "score": self.score,
            "checks": [
                {
                    "id": c.id,
                    "pass": c.passed,
                    "notes": c.notes,
                    **({"details": c.details} if c.details else {}),
                }
                for c in self.checks
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoreResult:
        """Create from dictionary."""
        return cls(
            overall_pass=data["overall_pass"],
            score=data["score"],
            checks=[
                CheckResult(
                    id=c["id"],
                    passed=c["pass"],
                    notes=c.get("notes", ""),
                    details=c.get("details", {}),
                )
                for c in data.get("checks", [])
            ],
            metadata=data.get("metadata", {}),
        )


class Scorer(ABC):
    """Abstract base class for scorers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the scorer name."""
        ...

    @abstractmethod
    async def score(self, artifacts_path: Path) -> ScoreResult:
        """Score the artifacts from a harness run.

        Args:
            artifacts_path: Path to artifacts directory containing:
                - workspace/: Final filesystem state
                - trajectory.jsonl: Execution trace
                - metadata.json: Job metadata

        Returns:
            ScoreResult with overall pass/fail and individual checks.
        """
        ...

    def required_env_keys(self) -> list[str]:
        """Return environment variable names this scorer requires.

        Override this for scorers that need API keys (e.g., LLM rubric).

        Returns:
            List of required environment variable names.
        """
        return []
