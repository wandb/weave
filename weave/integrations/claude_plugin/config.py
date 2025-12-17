#!/usr/bin/env python3
"""Configuration management for Claude Code plugin.

This module manages the global enabled/disabled state of the Weave tracing
plugin, separate from per-session state. It also supports local project
overrides via .claude/settings.json.

Configuration is stored in:
- Global: ~/.cache/weave/config.json
- Local: $CWD/.claude/settings.json (weave.enabled key)

Priority order (highest first):
1. Local settings.json weave.enabled (if key exists)
2. Global config.json enabled
3. Default: false (disabled)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Global config file location
CONFIG_DIR = Path.home() / ".cache" / "weave"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _read_config() -> dict[str, Any]:
    """Read global config file, returning defaults if not exists."""
    if not CONFIG_FILE.exists():
        return {"enabled": False}

    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"enabled": False}


def _write_config(config: dict[str, Any]) -> None:
    """Write config file atomically."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = CONFIG_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w") as f:
            json.dump(config, f, indent=2)
        temp_file.rename(CONFIG_FILE)
    except OSError:
        if temp_file.exists():
            temp_file.unlink()


def get_enabled() -> bool:
    """Get global enabled state.

    Returns:
        True if globally enabled, False otherwise (default: False)
    """
    config = _read_config()
    return config.get("enabled", False)


def set_enabled(enabled: bool) -> None:
    """Set global enabled state.

    Args:
        enabled: True to enable, False to disable
    """
    config = _read_config()
    config["enabled"] = enabled
    _write_config(config)


def get_local_enabled(cwd: str | None = None) -> bool | None:
    """Check local settings for weave.enabled.

    Args:
        cwd: Working directory to check, defaults to current directory

    Returns:
        True/False if weave.enabled is set, None if not set
    """
    if cwd is None:
        cwd = os.getcwd()

    settings_path = Path(cwd) / ".claude" / "settings.json"
    if not settings_path.exists():
        return None

    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    weave_config = settings.get("weave")
    if not isinstance(weave_config, dict):
        return None

    enabled = weave_config.get("enabled")
    if isinstance(enabled, bool):
        return enabled

    return None


def set_local_enabled(enabled: bool, cwd: str | None = None) -> None:
    """Set weave.enabled in local settings.json.

    Creates .claude/settings.json if it doesn't exist.

    Args:
        enabled: True to enable, False to disable
        cwd: Working directory, defaults to current directory
    """
    if cwd is None:
        cwd = os.getcwd()

    settings_dir = Path(cwd) / ".claude"
    settings_path = settings_dir / "settings.json"

    # Read existing settings or start fresh
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError):
            settings = {}

    # Ensure weave section exists
    if "weave" not in settings or not isinstance(settings["weave"], dict):
        settings["weave"] = {}

    settings["weave"]["enabled"] = enabled

    # Write atomically
    settings_dir.mkdir(parents=True, exist_ok=True)
    temp_file = settings_path.with_suffix(".tmp")
    try:
        with open(temp_file, "w") as f:
            json.dump(settings, f, indent=2)
        temp_file.rename(settings_path)
    except OSError:
        if temp_file.exists():
            temp_file.unlink()


def is_enabled(cwd: str | None = None) -> bool:
    """Check if tracing is enabled for the given directory.

    Checks local override first, then falls back to global setting.

    Args:
        cwd: Working directory to check, defaults to current directory

    Returns:
        True if tracing should be enabled, False otherwise
    """
    # Local override takes precedence
    local = get_local_enabled(cwd)
    if local is not None:
        return local

    # Fall back to global setting (defaults to False)
    return get_enabled()


def get_status(cwd: str | None = None) -> dict[str, Any]:
    """Get comprehensive status information.

    Args:
        cwd: Working directory to check, defaults to current directory

    Returns:
        Dict with global, local, effective, and project info
    """
    if cwd is None:
        cwd = os.getcwd()

    global_enabled = get_enabled()
    local_enabled = get_local_enabled(cwd)
    effective = is_enabled(cwd)
    project = os.environ.get("WEAVE_PROJECT")

    return {
        "global": global_enabled,
        "local": local_enabled,  # None if not set
        "effective": effective,
        "project": project,
        "cwd": cwd,
    }


def has_local_settings(cwd: str | None = None) -> bool:
    """Check if .claude/settings.json exists in the given directory.

    Args:
        cwd: Working directory to check, defaults to current directory

    Returns:
        True if .claude/settings.json exists
    """
    if cwd is None:
        cwd = os.getcwd()

    settings_path = Path(cwd) / ".claude" / "settings.json"
    return settings_path.exists()


def main() -> int:
    """CLI interface for config management.

    Usage:
        python -m weave.integrations.claude_plugin.config <command> [options]

    Commands:
        enable [--global]   Enable tracing (locally by default, globally with --global)
        disable [--global]  Disable tracing
        status              Show current status
    """
    if len(sys.argv) < 2:
        print("Usage: python -m weave.integrations.claude_plugin.config <command>")
        print("Commands: enable, disable, status")
        return 1

    command = sys.argv[1]
    global_flag = "--global" in sys.argv

    if command == "enable":
        if global_flag:
            set_enabled(True)
            print("Weave tracing enabled globally (~/.cache/weave/config.json)")
        else:
            set_local_enabled(True)
            print("Weave tracing enabled locally (.claude/settings.json)")
        return 0

    elif command == "disable":
        if global_flag:
            set_enabled(False)
            print("Weave tracing disabled globally (~/.cache/weave/config.json)")
        else:
            set_local_enabled(False)
            print("Weave tracing disabled locally (.claude/settings.json)")
        return 0

    elif command == "status":
        status = get_status()

        print("Weave Tracing Status:")
        print(f"  Global: {'enabled' if status['global'] else 'disabled'}")

        if status["local"] is not None:
            print(f"  Local (.claude/settings.json): {'enabled' if status['local'] else 'disabled'}")
        else:
            print("  Local (.claude/settings.json): not set")

        print(f"  Effective: {'enabled' if status['effective'] else 'disabled'}")
        print(f"  Project: {status['project'] or 'not set'}")
        return 0

    else:
        print(f"Unknown command: {command}")
        print("Commands: enable, disable, status")
        return 1


if __name__ == "__main__":
    sys.exit(main())
