"""Weave CLI.

Entry point for the weave command line interface.

Usage:
    weave claude hook      # Handle Claude Code hook events (reads from stdin)
    weave claude import    # Import historic Claude sessions into Weave
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


@claude.command("import")
@click.argument("path", type=click.Path(exists=True))
@click.argument("project")
@click.option(
    "--full",
    is_flag=True,
    help="Import ALL sessions (default: most recent only)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be imported without importing",
)
@click.option(
    "--no-ollama",
    is_flag=True,
    help="Skip Ollama for display names",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show details for each session",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging (logs to /tmp/weave-import-debug.log)",
)
def import_sessions_cmd(
    path: str,
    project: str,
    full: bool,
    dry_run: bool,
    no_ollama: bool,
    verbose: bool,
    debug: bool,
) -> None:
    """Import historic Claude Code sessions into Weave.

    PATH can be a single session .jsonl file or a directory containing sessions.
    When given a directory, only UUID-named session files are imported (agent-*
    files are skipped).

    PROJECT should be in "entity/project" format (e.g., "myteam/claude-sessions").

    By default, only the most recent session is imported. Use --full to import
    all sessions in the directory.

    Examples:

        # Import most recent session from a directory
        weave claude import ~/.claude/projects/myproject vanpelt/sessions

        # Import a specific session file
        weave claude import /path/to/session.jsonl vanpelt/sessions

        # Import all sessions
        weave claude import ~/.claude/projects/myproject vanpelt/sessions --full

        # Dry run to see what would be imported
        weave claude import ~/.claude/projects/myproject vanpelt/sessions --dry-run
    """
    from pathlib import Path

    from weave.integrations.claude_plugin.cli_output import (
        ImportResult,
        ImportSummary,
        get_output,
        suppress_verbose_logging,
    )
    from weave.integrations.claude_plugin.session_importer import (
        discover_session_files,
        import_session_with_result,
        init_weave_quiet,
    )

    output = get_output(verbose=verbose)

    try:
        # Discover session files
        session_path = Path(path)
        if session_path.is_file():
            session_files = [session_path]
        elif session_path.is_dir():
            session_files = discover_session_files(session_path, most_recent_only=not full)
        else:
            raise ValueError(f"Path does not exist: {path}")

        if not session_files:
            raise ValueError("No session files found (only UUID-named files are imported, agent-* files are skipped)")

        output.print_starting(len(session_files), project, dry_run)

        # Import sessions with progress tracking
        results: list[ImportResult] = []
        is_single_session = len(session_files) == 1

        with suppress_verbose_logging(debug=debug):
            # Initialize weave (unless dry run)
            if not dry_run:
                init_weave_quiet(project)

            if is_single_session:
                # Single session: use line-based progress and include details for visualization
                session_file = session_files[0]

                # Count lines for progress bar
                try:
                    with open(session_file) as f:
                        total_lines = sum(1 for _ in f)
                except Exception:
                    total_lines = 100  # Fallback estimate

                # For single session, use simpler progress (line tracking would require parser changes)
                # Just show a spinner while importing
                if hasattr(output, "line_progress_context"):
                    with output.line_progress_context(total_lines, session_file.name) as update_progress:
                        # Update progress at start
                        update_progress(0, 1, "Starting...")
                        result = import_session_with_result(
                            session_path=session_file,
                            dry_run=dry_run,
                            use_ollama=not no_ollama,
                            include_details=True,
                        )
                        # Update progress at end
                        update_progress(total_lines, result.turns, "Complete")
                        results.append(result)
                else:
                    result = import_session_with_result(
                        session_path=session_file,
                        dry_run=dry_run,
                        use_ollama=not no_ollama,
                        include_details=True,
                    )
                    results.append(result)
            else:
                # Multiple sessions: use session-based progress, skip details to save memory
                if hasattr(output, "progress_context"):
                    with output.progress_context(len(session_files)) as progress:
                        if progress is not None:
                            task = progress.add_task("Importing sessions...", total=len(session_files))
                            for session_file in session_files:
                                result = import_session_with_result(
                                    session_path=session_file,
                                    dry_run=dry_run,
                                    use_ollama=not no_ollama,
                                    include_details=False,
                                )
                                results.append(result)
                                output.print_session_result(result, dry_run=dry_run)
                                progress.update(task, advance=1, description=f"Importing {session_file.name[:20]}...")
                        else:
                            # BasicOutput fallback
                            for session_file in session_files:
                                result = import_session_with_result(
                                    session_path=session_file,
                                    dry_run=dry_run,
                                    use_ollama=not no_ollama,
                                    include_details=False,
                                )
                                results.append(result)
                                output.print_session_result(result, dry_run=dry_run)
                else:
                    for session_file in session_files:
                        result = import_session_with_result(
                            session_path=session_file,
                            dry_run=dry_run,
                            use_ollama=not no_ollama,
                            include_details=False,
                        )
                        results.append(result)
                        output.print_session_result(result, dry_run=dry_run)

        # Build summary
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Get traces URL
        traces_url = None
        if not dry_run and successful:
            try:
                from weave.trace.context.weave_client_context import require_weave_client
                client = require_weave_client()
                traces_url = f"https://wandb.ai/{client.entity}/{client.project}/weave/traces"
            except Exception:
                if "/" in project:
                    entity, proj = project.split("/", 1)
                    traces_url = f"https://wandb.ai/{entity}/{proj}/weave/traces"

        summary = ImportSummary(
            sessions_imported=len(successful),
            sessions_failed=len(failed),
            total_turns=sum(r.turns for r in successful),
            total_tool_calls=sum(r.tool_calls for r in successful),
            total_weave_calls=sum(r.weave_calls for r in successful),
            total_tokens=sum(r.tokens for r in successful),
            traces_url=traces_url,
            dry_run=dry_run,
            results=results,
        )

        output.print_summary(summary)

        if debug:
            click.echo("\nDebug log written to: /tmp/weave-import-debug.log")

    except ValueError as e:
        output.print_error(str(e))
        sys.exit(1)
    except Exception as e:
        output.print_error(str(e))
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


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
