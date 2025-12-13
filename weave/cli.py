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
