"""OpenAI Agent harness adapter.

A simple agent that uses the OpenAI API directly via Node.js.
This works reliably in Docker containers where Codex CLI has networking issues.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import HarnessAdapter
from .registry import register_harness

if TYPE_CHECKING:
    from ..config.schema import HarnessConfig


@register_harness("openai-agent")
class OpenAIAgentAdapter(HarnessAdapter):
    """Adapter for the simple OpenAI API-based agent.
    
    This agent uses Node.js to call the OpenAI API directly, which works
    reliably in Docker containers (unlike Codex CLI which has Rust HTTP issues).
    
    The agent supports:
      - Executing shell commands
      - Reading/writing files
      - Listing directory contents
    """

    @property
    def name(self) -> str:
        return "openai-agent"

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
        """Build command to run the OpenAI agent adapter."""
        # The adapter script handles everything via environment variables
        return ["node", "/usr/local/bin/openai-agent-adapter.js"]

    def build_env(
        self,
        prompt: str,
        skill_path: str,
        workdir: str,
        timeout: int,
        model: str | None = None,
    ) -> dict[str, str]:
        """Build environment variables for the agent."""
        env = {
            "AGENT_EVAL_PROMPT": prompt,
            "AGENT_EVAL_SKILL_PATH": skill_path,
            "AGENT_EVAL_WORKDIR": workdir,
            "AGENT_EVAL_TIMEOUT": str(timeout),
        }
        if model:
            env["AGENT_EVAL_MODEL"] = model
        return env

    def get_adapter_script_path(self) -> Path | None:
        """Return path to the Node.js adapter script."""
        adapter_path = Path(__file__).parent.parent.parent / "agent_eval_adapters" / "openai-agent-adapter.js"
        if adapter_path.exists():
            return adapter_path
        return None

    def get_setup_commands(self) -> list[str]:
        """No additional setup needed - Node.js is in the base image."""
        return []
