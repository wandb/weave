"""Tests for agent-specific tool registries."""

import pytest

from weave.integrations.ag_ui.tools import get_tool_registry
from weave.integrations.ag_ui.tools.claude import CLAUDE_TOOL_REGISTRY


class TestToolRegistry:
    def test_get_claude_registry(self):
        registry = get_tool_registry("Claude Code")
        assert registry is not None
        assert "Task" in registry
        assert "Edit" in registry

    def test_get_unknown_registry(self):
        registry = get_tool_registry("Unknown Agent")
        assert registry == {}  # Empty registry for unknown agents

    def test_claude_task_spawns_subagent(self):
        registry = get_tool_registry("Claude Code")
        task_config = registry.get("Task", {})
        assert task_config.get("spawns_subagent") is True

    def test_claude_edit_has_diff_view(self):
        registry = get_tool_registry("Claude Code")
        edit_config = registry.get("Edit", {})
        assert edit_config.get("has_diff_view") is True

    def test_claude_ask_user_question_is_qa_flow(self):
        registry = get_tool_registry("Claude Code")
        ask_config = registry.get("AskUserQuestion", {})
        assert ask_config.get("is_qa_flow") is True


class TestClaudeToolRegistry:
    def test_registry_has_expected_tools(self):
        expected_tools = [
            "Task",
            "Edit",
            "Write",
            "Read",
            "Bash",
            "Glob",
            "Grep",
            "TodoWrite",
            "Skill",
            "AskUserQuestion",
            "WebFetch",
            "WebSearch",
        ]
        for tool in expected_tools:
            assert tool in CLAUDE_TOOL_REGISTRY, f"Missing tool: {tool}"
