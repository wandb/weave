"""Tests for harness adapters."""

import pytest

from agent_eval.config.schema import HarnessConfig, HarnessType
from agent_eval.harnesses.registry import get_harness, list_harnesses
from agent_eval.harnesses.codex import CodexAdapter
from agent_eval.harnesses.claude import ClaudeAdapter
from agent_eval.harnesses.opencode import OpenCodeAdapter
from agent_eval.harnesses.generic import GenericAdapter


class TestHarnessRegistry:
    """Test harness registration and retrieval."""

    def test_list_harnesses(self):
        """Test that all expected harnesses are registered."""
        harnesses = list_harnesses()
        
        assert "codex" in harnesses
        assert "claude" in harnesses
        assert "opencode" in harnesses
        assert "generic" in harnesses

    def test_get_codex_harness(self):
        """Test getting codex harness adapter."""
        config = HarnessConfig(type=HarnessType.CODEX, model="gpt-4o")
        adapter = get_harness(config)
        
        assert isinstance(adapter, CodexAdapter)
        assert adapter.name == "codex"

    def test_get_claude_harness(self):
        """Test getting claude harness adapter."""
        config = HarnessConfig(type=HarnessType.CLAUDE, model="claude-sonnet-4-20250514")
        adapter = get_harness(config)
        
        assert isinstance(adapter, ClaudeAdapter)
        assert adapter.name == "claude"

    def test_unknown_harness_raises(self):
        """Test that unknown harness type raises error."""
        # This shouldn't happen due to enum validation, but test anyway
        config = HarnessConfig(type=HarnessType.CODEX, model="test")
        config.type = "unknown"  # type: ignore
        
        with pytest.raises(ValueError, match="Unknown harness type"):
            get_harness(config)


class TestCodexAdapter:
    """Test Codex harness adapter."""

    def test_required_env_keys(self):
        """Test required environment variables."""
        config = HarnessConfig(type=HarnessType.CODEX, model="gpt-4o")
        adapter = CodexAdapter()
        
        keys = adapter.required_env_keys(config)
        assert "OPENAI_API_KEY" in keys

    def test_build_command_basic(self):
        """Test basic command building."""
        adapter = CodexAdapter()
        
        cmd = adapter.build_command(
            prompt="Create a file",
            skill_path="/skill",
            workdir="/workspace",
            timeout=300,
            model="gpt-4o",
            extra_args=[],
        )
        
        assert cmd[0] == "codex"
        assert cmd[1] == "exec"
        assert "--json" in cmd
        assert "--full-auto" in cmd
        assert "--skip-git-repo-check" in cmd  # Required for running in containers
        assert "--model" in cmd
        assert "gpt-4o" in cmd
        assert "Create a file" in cmd
        
        # Should NOT have --timeout (not supported by codex)
        assert "--timeout" not in cmd
        # Should NOT have --skills-path (not supported by codex)
        assert "--skills-path" not in cmd

    def test_build_command_with_extra_args(self):
        """Test command building with extra arguments."""
        adapter = CodexAdapter()
        
        cmd = adapter.build_command(
            prompt="Do something",
            skill_path="/skill",
            workdir="/workspace",
            timeout=60,
            model="o3",
            extra_args=["--sandbox", "danger-full-access"],
        )
        
        assert "--sandbox" in cmd
        assert "danger-full-access" in cmd

    def test_prompt_is_last(self):
        """Test that prompt is the last argument."""
        adapter = CodexAdapter()
        
        cmd = adapter.build_command(
            prompt="The prompt text",
            skill_path="/skill",
            workdir="/workspace",
            timeout=300,
            model="gpt-4o",
            extra_args=[],
        )
        
        assert cmd[-1] == "The prompt text"


class TestClaudeAdapter:
    """Test Claude harness adapter."""

    def test_required_env_keys(self):
        """Test required environment variables."""
        config = HarnessConfig(type=HarnessType.CLAUDE, model="claude-sonnet")
        adapter = ClaudeAdapter()
        
        keys = adapter.required_env_keys(config)
        assert "ANTHROPIC_API_KEY" in keys

    def test_build_command(self):
        """Test command building."""
        adapter = ClaudeAdapter()
        
        cmd = adapter.build_command(
            prompt="Create a file",
            skill_path="/skill",
            workdir="/workspace",
            timeout=300,
            model="claude-sonnet-4-20250514",
            extra_args=[],
        )
        
        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--model" in cmd
        assert "claude-sonnet-4-20250514" in cmd


class TestOpenCodeAdapter:
    """Test OpenCode harness adapter."""

    def test_required_env_keys_openai_model(self):
        """Test required env keys for OpenAI model."""
        config = HarnessConfig(type=HarnessType.OPENCODE, model="gpt-4o")
        adapter = OpenCodeAdapter()
        
        keys = adapter.required_env_keys(config)
        assert "OPENAI_API_KEY" in keys

    def test_required_env_keys_claude_model(self):
        """Test required env keys for Claude model."""
        config = HarnessConfig(type=HarnessType.OPENCODE, model="claude-sonnet")
        adapter = OpenCodeAdapter()
        
        keys = adapter.required_env_keys(config)
        assert "ANTHROPIC_API_KEY" in keys


class TestGenericAdapter:
    """Test Generic harness adapter."""

    def test_required_env_keys_empty(self):
        """Test that generic adapter has no required keys."""
        config = HarnessConfig(type=HarnessType.GENERIC, model="custom")
        adapter = GenericAdapter()
        
        keys = adapter.required_env_keys(config)
        assert keys == []

    def test_build_command_uses_adapter_script(self):
        """Test that generic adapter uses adapter script."""
        adapter = GenericAdapter()
        
        cmd = adapter.build_command(
            prompt="Do something",
            skill_path="/skill",
            workdir="/workspace",
            timeout=60,
            model="custom",
            extra_args=["--custom-flag"],
        )
        
        assert cmd[0] == "/usr/local/bin/adapter.sh"
        assert "--custom-flag" in cmd
