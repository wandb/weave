"""Weave CLI.

Entry point for the weave command line interface.

Usage:
    weave claude hook      # Handle Claude Code hook events (reads from stdin)
    weave claude teleport  # Teleport a Claude session to current machine
"""

from __future__ import annotations

import os
import sys

import click


@click.group()
def cli() -> None:
    """Weave - A toolkit for building AI applications."""
    pass


@cli.group()
def claude() -> None:
    """Claude Code integration commands."""
    pass


@claude.command()
def hook() -> None:
    """Handle Claude Code hook events.

    Reads hook payload from stdin and relays events to the daemon process.
    This is typically invoked by Claude Code hooks, not directly by users.

    Required environment variables:
        WEAVE_PROJECT: Weave project in "entity/project" format
    """
    from weave.integrations.claude_plugin.hook import main

    main()


@claude.command()
@click.option(
    "--global",
    "use_global",
    is_flag=True,
    help="Enable globally instead of for this project",
)
def enable(use_global: bool) -> None:
    """Enable Weave tracing for Claude Code sessions.

    By default, enables tracing for the current project by writing to
    .claude/settings.json. Use --global to enable for all projects.
    """
    from weave.integrations.claude_plugin.config import set_enabled, set_local_enabled

    if use_global:
        set_enabled(True)
        click.echo("Weave tracing enabled globally (~/.cache/weave/config.json)")
    else:
        set_local_enabled(True)
        click.echo("Weave tracing enabled locally (.claude/settings.json)")


@claude.command()
@click.option(
    "--global",
    "use_global",
    is_flag=True,
    help="Disable globally instead of for this project",
)
def disable(use_global: bool) -> None:
    """Disable Weave tracing for Claude Code sessions.

    By default, disables tracing for the current project by writing to
    .claude/settings.json. Use --global to disable for all projects.
    """
    from weave.integrations.claude_plugin.config import set_enabled, set_local_enabled

    if use_global:
        set_enabled(False)
        click.echo("Weave tracing disabled globally (~/.cache/weave/config.json)")
    else:
        set_local_enabled(False)
        click.echo("Weave tracing disabled locally (.claude/settings.json)")


@claude.command()
def status() -> None:
    """Show Weave tracing plugin status.

    Displays the current enabled/disabled state for both global and local
    settings, as well as the effective state for the current directory.
    """
    from weave.integrations.claude_plugin.config import get_status

    status_info = get_status()

    click.echo("Weave Tracing Status:")
    click.echo(f"  Global: {'enabled' if status_info['global'] else 'disabled'}")

    if status_info["local"] is not None:
        local_state = "enabled" if status_info["local"] else "disabled"
        click.echo(f"  Local (.claude/settings.json): {local_state}")
    else:
        click.echo("  Local (.claude/settings.json): not set")

    click.echo(f"  Effective: {'enabled' if status_info['effective'] else 'disabled'}")
    click.echo(f"  Project: {status_info['project'] or 'not set'}")


@claude.command()
@click.argument("session_id")
@click.argument("project")
@click.option(
    "--cwd",
    default=None,
    help="Working directory (default: current directory)",
)
@click.option(
    "--skip-git-check",
    is_flag=True,
    help="Skip git verification (dangerous)",
)
def teleport(
    session_id: str,
    project: str,
    cwd: str | None,
    skip_git_check: bool,
) -> None:
    """Teleport a Claude Code session from Weave.

    Fetches session data from Weave, restores files, and downloads the
    session file for resuming with `claude --resume`.

    Arguments:
        SESSION_ID: Session UUID to teleport
        PROJECT: Weave project in "entity/project" format (e.g., "myteam/myproject")

    Example:
        weave claude teleport abc123 myteam/myproject
    """
    from weave.integrations.claude_plugin.teleport import teleport as do_teleport

    working_dir = cwd or os.getcwd()

    success, message = do_teleport(
        session_id=session_id,
        cwd=working_dir,
        project=project,
        skip_git_check=skip_git_check,
    )

    click.echo(message)

    if not success:
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
