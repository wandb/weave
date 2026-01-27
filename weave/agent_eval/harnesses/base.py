"""Base harness adapter protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.schema import HarnessConfig


class HarnessAdapter(ABC):
    """Abstract base class for harness adapters.

    A harness adapter normalizes different agent CLIs to a common interface.
    Each adapter knows how to:
    - Declare required environment variables
    - Build the command to run inside a container
    - Provide an optional shell adapter script
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the harness name (e.g., 'codex', 'claude')."""
        ...

    @abstractmethod
    def required_env_keys(self, config: HarnessConfig) -> list[str]:
        """Return environment variable names this harness requires.

        Args:
            config: The harness configuration.

        Returns:
            List of required environment variable names.
        """
        ...

    @abstractmethod
    def build_command(
        self,
        prompt: str,
        skill_path: str,
        workdir: str,
        timeout: int,
        model: str,
        extra_args: list[str],
    ) -> list[str]:
        """Build the command to run inside the container.

        Args:
            prompt: The user prompt to execute.
            skill_path: Path to skill directory inside container.
            workdir: Working directory inside container.
            timeout: Timeout in seconds.
            model: Model identifier to use.
            extra_args: Additional CLI arguments.

        Returns:
            Command as list of strings.
        """
        ...

    def get_adapter_script_path(self) -> Path | None:
        """Return path to shell adapter script, if any.

        Override this to provide a shell script that wraps the CLI.
        The script will be copied to /usr/local/bin/adapter.sh in the container.

        Returns:
            Path to adapter script, or None if not needed.
        """
        return None

    def get_base_image(self) -> str:
        """Return recommended base image for this harness.

        Override this to specify a different default base image.

        Returns:
            Docker image name.
        """
        return "python:3.12-slim"

    def get_setup_commands(self) -> list[str]:
        """Return setup commands to run during image build.

        Override this to install harness dependencies.

        Returns:
            List of shell commands.
        """
        return []

    def build_env(
        self,
        prompt: str,
        skill_path: str,
        workdir: str,
        timeout: int,
        model: str | None = None,
    ) -> dict[str, str]:
        """Build environment variables for the harness.

        Returns standard AGENT_EVAL_* variables that adapter scripts can use.

        Args:
            prompt: The user prompt.
            skill_path: Path to skill directory.
            workdir: Working directory.
            timeout: Timeout in seconds.
            model: Model identifier (optional).

        Returns:
            Dictionary of environment variables.
        """
        env = {
            "AGENT_EVAL_PROMPT": prompt,
            "AGENT_EVAL_SKILL_PATH": skill_path,
            "AGENT_EVAL_WORKDIR": workdir,
            "AGENT_EVAL_TIMEOUT": str(timeout),
        }
        if model:
            env["AGENT_EVAL_MODEL"] = model
        return env
