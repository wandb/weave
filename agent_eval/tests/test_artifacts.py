"""Tests for artifact management."""

import json
from pathlib import Path

import pytest

from agent_eval.artifacts import ArtifactManager, RunArtifacts, TaskArtifacts


class TestArtifactManager:
    """Test artifact manager."""

    def test_create_run(self, tmp_path: Path):
        """Test creating a new run."""
        manager = ArtifactManager(tmp_path)
        run = manager.create_run()
        
        assert run.run_dir.exists()
        assert run.run_id.startswith("run_")

    def test_create_run_with_name(self, tmp_path: Path):
        """Test creating a run with custom name."""
        manager = ArtifactManager(tmp_path)
        run = manager.create_run(name="custom-run")
        
        assert run.run_id == "custom-run"
        assert run.run_dir.name == "custom-run"

    def test_get_run(self, tmp_path: Path):
        """Test retrieving an existing run."""
        manager = ArtifactManager(tmp_path)
        created = manager.create_run(name="test-run")
        
        retrieved = manager.get_run("test-run")
        
        assert retrieved.run_id == created.run_id
        assert retrieved.run_dir == created.run_dir

    def test_get_nonexistent_run(self, tmp_path: Path):
        """Test retrieving non-existent run raises error."""
        manager = ArtifactManager(tmp_path)
        
        with pytest.raises(FileNotFoundError):
            manager.get_run("nonexistent")

    def test_list_runs(self, tmp_path: Path):
        """Test listing runs."""
        manager = ArtifactManager(tmp_path)
        manager.create_run(name="run-1")
        manager.create_run(name="run-2")
        
        runs = manager.list_runs()
        
        assert "run-1" in runs
        assert "run-2" in runs


class TestRunArtifacts:
    """Test run artifacts."""

    def test_create_task(self, tmp_path: Path):
        """Test creating task artifacts."""
        run = RunArtifacts(tmp_path / "run")
        run.run_dir.mkdir(parents=True)
        
        task = run.create_task("task-1")
        
        assert task.task_dir.exists()
        assert task.task_id == "task-1"

    def test_create_task_with_harness_id(self, tmp_path: Path):
        """Test creating task with harness ID."""
        run = RunArtifacts(tmp_path / "run")
        run.run_dir.mkdir(parents=True)
        
        task = run.create_task("task-1", harness_id="codex_gpt-4o")
        
        assert task.task_id == "task-1_codex_gpt-4o"

    def test_list_tasks(self, tmp_path: Path):
        """Test listing tasks."""
        run = RunArtifacts(tmp_path / "run")
        run.run_dir.mkdir(parents=True)
        
        run.create_task("task-1")
        run.create_task("task-2")
        
        tasks = run.list_tasks()
        
        assert "task-1" in tasks
        assert "task-2" in tasks

    def test_write_read_metadata(self, tmp_path: Path):
        """Test writing and reading run metadata."""
        run = RunArtifacts(tmp_path / "run")
        run.run_dir.mkdir(parents=True)
        
        run.write_metadata({"key": "value", "count": 42})
        
        metadata = run.read_metadata()
        
        assert metadata["key"] == "value"
        assert metadata["count"] == 42


class TestTaskArtifacts:
    """Test task artifacts."""

    def test_setup(self, tmp_path: Path):
        """Test setting up task directories."""
        task = TaskArtifacts(tmp_path / "task")
        task.setup()
        
        assert task.task_dir.exists()
        assert task.workspace.exists()
        assert task.scores_dir.exists()

    def test_write_read_metadata(self, tmp_path: Path):
        """Test writing and reading task metadata."""
        task = TaskArtifacts(tmp_path / "task")
        task.setup()
        
        task.write_metadata({"task_id": "test", "status": "running"})
        
        metadata = task.read_metadata()
        
        assert metadata["task_id"] == "test"
        assert metadata["status"] == "running"

    def test_trajectory_operations(self, tmp_path: Path):
        """Test trajectory write and read operations."""
        task = TaskArtifacts(tmp_path / "task")
        task.setup()
        
        events = [
            {"type": "start", "time": 0},
            {"type": "end", "time": 100},
        ]
        task.write_trajectory(events)
        
        read_events = task.read_trajectory()
        
        assert len(read_events) == 2
        assert read_events[0]["type"] == "start"
        assert read_events[1]["type"] == "end"

    def test_append_trajectory(self, tmp_path: Path):
        """Test appending to trajectory."""
        task = TaskArtifacts(tmp_path / "task")
        task.setup()
        
        task.append_trajectory({"type": "event1"})
        task.append_trajectory({"type": "event2"})
        
        events = task.read_trajectory()
        
        assert len(events) == 2

    def test_score_operations(self, tmp_path: Path):
        """Test score write, read, and list operations."""
        task = TaskArtifacts(tmp_path / "task")
        task.setup()
        
        task.write_score("deterministic", {"overall_pass": True, "score": 100})
        task.write_score("rubric", {"overall_pass": False, "score": 75})
        
        det_score = task.read_score("deterministic")
        rub_score = task.read_score("rubric")
        missing = task.read_score("nonexistent")
        
        assert det_score["overall_pass"] is True
        assert rub_score["score"] == 75
        assert missing is None
        
        scorers = task.list_scores()
        assert "deterministic" in scorers
        assert "rubric" in scorers
