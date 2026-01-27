"""Generic harness adapter for custom CLIs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .base import HarnessAdapter
from .registry import register_harness

if TYPE_CHECKING:
    from ..config.schema import HarnessConfig


@register_harness("generic")
class GenericAdapter(HarnessAdapter):
    """Adapter for generic/custom agent CLIs.

    The generic adapter uses a shell adapter script that must be provided.
    The script receives standard AGENT_EVAL_* environment variables.
    """

    @property
    def name(self) -> str:
        return "generic"

    def required_env_keys(self, config: HarnessConfig) -> list[str]:
        # Generic adapter doesn't know what keys are needed
        # Users should specify via environment.additional_env_keys
        return []

    def build_command(
        self,
        prompt: str,
        skill_path: str,
        workdir: str,
        timeout: int,
        model: str,
        extra_args: list[str],
    ) -> list[str]:
        """Build command using adapter script.

        The generic adapter relies on the adapter script to handle
        the actual command execution. Environment variables are passed
        via build_env().
        """
        # Just run the adapter script - it will use env vars
        return ["/usr/local/bin/adapter.sh"] + extra_args

    def get_adapter_script_path(self) -> Path | None:
        """Generic adapter requires user to provide script via config."""
        return None

    def get_setup_commands(self) -> list[str]:
        """No default setup for generic adapter."""
        return []
