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
    """Adapter for OpenAI Codex CLI.
    
    Codex CLI reference: https://github.com/openai/codex
    
    Key flags:
      --json           Output JSONL trajectory to stdout
      --full-auto      Sandboxed automatic execution (workspace-write)
      --model MODEL    Model to use
      -C DIR           Working directory
    
    Note: Codex doesn't have --timeout or --skills-path flags.
    Skills are loaded from .codex/skills/ in the working directory.
    """

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
        """Build codex exec command.
        
        Note: timeout is handled at the Docker level, not by codex itself.
        Skills must be copied to .codex/skills/ in the workspace.
        """
        cmd = [
            "codex",
            "exec",
            "--json",  # Output JSONL trajectory
            "--full-auto",  # Sandboxed automatic execution
            "--skip-git-repo-check",  # Allow running outside git repo
            "--model", model,
        ]

        # Add any extra arguments
        cmd.extend(extra_args)

        # Add the prompt last
        cmd.append(prompt)

        return cmd

    def get_adapter_script_path(self) -> Path | None:
        """Return path to codex adapter script."""
        adapter_path = Path(__file__).parent.parent / "adapters" / "codex-adapter.sh"
        if adapter_path.exists():
            return adapter_path
        return None

    def get_setup_commands(self) -> list[str]:
        """Return setup commands to install Codex CLI."""
        return [
            "npm install -g @openai/codex",
        ]
