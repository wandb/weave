"""Artifact management for evaluation runs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class ArtifactManager:
    """Manages artifact directories for evaluation runs."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_run(self, name: str | None = None) -> RunArtifacts:
        """Create a new run directory.

        Args:
            name: Optional name for the run. If not provided, generates UUID.

        Returns:
            RunArtifacts instance for the new run.
        """
        run_id = name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return RunArtifacts(run_dir)

    def get_run(self, run_id: str) -> RunArtifacts:
        """Get an existing run.

        Args:
            run_id: The run identifier.

        Returns:
            RunArtifacts instance.

        Raises:
            FileNotFoundError: If run doesn't exist.
        """
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")
        return RunArtifacts(run_dir)

    def list_runs(self) -> list[str]:
        """List all run IDs.

        Returns:
            List of run identifiers.
        """
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]


class RunArtifacts:
    """Artifacts for a single evaluation run."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.run_id = run_dir.name

    def create_task(self, task_id: str, harness_id: str | None = None) -> TaskArtifacts:
        """Create artifacts directory for a task.

        Args:
            task_id: The task identifier.
            harness_id: Optional harness identifier for matrix runs.

        Returns:
            TaskArtifacts instance.
        """
        if harness_id:
            task_dir = self.run_dir / f"{task_id}_{harness_id}"
        else:
            task_dir = self.run_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return TaskArtifacts(task_dir)

    def get_task(self, task_id: str, harness_id: str | None = None) -> TaskArtifacts:
        """Get artifacts for a task.

        Args:
            task_id: The task identifier.
            harness_id: Optional harness identifier.

        Returns:
            TaskArtifacts instance.
        """
        if harness_id:
            task_dir = self.run_dir / f"{task_id}_{harness_id}"
        else:
            task_dir = self.run_dir / task_id
        return TaskArtifacts(task_dir)

    def list_tasks(self) -> list[str]:
        """List all task IDs in this run.

        Returns:
            List of task identifiers.
        """
        return [d.name for d in self.run_dir.iterdir() if d.is_dir()]

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        """Write run-level metadata.

        Args:
            metadata: Metadata dictionary.
        """
        (self.run_dir / "run_metadata.json").write_text(
            json.dumps(metadata, indent=2, default=str)
        )

    def read_metadata(self) -> dict[str, Any]:
        """Read run-level metadata.

        Returns:
            Metadata dictionary.
        """
        path = self.run_dir / "run_metadata.json"
        if path.exists():
            return json.loads(path.read_text())
        return {}


class TaskArtifacts:
    """Artifacts for a single task execution."""

    def __init__(self, task_dir: Path):
        self.task_dir = task_dir
        self.task_id = task_dir.name

        # Standard artifact paths
        self.workspace = task_dir / "workspace"
        self.trajectory = task_dir / "trajectory.jsonl"
        self.metadata_file = task_dir / "metadata.json"
        self.scores_dir = task_dir / "scores"

    def setup(self) -> None:
        """Create artifact directories."""
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.scores_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        """Return the task artifacts directory path."""
        return self.task_dir

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        """Write task metadata.

        Args:
            metadata: Metadata dictionary.
        """
        self.metadata_file.write_text(json.dumps(metadata, indent=2, default=str))

    def read_metadata(self) -> dict[str, Any]:
        """Read task metadata.

        Returns:
            Metadata dictionary.
        """
        if self.metadata_file.exists():
            return json.loads(self.metadata_file.read_text())
        return {}

    def write_trajectory(self, events: list[dict[str, Any]]) -> None:
        """Write trajectory events.

        Args:
            events: List of trajectory events.
        """
        lines = [json.dumps(e) for e in events]
        self.trajectory.write_text("\n".join(lines))

    def append_trajectory(self, event: dict[str, Any]) -> None:
        """Append a single event to trajectory.

        Args:
            event: Trajectory event.
        """
        with open(self.trajectory, "a") as f:
            f.write(json.dumps(event) + "\n")

    def read_trajectory(self) -> list[dict[str, Any]]:
        """Read trajectory events.

        Returns:
            List of trajectory events.
        """
        if not self.trajectory.exists():
            return []
        events = []
        for line in self.trajectory.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def write_score(self, scorer_name: str, score: dict[str, Any]) -> None:
        """Write score from a scorer.

        Args:
            scorer_name: Name of the scorer.
            score: Score dictionary.
        """
        self.scores_dir.mkdir(parents=True, exist_ok=True)
        score_file = self.scores_dir / f"{scorer_name}.json"
        score_file.write_text(json.dumps(score, indent=2))

    def read_score(self, scorer_name: str) -> dict[str, Any] | None:
        """Read score from a scorer.

        Args:
            scorer_name: Name of the scorer.

        Returns:
            Score dictionary or None if not found.
        """
        score_file = self.scores_dir / f"{scorer_name}.json"
        if score_file.exists():
            return json.loads(score_file.read_text())
        return None

    def list_scores(self) -> list[str]:
        """List all scorer names with scores.

        Returns:
            List of scorer names.
        """
        if not self.scores_dir.exists():
            return []
        return [f.stem for f in self.scores_dir.glob("*.json")]
