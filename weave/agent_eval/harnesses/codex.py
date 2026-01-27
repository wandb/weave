"""OpenAI Codex harness adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import HarnessAdapter
from .registry import register_harness

if TYPE_CHECKING:
    from ..config.schema import HarnessConfig


@register_harness("codex")
class CodexAdapter(HarnessAdapter):
    """Adapter for OpenAI Codex CLI."""

    @property
    def name(self) -> str:
        return "codex"

    def required_env_keys(self, config: HarnessConfig) -> list[str]:
        return ["OPENAI_API_KEY"]

    def build_command(
        self,
        prompt: str,
        skill_path: str,
        workdir: str,
        timeout: int,
        model: str,
        extra_args: list[str],
    ) -> list[str]:
        """Build codex exec command."""
        cmd = [
            "codex",
            "exec",
            "--json",  # Output JSONL trajectory
            "--full-auto",  # Allow file system changes
            "--model", model,
            "--timeout", str(timeout),
        ]

        # Add skills path if provided
        if skill_path:
            cmd.extend(["--skills-path", skill_path])

        # Add any extra arguments
        cmd.extend(extra_args)

        # Add the prompt
        cmd.append(prompt)

        return cmd

    def get_adapter_script_path(self) -> Path | None:
        """Return path to codex adapter script."""
        # Look for adapter in agent_eval_adapters directory
        adapter_path = Path(__file__).parent.parent.parent / "agent_eval_adapters" / "codex-adapter.sh"
        if adapter_path.exists():
            return adapter_path
        return None

    def get_setup_commands(self) -> list[str]:
        """Return setup commands to install Codex CLI."""
        return [
            "npm install -g @openai/codex",
        ]
