"""Configuration handling for Claude Code Weave Exporter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Plugin root is the parent of the scripts directory
PLUGIN_ROOT = Path(__file__).parent.parent
ENV_FILE = PLUGIN_ROOT / ".env"


def _load_env_file() -> dict[str, str]:
    """Load configuration from .env file in plugin directory."""
    config = {}
    if not ENV_FILE.exists():
        return config

    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=value
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                config[key] = value
    return config


def _get_config_value(env_config: dict[str, str], key: str, default: str = "") -> str:
    """Get config value from .env file (no env var fallback)."""
    return env_config.get(key, default)


@dataclass
class Config:
    """Configuration for the Weave exporter."""

    enabled: bool
    project: str
    api_key: str | None
    debug: bool

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from .env file in plugin directory."""
        env_config = _load_env_file()

        enabled = _get_config_value(env_config, "CC_ENABLED", "true").lower() == "true"

        # CC_WEAVE_PROJECT takes precedence (full entity/project path)
        weave_project = _get_config_value(env_config, "CC_WEAVE_PROJECT")
        if weave_project:
            project = weave_project
        else:
            # Fall back to CC_WEAVE_ENTITY/CC_WEAVE_PROJECT_NAME
            entity = _get_config_value(env_config, "CC_WEAVE_ENTITY")
            project_name = _get_config_value(env_config, "CC_WEAVE_PROJECT_NAME", "claude-code-traces")
            if entity:
                project = f"{entity}/{project_name}"
            else:
                project = project_name

        api_key = _get_config_value(env_config, "CC_WANDB_API_KEY") or None
        debug = _get_config_value(env_config, "CC_DEBUG", "false").lower() == "true"

        # Set WANDB_API_KEY in environment for weave client to use
        if api_key:
            os.environ["WANDB_API_KEY"] = api_key

        return cls(
            enabled=enabled,
            project=project,
            api_key=api_key,
            debug=debug,
        )

    def is_valid(self) -> bool:
        """Check if the configuration is valid for tracing."""
        return self.enabled and bool(self.project)
