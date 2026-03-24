"""Install/update IDE hook configuration files.

Writes the correct hooks.json / settings.json entries so that every supported
IDE event is relayed to the running daemon via ``weave agent-hooks relay``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_PORT = 6346

# All Cursor hooks we want to capture
_CURSOR_HOOKS = [
    "sessionStart",
    "sessionEnd",
    "beforeSubmitPrompt",
    "afterAgentResponse",
    "afterAgentThought",
    "preToolUse",
    "postToolUse",
    "postToolUseFailure",
    "afterShellExecution",
    "afterMCPExecution",
    "afterFileEdit",
    "subagentStart",
    "subagentStop",
    "preCompact",
    "stop",
]

# Claude Code hooks that support all handler types (command, http, prompt, agent).
# These can use HTTP hooks for zero-overhead direct POSTs to the daemon.
_CLAUDE_HTTP_HOOKS = [
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "SubagentStop",
    "Stop",
]

# Claude Code hooks that ONLY support type: "command" handlers.
# These must use the relay command, not HTTP.
_CLAUDE_COMMAND_HOOKS = [
    "SessionStart",
    "SessionEnd",
    "Notification",
    "SubagentStart",
    "PreCompact",
    "PostCompact",
]


def _relay_command(port: int) -> str:
    """Return the relay command string for embedding in hook config."""
    # Use absolute path to the weave binary so hooks work regardless of shell PATH
    weave_bin = _find_weave_bin()
    base = f"{weave_bin} agent-hooks relay"
    if port != DEFAULT_PORT:
        base += f" --port {port}"
    return base


def _find_weave_bin() -> str:
    """Locate the installed ``weave`` binary, falling back to module invocation."""
    import shutil

    which = shutil.which("weave")
    if which:
        return which
    # Fallback: invoke via the same Python as the current process
    return f"{sys.executable} -m weave.cli"


def install(ide: str = "cursor", port: int | None = None) -> None:
    """Install hook configuration for the given IDE.

    Args:
        ide: ``"cursor"``, ``"claude-code"``, ``"codex"``, or ``"all"``.
        port: Daemon port.  Default: 6346.
    """
    port = port or DEFAULT_PORT
    targets = ["cursor", "claude-code", "codex"] if ide == "all" else [ide]
    for target in targets:
        if target == "cursor":
            _install_cursor(port)
        elif target == "claude-code":
            _install_claude_code(port)
        elif target == "codex":
            _install_codex(port)


def _install_cursor(port: int) -> None:
    hooks_path = Path.home() / ".cursor" / "hooks.json"
    cmd = _relay_command(port)
    hook_entry = {"command": cmd, "timeout": 5}

    existing: dict = {}
    if hooks_path.exists():
        try:
            existing = json.loads(hooks_path.read_text())
        except json.JSONDecodeError:
            pass  # overwrite malformed file

    hooks: dict = existing.get("hooks", {})

    added = []
    for hook_name in _CURSOR_HOOKS:
        entries: list = hooks.get(hook_name, [])
        # Avoid duplicate entries
        if not any(e.get("command", "").endswith("agent-hooks relay") for e in entries):
            entries.append(hook_entry)
            added.append(hook_name)
        hooks[hook_name] = entries

    existing["version"] = 1
    existing["hooks"] = hooks
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps(existing, indent=2))

    print(f"✅  Cursor hooks installed at {hooks_path}")
    if added:
        print(f"   Added relay to: {', '.join(added)}")
    else:
        print("   Relay was already configured for all hooks.")


def _has_weave_hook(matcher_group: dict) -> bool:
    """Return True if a Claude Code matcher group already contains a weave hook."""
    for handler in matcher_group.get("hooks", []):
        cmd = handler.get("command", "")
        url = handler.get("url", "")
        if "agent-hooks relay" in cmd or "/event" in url:
            return True
    return False


def _install_claude_code(port: int) -> None:
    settings_path = Path.home() / ".claude" / "settings.json"

    daemon_url = f"http://127.0.0.1:{port}/event"
    http_handler: dict = {"type": "http", "url": daemon_url, "timeout": 5}

    cmd = _relay_command(port)
    cmd_handler: dict = {"type": "command", "command": cmd, "timeout": 5}

    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass

    hooks: dict = existing.get("hooks", {})
    added = []

    for hook_name in _CLAUDE_HTTP_HOOKS:
        matcher_groups: list = hooks.get(hook_name, [])
        if not any(_has_weave_hook(mg) for mg in matcher_groups):
            matcher_groups.append({"hooks": [http_handler]})
            added.append(hook_name)
        hooks[hook_name] = matcher_groups

    for hook_name in _CLAUDE_COMMAND_HOOKS:
        matcher_groups = hooks.get(hook_name, [])
        if not any(_has_weave_hook(mg) for mg in matcher_groups):
            matcher_groups.append({"hooks": [cmd_handler]})
            added.append(hook_name)
        hooks[hook_name] = matcher_groups

    existing["hooks"] = hooks
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(existing, indent=2))

    print(f"✅  Claude Code hooks installed at {settings_path}")
    if added:
        print(f"   Added hooks to: {', '.join(added)}")
    else:
        print("   Hooks were already configured for all events.")


def _install_codex(port: int) -> None:
    hooks_path = Path.home() / ".codex" / "hooks.json"
    cmd = _relay_command(port)
    hook_entry = {"command": cmd, "timeout": 5}

    existing: dict = {}
    if hooks_path.exists():
        try:
            existing = json.loads(hooks_path.read_text())
        except json.JSONDecodeError:
            pass

    hooks: dict = existing.get("hooks", {})
    added = []
    for hook_name in _CURSOR_HOOKS:  # Codex uses same schema as Cursor
        entries: list = hooks.get(hook_name, [])
        if not any(e.get("command", "").endswith("agent-hooks relay") for e in entries):
            entries.append(hook_entry)
            added.append(hook_name)
        hooks[hook_name] = entries

    existing["version"] = 1
    existing["hooks"] = hooks
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps(existing, indent=2))

    print(f"✅  Codex hooks installed at {hooks_path}")
    if added:
        print(f"   Added relay to: {', '.join(added)}")
    else:
        print("   Relay was already configured for all hooks.")
