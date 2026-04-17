"""Weave CLI entry point.

Provides the ``weave`` command with subcommands for agent session tracing and
other tooling.

Usage::

    weave agent-hooks daemon --project my-project
    weave agent-hooks relay     # called by IDE hooks (reads stdin)
    weave agent-hooks status
    weave agent-hooks stop
"""

from __future__ import annotations

import os
import sys

import click


@click.group()
def main() -> None:
    """Weave developer tools."""


# ---------------------------------------------------------------------------
# weave agent-hooks
# ---------------------------------------------------------------------------

@main.group("agent-hooks")
def agent_hooks() -> None:
    """Instrument IDE agent sessions as OTel traces in Weave.

    Supports Cursor, Claude Code, and Codex via their respective hook systems.
    Requires a running daemon (``weave agent-hooks daemon``) to process events.

    Quick start::

        # 1. Start the daemon (keep it running in a terminal or as a service)
        weave agent-hooks daemon --project my-project

        # 2. Enable hooks in your IDE — Cursor example (~/.cursor/hooks.json):
        weave agent-hooks install-hooks --ide cursor

        # 3. Open Cursor and start chatting — traces appear in Weave!
    """


@agent_hooks.command("daemon")
@click.option(
    "--port",
    type=int,
    default=None,
    envvar="WEAVE_AGENT_HOOKS_PORT",
    help="Port to listen on.  Default: 6346.",
    show_default=True,
)
@click.option(
    "--endpoint",
    default=None,
    envvar="WEAVE_AGENT_HOOKS_ENDPOINT",
    help="Weave GenAI OTLP endpoint.  Default: http://localhost:6345/otel/v1/genai/traces",
)
@click.option(
    "--project",
    default=None,
    envvar="WEAVE_AGENT_HOOKS_PROJECT",
    help="W&B project name.  Default: agent-sessions",
)
@click.option(
    "--entity",
    default=None,
    envvar="WANDB_ENTITY",
    help="W&B entity (user or team).  Default: $WANDB_ENTITY",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Log verbosity.",
    show_default=True,
)
def daemon_cmd(
    port: int | None,
    endpoint: str | None,
    project: str | None,
    entity: str | None,
    log_level: str,
) -> None:
    """Start the agent-hooks daemon.

    The daemon receives hook events from the relay and converts them into OTel
    spans, exported to the Weave GenAI trace server.  Keep it running in a
    terminal or register it as a launchd / systemd service.
    """
    from weave.agent_hooks.daemon import run

    run(
        port=port,
        endpoint=endpoint,
        project=project,
        entity=entity,
        log_level=log_level,
    )


@agent_hooks.command("relay")
@click.option(
    "--port",
    type=int,
    default=None,
    envvar="WEAVE_AGENT_HOOKS_PORT",
    help="Daemon port.  Default: 6346.",
)
def relay_cmd(port: int | None) -> None:
    """Forward a hook event from stdin to the daemon (called by IDE hooks).

    This command is designed to be invoked by IDE hook scripts.  It reads
    one JSON payload from stdin and POSTs it to the running daemon.  It
    exits immediately after forwarding and silently ignores errors so it
    never blocks the IDE.

    Example hooks.json entry::

        "preToolUse": [{"command": "weave agent-hooks relay", "timeout": 5}]
    """
    from weave.agent_hooks.relay import relay

    relay(port=port)


@agent_hooks.command("status")
@click.option(
    "--port",
    type=int,
    default=None,
    envvar="WEAVE_AGENT_HOOKS_PORT",
    help="Daemon port.  Default: 6346.",
)
def status_cmd(port: int | None) -> None:
    """Check whether the daemon is running."""
    import urllib.error
    import urllib.request

    from weave.agent_hooks.daemon import DEFAULT_PORT, is_running, read_pid

    port = port or int(os.environ.get("WEAVE_AGENT_HOOKS_PORT", DEFAULT_PORT))

    if not is_running():
        click.echo("⏹  Daemon is NOT running.", err=False)
        click.echo(
            "   Start it with: weave agent-hooks daemon",
            err=False,
        )
        sys.exit(1)

    pid = read_pid()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/status", timeout=2
        ) as resp:
            data = resp.read()
            click.echo(f"✅  Daemon is running (PID {pid}, port {port}).")
            click.echo(f"   {data.decode()}")
    except urllib.error.URLError:
        click.echo(
            f"⚠️  PID file says daemon is running (PID {pid}) but port {port} "
            "is not responding.  The process may have crashed.",
        )
        sys.exit(1)


@agent_hooks.command("stop")
def stop_cmd() -> None:
    """Stop the running daemon."""
    import signal

    from weave.agent_hooks.daemon import is_running, read_pid

    if not is_running():
        click.echo("⏹  No daemon is running.")
        return

    pid = read_pid()
    try:
        os.kill(pid, signal.SIGTERM)  # type: ignore[arg-type]
        click.echo(f"✅  Sent SIGTERM to PID {pid}.")
    except OSError as exc:
        click.echo(f"❌  Failed to stop daemon: {exc}", err=True)
        sys.exit(1)


@agent_hooks.command("install-hooks")
@click.option(
    "--ide",
    type=click.Choice(["cursor", "claude-code", "codex", "all"], case_sensitive=False),
    default="cursor",
    show_default=True,
    help="Which IDE to configure.",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="Daemon port to embed in hook command.  Default: 6346.",
)
def install_hooks_cmd(ide: str, port: int | None) -> None:
    """Write or update hook configuration for the specified IDE.

    For Cursor this writes ``~/.cursor/hooks.json``.
    For Claude Code this writes ``~/.claude/settings.json`` hooks section.

    Use ``--ide all`` to configure every supported IDE at once.
    """
    from weave.agent_hooks.installer import install

    install(ide=ide, port=port)


if __name__ == "__main__":
    main()
