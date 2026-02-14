"""Tests for scorers."""

import json
from pathlib import Path

import pytest

from agent_eval.config.schema import (
    CheckType,
    DeterministicCheck,
    DeterministicScorerConfig,
)
from agent_eval.scorers.deterministic import DeterministicScorer
from agent_eval.scorers.base import ScoreResult, CheckResult


class TestDeterministicScorer:
    """Test deterministic scorer."""

    @pytest.fixture
    def artifacts_dir(self, tmp_path: Path) -> Path:
        """Create a mock artifacts directory."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        
        # Create some test files
        (workspace / "output.txt").write_text("Hello, World!")
        (workspace / "data.json").write_text('{"success": true}')
        
        subdir = workspace / "src"
        subdir.mkdir()
        (subdir / "main.py").write_text("print('hello')")
        
        # Create trajectory
        trajectory = tmp_path / "trajectory.jsonl"
        events = [
            {"type": "item.started", "item": {"type": "command_execution", "command": "npm install"}},
            {"type": "item.completed", "item": {"type": "command_execution", "command": "npm install"}},
            {"type": "item.started", "item": {"type": "command_execution", "command": "npm run build"}},
        ]
        trajectory.write_text("\n".join(json.dumps(e) for e in events))
        
        return tmp_path

    @pytest.mark.asyncio
    async def test_file_exists_pass(self, artifacts_dir: Path):
        """Test file_exists check passes when file exists."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(type=CheckType.FILE_EXISTS, path="output.txt"),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert result.overall_pass
        assert result.score == 100.0
        assert len(result.checks) == 1
        assert result.checks[0].passed

    @pytest.mark.asyncio
    async def test_file_exists_fail(self, artifacts_dir: Path):
        """Test file_exists check fails when file doesn't exist."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(type=CheckType.FILE_EXISTS, path="nonexistent.txt"),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert not result.overall_pass
        assert result.score == 0.0
        assert not result.checks[0].passed
        assert "not found" in result.checks[0].notes

    @pytest.mark.asyncio
    async def test_file_exists_nested(self, artifacts_dir: Path):
        """Test file_exists check with nested path."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(type=CheckType.FILE_EXISTS, path="src/main.py"),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert result.overall_pass
        assert result.checks[0].passed

    @pytest.mark.asyncio
    async def test_file_contains_pass(self, artifacts_dir: Path):
        """Test file_contains check passes when pattern matches."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(
                type=CheckType.FILE_CONTAINS,
                path="output.txt",
                pattern="Hello",
            ),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert result.overall_pass
        assert result.checks[0].passed

    @pytest.mark.asyncio
    async def test_file_contains_fail(self, artifacts_dir: Path):
        """Test file_contains check fails when pattern doesn't match."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(
                type=CheckType.FILE_CONTAINS,
                path="output.txt",
                pattern="Goodbye",
            ),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert not result.overall_pass
        assert not result.checks[0].passed

    @pytest.mark.asyncio
    async def test_file_contains_regex(self, artifacts_dir: Path):
        """Test file_contains check with regex pattern."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(
                type=CheckType.FILE_CONTAINS,
                path="data.json",
                pattern=r'"success":\s*true',
            ),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert result.overall_pass

    @pytest.mark.asyncio
    async def test_trajectory_contains_pass(self, artifacts_dir: Path):
        """Test trajectory_contains check passes when pattern found."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(
                type=CheckType.TRAJECTORY_CONTAINS,
                pattern="npm install",
            ),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert result.overall_pass

    @pytest.mark.asyncio
    async def test_trajectory_contains_fail(self, artifacts_dir: Path):
        """Test trajectory_contains check fails when pattern not found."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(
                type=CheckType.TRAJECTORY_CONTAINS,
                pattern="pip install",
            ),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert not result.overall_pass

    @pytest.mark.asyncio
    async def test_command_executed_pass(self, artifacts_dir: Path):
        """Test command_executed check extracts commands correctly."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(
                type=CheckType.COMMAND_EXECUTED,
                pattern="npm install",
            ),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert result.overall_pass

    @pytest.mark.asyncio
    async def test_multiple_checks(self, artifacts_dir: Path):
        """Test multiple checks with partial pass."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(type=CheckType.FILE_EXISTS, path="output.txt"),
            DeterministicCheck(type=CheckType.FILE_EXISTS, path="missing.txt"),
            DeterministicCheck(type=CheckType.FILE_CONTAINS, path="output.txt", pattern="Hello"),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert not result.overall_pass  # One check failed
        assert result.score == pytest.approx(66.67, rel=0.1)  # 2/3 passed
        assert result.checks[0].passed
        assert not result.checks[1].passed
        assert result.checks[2].passed

    @pytest.mark.asyncio
    async def test_score_metadata(self, artifacts_dir: Path):
        """Test that score result includes proper metadata."""
        config = DeterministicScorerConfig(checks=[
            DeterministicCheck(type=CheckType.FILE_EXISTS, path="output.txt"),
        ])
        scorer = DeterministicScorer(config)
        
        result = await scorer.score(artifacts_dir)
        
        assert result.metadata["scorer"] == "deterministic"
        assert result.metadata["version"] == "1.0"
        assert "duration_ms" in result.metadata
        assert result.metadata["checks_passed"] == 1
        assert result.metadata["checks_total"] == 1


class TestScoreResult:
    """Test ScoreResult dataclass."""

    def test_to_dict(self):
        """Test converting score result to dict."""
        result = ScoreResult(
            overall_pass=True,
            score=100.0,
            checks=[
                CheckResult(id="check1", passed=True, notes="OK"),
                CheckResult(id="check2", passed=True, notes="", details={"key": "value"}),
            ],
            metadata={"scorer": "test"},
        )
        
        d = result.to_dict()
        
        assert d["overall_pass"] is True
        assert d["score"] == 100.0
        assert len(d["checks"]) == 2
        assert d["checks"][0]["id"] == "check1"
        assert d["checks"][0]["pass"] is True
        assert d["checks"][1]["details"]["key"] == "value"
        assert d["metadata"]["scorer"] == "test"

    def test_from_dict(self):
        """Test creating score result from dict."""
        d = {
            "overall_pass": False,
            "score": 50.0,
            "checks": [
                {"id": "check1", "pass": True, "notes": "OK"},
                {"id": "check2", "pass": False, "notes": "Failed"},
            ],
            "metadata": {"scorer": "test"},
        }
        
        result = ScoreResult.from_dict(d)
        
        assert result.overall_pass is False
        assert result.score == 50.0
        assert len(result.checks) == 2
        assert result.checks[0].passed is True
        assert result.checks[1].passed is False
