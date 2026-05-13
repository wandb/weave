"""Tests for configuration loading and validation."""

import tempfile
from pathlib import Path

import pytest

from agent_eval.config.loader import load_config, validate_config
from agent_eval.config.schema import (
    CheckType,
    EvalConfig,
    HarnessType,
    DriverType,
)


class TestConfigSchema:
    """Test configuration schema validation."""

    def test_minimal_config(self, tmp_path: Path):
        """Test loading a minimal valid config."""
        config_yaml = """
version: "1.0"
name: test-eval

skill:
  path: ./skill

tasks:
  - id: test-task
    prompt: "Do something"
"""
        config_file = tmp_path / "eval.yaml"
        config_file.write_text(config_yaml)
        
        # Create skill directory
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill")

        config = load_config(config_file)
        
        assert config.name == "test-eval"
        assert config.version == "1.0"
        assert len(config.tasks) == 1
        assert config.tasks[0].id == "test-task"
        assert config.driver.type == DriverType.DOCKER  # default

    def test_full_config(self, tmp_path: Path):
        """Test loading a full config with all options."""
        config_yaml = """
version: "1.0"
name: full-eval
description: A complete evaluation config

matrix:
  harness:
    - type: codex
      model: gpt-4o
    - type: codex
      model: o3

driver:
  type: docker

environment:
  base_image: node:20-slim
  setup:
    - npm install -g something

skill:
  path: ./skill

tasks:
  - id: task-1
    prompt: "First task"
    timeout: 120
    expected_trigger: true
  - id: task-2
    prompt: "Second task"
    timeout: 60

scoring:
  deterministic:
    checks:
      - type: file_exists
        path: output.txt
      - type: file_contains
        path: output.txt
        pattern: "success"
      - type: trajectory_contains
        pattern: "npm install"

output:
  directory: ./results
"""
        config_file = tmp_path / "eval.yaml"
        config_file.write_text(config_yaml)
        
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        config = load_config(config_file)
        
        assert config.name == "full-eval"
        assert len(config.matrix.harness) == 2
        assert config.matrix.harness[0].type == HarnessType.CODEX
        assert config.matrix.harness[0].model == "gpt-4o"
        assert config.environment.base_image == "node:20-slim"
        assert len(config.tasks) == 2
        assert config.tasks[0].timeout == 120
        assert config.scoring.deterministic is not None
        assert len(config.scoring.deterministic.checks) == 3
        assert config.scoring.deterministic.checks[0].type == CheckType.FILE_EXISTS

    def test_matrix_expansion(self, tmp_path: Path):
        """Test that matrix expands correctly."""
        config_yaml = """
version: "1.0"
name: matrix-test

matrix:
  harness:
    - type: codex
      model: gpt-4o
    - type: codex
      model: o3

skill:
  path: ./skill

tasks:
  - id: task-1
    prompt: "Task 1"
  - id: task-2
    prompt: "Task 2"
"""
        config_file = tmp_path / "eval.yaml"
        config_file.write_text(config_yaml)
        
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        config = load_config(config_file)
        combinations = config.expand_matrix()
        
        # 2 harnesses × 2 tasks = 4 combinations
        assert len(combinations) == 4
        
        # Check all combinations exist
        combo_ids = [(h.model, t.id) for h, t in combinations]
        assert ("gpt-4o", "task-1") in combo_ids
        assert ("gpt-4o", "task-2") in combo_ids
        assert ("o3", "task-1") in combo_ids
        assert ("o3", "task-2") in combo_ids

    def test_default_harness_when_no_matrix(self, tmp_path: Path):
        """Test that default harness is used when no matrix specified."""
        config_yaml = """
version: "1.0"
name: no-matrix

skill:
  path: ./skill

tasks:
  - id: task-1
    prompt: "Task 1"
"""
        config_file = tmp_path / "eval.yaml"
        config_file.write_text(config_yaml)
        
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        config = load_config(config_file)
        combinations = config.expand_matrix()
        
        assert len(combinations) == 1
        harness, task = combinations[0]
        assert harness.type == HarnessType.OPENCODE
        assert harness.model == "gpt-4o"


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_missing_skill(self, tmp_path: Path):
        """Test validation fails when skill path doesn't exist."""
        config_yaml = """
version: "1.0"
name: test

skill:
  path: ./nonexistent

tasks:
  - id: task-1
    prompt: "Task"
"""
        config_file = tmp_path / "eval.yaml"
        config_file.write_text(config_yaml)

        is_valid, errors = validate_config(config_file)
        
        assert not is_valid
        assert any("Skill path not found" in e for e in errors)

    def test_validate_valid_config(self, tmp_path: Path):
        """Test validation passes for valid config."""
        config_yaml = """
version: "1.0"
name: test

skill:
  path: ./skill

tasks:
  - id: task-1
    prompt: "Task"
"""
        config_file = tmp_path / "eval.yaml"
        config_file.write_text(config_yaml)
        
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        is_valid, errors = validate_config(config_file)
        
        assert is_valid
        assert len(errors) == 0
