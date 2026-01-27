"""OpenCode harness adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import HarnessAdapter
from .registry import register_harness

if TYPE_CHECKING:
    from ..config.schema import HarnessConfig


@register_harness("opencode")
class OpenCodeAdapter(HarnessAdapter):
    """Adapter for OpenCode CLI."""

    @property
    def name(self) -> str:
        return "opencode"

    def required_env_keys(self, config: HarnessConfig) -> list[str]:
        # OpenCode can use either OpenAI or Anthropic
        # Return both, but only one needs to be present based on model
        if "claude" in config.model.lower():
            return ["ANTHROPIC_API_KEY"]
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
        """Build opencode command."""
        cmd = [
            "opencode",
            "exec",
            "--json",  # Output JSON
            "--model", model,
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
        """Return path to opencode adapter script."""
        adapter_path = Path(__file__).parent.parent.parent / "agent_eval_adapters" / "opencode-adapter.sh"
        if adapter_path.exists():
            return adapter_path
        return None

    def get_setup_commands(self) -> list[str]:
        """Return setup commands to install OpenCode CLI."""
        return [
            "npm install -g @anomalyco/opencode",
        ]
