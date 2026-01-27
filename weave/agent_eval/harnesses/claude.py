"""Anthropic Claude Code harness adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import HarnessAdapter
from .registry import register_harness

if TYPE_CHECKING:
    from ..config.schema import HarnessConfig


@register_harness("claude")
class ClaudeAdapter(HarnessAdapter):
    """Adapter for Anthropic Claude Code CLI."""

    @property
    def name(self) -> str:
        return "claude"

    def required_env_keys(self, config: HarnessConfig) -> list[str]:
        return ["ANTHROPIC_API_KEY"]

    def build_command(
        self,
        prompt: str,
        skill_path: str,
        workdir: str,
        timeout: int,
        model: str,
        extra_args: list[str],
    ) -> list[str]:
        """Build claude command."""
        cmd = [
            "claude",
            "--print",  # Print output to stdout
            "--output-format", "json",  # JSON output
            "--model", model,
            "--max-turns", "100",  # Reasonable default
        ]

        # Add any extra arguments
        cmd.extend(extra_args)

        # Add the prompt
        cmd.extend(["--prompt", prompt])

        return cmd

    def get_adapter_script_path(self) -> Path | None:
        """Return path to claude adapter script."""
        adapter_path = Path(__file__).parent.parent.parent / "agent_eval_adapters" / "claude-adapter.sh"
        if adapter_path.exists():
            return adapter_path
        return None

    def get_setup_commands(self) -> list[str]:
        """Return setup commands to install Claude CLI."""
        return [
            "npm install -g @anthropic-ai/claude-code",
        ]
