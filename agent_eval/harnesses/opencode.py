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
        """Build opencode command.
        
        OpenCode CLI reference:
          opencode run [message..] - run opencode with a message
          --format json            - output raw JSON events
          --model provider/model   - model to use (e.g., openai/gpt-4o)
          --print-logs             - print logs to stderr
        """
        # Model format is provider/model for opencode
        # If model doesn't contain /, assume openai provider
        if "/" not in model:
            model = f"openai/{model}"
        
        cmd = [
            "opencode",
            "run",
            "--format", "json",  # Output JSON events
            "--model", model,
            "--print-logs",  # Print logs for debugging
        ]

        # Add any extra arguments
        cmd.extend(extra_args)

        # Add the prompt as the message
        cmd.append(prompt)

        return cmd

    def get_adapter_script_path(self) -> Path | None:
        """Return path to opencode adapter script."""
        adapter_path = Path(__file__).parent.parent / "adapters" / "opencode-adapter.sh"
        if adapter_path.exists():
            return adapter_path
        return None

    def get_setup_commands(self) -> list[str]:
        """Return setup commands to install OpenCode CLI."""
        return [
            "npm install -g opencode-ai",
        ]
