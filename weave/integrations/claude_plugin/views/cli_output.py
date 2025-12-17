"""Rich CLI output helpers for Claude Code commands.

Provides beautiful terminal output with progress bars, formatted tables,
timeline visualizations, and session details display.
With graceful fallback to basic print when rich is not available.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console
    from rich.progress import Progress

    from weave.integrations.claude_plugin.session.session_parser import Session

# Try to import rich, gracefully degrade if not available
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# Tool category colors for timeline visualization
TOOL_CATEGORIES = {
    # Read/Search - Blue
    "Read": "blue",
    "Grep": "blue",
    "Glob": "blue",
    "WebFetch": "blue",
    "WebSearch": "blue",
    # Write/Modify - Green
    "Write": "green",
    "Edit": "green",
    "NotebookEdit": "green",
    # Execute - Yellow
    "Bash": "yellow",
    "Task": "yellow",
    "KillShell": "yellow",
    # Interact - Magenta
    "TodoWrite": "magenta",
    "AskUserQuestion": "magenta",
    "EnterPlanMode": "magenta",
    "ExitPlanMode": "magenta",
    "Skill": "magenta",
    "SlashCommand": "magenta",
}

CATEGORY_NAMES = {
    "blue": "Read/Search",
    "green": "Write/Modify",
    "yellow": "Execute",
    "magenta": "Interact",
    "dim": "Other",
}


def get_tool_color(tool_name: str) -> str:
    """Get the color for a tool based on its category."""
    return TOOL_CATEGORIES.get(tool_name, "dim")


@dataclass
class TurnStats:
    """Statistics for a single turn, used for timeline visualization."""

    turn_number: int
    duration_ms: int
    tool_counts: dict[str, int] = field(default_factory=dict)

    def tool_color_distribution(self) -> list[tuple[str, float]]:
        """Get distribution of tools by color category as (color, fraction) pairs."""
        color_counts: dict[str, int] = defaultdict(int)
        total = sum(self.tool_counts.values())
        if total == 0:
            return [("dim", 1.0)]

        for tool_name, count in self.tool_counts.items():
            color = get_tool_color(tool_name)
            color_counts[color] += count

        # Sort by count descending for consistent ordering
        return [
            (color, count / total)
            for color, count in sorted(color_counts.items(), key=lambda x: -x[1])
        ]


@dataclass
class TodoItem:
    """A single todo item from TodoWrite."""

    content: str
    status: str  # "pending", "in_progress", "completed"


@dataclass
class FileChangeStats:
    """Statistics about file changes in a session."""

    files_modified: int = 0
    files_created: int = 0
    lines_added: int = 0
    lines_removed: int = 0

    @property
    def total_files(self) -> int:
        return self.files_modified + self.files_created

    def has_changes(self) -> bool:
        return self.total_files > 0 or self.lines_added > 0 or self.lines_removed > 0


@dataclass
class SessionDetails:
    """Detailed session information for rich visualization."""

    turn_stats: list[TurnStats] = field(default_factory=list)
    latest_prompt: str = ""
    latest_response: str = ""
    todos: list[TodoItem] = field(default_factory=list)
    max_duration_ms: int = 0  # For scaling timeline bars
    total_duration_ms: int = 0  # Sum of all turn durations
    file_changes: FileChangeStats = field(default_factory=FileChangeStats)


@dataclass
class ImportProgress:
    """Progress update during session import."""

    session_index: int
    total_sessions: int
    session_name: str
    status: str  # "parsing", "importing", "done", "error"
    turns: int = 0
    tool_calls: int = 0
    current_line: int = 0
    total_lines: int = 0
    current_tool: str = ""


@dataclass
class ImportResult:
    """Result of importing a single session."""

    session_name: str
    session_id: str
    turns: int
    tool_calls: int
    weave_calls: int
    tokens: int
    display_name: str
    success: bool
    error: str | None = None
    # Detailed session info for single-session visualization
    session_details: SessionDetails | None = None
    # Call ID for direct trace link (only populated for single session imports)
    call_id: str | None = None


@dataclass
class ImportSummary:
    """Summary of the entire import operation."""

    sessions_imported: int
    sessions_failed: int
    total_turns: int
    total_tool_calls: int
    total_weave_calls: int
    total_tokens: int
    total_duration_ms: int
    traces_url: str | None
    dry_run: bool
    results: list[ImportResult]


def format_tokens(tokens: int) -> str:
    """Format token count with appropriate suffix."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    return str(tokens)


def format_duration(duration_ms: int) -> str:
    """Format duration in milliseconds to human-readable format.

    Examples:
        500 -> "0.5s"
        1500 -> "1.5s"
        65000 -> "1m 5s"
        3665000 -> "1h 1m"
    """
    if duration_ms < 1000:
        return f"{duration_ms}ms"

    seconds = duration_ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"


def extract_session_details(session: Session) -> SessionDetails:
    """Extract visualization details from a parsed session.

    Args:
        session: Parsed Session object

    Returns:
        SessionDetails with turn stats, latest content, and todos
    """
    details = SessionDetails()

    # Extract turn statistics
    max_duration_ms = 0
    total_duration_ms = 0
    for i, turn in enumerate(session.turns, 1):
        turn_duration_ms = turn.duration_ms()
        max_duration_ms = max(max_duration_ms, turn_duration_ms)
        total_duration_ms += turn_duration_ms

        # Count tools by name
        tool_counts: dict[str, int] = defaultdict(int)
        for tc in turn.all_tool_calls():
            tool_counts[tc.name] += 1

        details.turn_stats.append(
            TurnStats(
                turn_number=i,
                duration_ms=turn_duration_ms,
                tool_counts=dict(tool_counts),
            )
        )

    details.max_duration_ms = max_duration_ms
    details.total_duration_ms = total_duration_ms

    # Extract latest user prompt
    if session.turns:
        last_turn = session.turns[-1]
        details.latest_prompt = last_turn.user_message.content[:500]

        # Extract latest assistant response (text content)
        if last_turn.assistant_messages:
            text_parts = []
            for msg in last_turn.assistant_messages:
                text_parts.extend(msg.text_content)
            if text_parts:
                details.latest_response = "\n".join(text_parts)[:800]

        # Extract latest todos from last TodoWrite call in the session
        for turn in reversed(session.turns):
            for tc in reversed(turn.all_tool_calls()):
                if tc.name == "TodoWrite" and tc.input:
                    todos_data = tc.input.get("todos", [])
                    for todo in todos_data:
                        if isinstance(todo, dict):
                            details.todos.append(
                                TodoItem(
                                    content=todo.get("content", ""),
                                    status=todo.get("status", "pending"),
                                )
                            )
                    if details.todos:
                        break
            if details.todos:
                break

    # Extract file change statistics
    modified_files = session.get_modified_files()
    created_files = session.get_created_files()

    lines_added = 0
    lines_removed = 0

    # Calculate line changes from Edit tool calls
    for turn in session.turns:
        for tc in turn.all_tool_calls():
            if tc.name == "Edit" and tc.input:
                old_string = tc.input.get("old_string", "")
                new_string = tc.input.get("new_string", "")
                # Count lines (split on newlines, handle empty strings)
                old_lines = len(old_string.split("\n")) if old_string else 0
                new_lines = len(new_string.split("\n")) if new_string else 0
                lines_removed += old_lines
                lines_added += new_lines
            elif tc.name == "Write" and tc.input:
                # For new files, count all lines as added
                content = tc.input.get("content", "")
                file_path = tc.input.get("file_path", "")
                if content and file_path in created_files:
                    lines_added += len(content.split("\n"))

    details.file_changes = FileChangeStats(
        files_modified=len(modified_files),
        files_created=len(created_files),
        lines_added=lines_added,
        lines_removed=lines_removed,
    )

    return details


class RichOutput:
    """Rich terminal output for import operations."""

    BAR_WIDTH = 40  # Width of timeline bars in characters

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.console: Console = Console()
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None

    def print_starting(self, session_count: int, project: str, dry_run: bool) -> None:
        """Print import starting message."""
        mode = "[yellow]DRY RUN[/yellow] " if dry_run else ""
        if session_count == 1:
            self.console.print(f"{mode}Importing 1 session to [cyan]{project}[/cyan]")
        else:
            self.console.print(
                f"{mode}Importing {session_count} sessions to [cyan]{project}[/cyan]"
            )

    @contextmanager
    def progress_context(self, total: int) -> Iterator[Progress]:
        """Create a progress bar context."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        ) as progress:
            yield progress

    @contextmanager
    def line_progress_context(
        self, total_lines: int, session_name: str
    ) -> Iterator[Callable[[int, int, str], None]]:
        """Create a line-based progress bar context for single session import.

        Args:
            total_lines: Total number of lines in the session file
            session_name: Name of the session file

        Yields:
            A callback function to update progress: (current_line, turn_number, tool_name)
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task(
                f"Importing {session_name[:30]}...", total=total_lines
            )

            def update_progress(
                current_line: int, turn_number: int, tool_name: str
            ) -> None:
                desc = f"Turn {turn_number}"
                if tool_name:
                    desc += f": {tool_name}"
                progress.update(task, completed=current_line, description=desc)

            yield update_progress

    @contextmanager
    def spinner_context(self, session_name: str) -> Iterator[Callable[[str], None]]:
        """Create a simple spinner context for single session import.

        Args:
            session_name: Name of the session file

        Yields:
            A callback function to update status text
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Importing {session_name[:30]}...", total=None)

            def update_status(status: str) -> None:
                progress.update(task, description=status)

            yield update_status

    def _render_colored_bar(
        self, width: int, color_distribution: list[tuple[str, float]]
    ) -> Text:
        """Render a bar with colored segments based on tool distribution."""
        text = Text()
        remaining_width = width

        for i, (color, fraction) in enumerate(color_distribution):
            segment_width = int(width * fraction)
            # Give remaining width to last segment to handle rounding
            if i == len(color_distribution) - 1:
                segment_width = remaining_width

            if segment_width > 0:
                text.append("█" * segment_width, style=color)
                remaining_width -= segment_width

        return text

    def print_timeline(self, details: SessionDetails) -> None:
        """Print the session timeline with colored tool bars."""
        if not details.turn_stats:
            return

        # Build timeline content
        lines = []
        for stats in details.turn_stats:
            # Calculate bar width proportional to duration
            if details.max_duration_ms > 0:
                bar_width = max(
                    1, int(self.BAR_WIDTH * stats.duration_ms / details.max_duration_ms)
                )
            else:
                bar_width = 1

            # Get color distribution for this turn
            color_dist = stats.tool_color_distribution()

            # Build the line
            turn_label = f"Turn {stats.turn_number:2d}  "
            bar = self._render_colored_bar(bar_width, color_dist)
            padding = " " * (self.BAR_WIDTH - bar_width)
            duration_label = f"  {format_duration(stats.duration_ms)}"

            line = Text()
            line.append(turn_label, style="dim")
            line.append(bar)
            line.append(padding)
            line.append(duration_label, style="dim")
            lines.append(line)

        # Create panel with timeline
        from rich.console import Group

        content = Group(*lines)
        self.console.print()
        self.console.print(
            Panel(content, title="Session Timeline", border_style="cyan")
        )

        # Print legend
        legend = Text()
        for color, name in CATEGORY_NAMES.items():
            legend.append("■ ", style=color)
            legend.append(f"{name}  ", style="dim")
        self.console.print(legend)

    def print_latest_content(self, details: SessionDetails) -> None:
        """Print the latest prompt, response, and todos."""
        # Latest Prompt
        if details.latest_prompt:
            prompt_text = details.latest_prompt
            if len(prompt_text) > 200:
                prompt_text = prompt_text[:200] + "..."
            self.console.print()
            self.console.print(
                Panel(prompt_text, title="Latest Prompt", border_style="blue")
            )

        # Latest Response (render as markdown)
        if details.latest_response:
            response_text = details.latest_response
            if len(response_text) > 300:
                response_text = response_text[:300] + "..."
            try:
                md = Markdown(response_text)
                self.console.print()
                self.console.print(
                    Panel(md, title="Latest Response", border_style="green")
                )
            except Exception:
                # Fallback to plain text if markdown fails
                self.console.print()
                self.console.print(
                    Panel(response_text, title="Latest Response", border_style="green")
                )

        # Todos
        if details.todos:
            todo_lines = []
            for todo in details.todos:
                if todo.status == "completed":
                    icon = "[green]✓[/green]"
                elif todo.status == "in_progress":
                    icon = "[yellow]→[/yellow]"
                else:
                    icon = "[dim]○[/dim]"
                # Truncate long todo content
                content = (
                    todo.content[:60] + "..."
                    if len(todo.content) > 60
                    else todo.content
                )
                todo_lines.append(f"{icon} {content}")

            self.console.print()
            self.console.print(
                Panel("\n".join(todo_lines), title="Todos", border_style="magenta")
            )

    def print_file_changes(self, details: SessionDetails) -> None:
        """Print file change summary if there are changes."""
        fc = details.file_changes
        if not fc.has_changes():
            return

        # Build summary like: "3 files changed  +45 −12"
        parts = []

        # Files count
        file_count = fc.total_files
        if file_count == 1:
            parts.append("1 file changed")
        else:
            parts.append(f"{file_count} files changed")

        # Lines added/removed
        if fc.lines_added > 0:
            parts.append(f"[green]+{fc.lines_added}[/green]")
        if fc.lines_removed > 0:
            parts.append(f"[red]−{fc.lines_removed}[/red]")

        # Show breakdown if we have both modified and created
        breakdown = ""
        if fc.files_modified > 0 and fc.files_created > 0:
            breakdown = f" ({fc.files_modified} modified, {fc.files_created} created)"
        elif fc.files_created > 0:
            breakdown = f" ({fc.files_created} created)"

        self.console.print()
        summary_text = "  ".join(parts) + breakdown
        self.console.print(
            Panel(summary_text, title="File Changes", border_style="yellow")
        )

    def print_session_details(self, details: SessionDetails) -> None:
        """Print full session details (timeline + latest content)."""
        self.print_timeline(details)
        self.print_file_changes(details)
        self.print_latest_content(details)

    def print_summary(self, summary: ImportSummary) -> None:
        """Print a beautiful summary table."""
        # For single session imports with details, show the rich visualization first
        if len(summary.results) == 1 and summary.results[0].session_details:
            self.print_session_details(summary.results[0].session_details)

        # Create main stats table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        prefix = (
            "[yellow]Would import[/yellow]"
            if summary.dry_run
            else "[green]Imported[/green]"
        )
        table.add_row("Sessions", f"{prefix} {summary.sessions_imported}")

        if summary.sessions_failed > 0:
            table.add_row("Failed", f"[red]{summary.sessions_failed}[/red]")

        table.add_row("Turns", str(summary.total_turns))
        table.add_row("Tool Calls", str(summary.total_tool_calls))

        if not summary.dry_run:
            table.add_row("Weave Calls", str(summary.total_weave_calls))

        table.add_row("Tokens", format_tokens(summary.total_tokens))

        if summary.total_duration_ms > 0:
            table.add_row("Duration", format_duration(summary.total_duration_ms))

        # Print table in a panel
        title = "Dry Run Summary" if summary.dry_run else "Import Summary"
        self.console.print()
        self.console.print(
            Panel(
                table,
                title=title,
                border_style="green" if not summary.dry_run else "yellow",
            )
        )

        # Print traces URL if available
        if summary.traces_url and not summary.dry_run:
            self.console.print()
            # For single session imports with call_id, link directly to the trace
            if len(summary.results) == 1 and summary.results[0].call_id:
                call_id = summary.results[0].call_id
                trace_url = f"{summary.traces_url}?peekPath=%2F%3Aid%2F{call_id}"
                self.console.print(
                    f"[bold]View trace:[/bold] [link={trace_url}]{trace_url}[/link]"
                )
            else:
                self.console.print(
                    f"[bold]View traces:[/bold] [link={summary.traces_url}]{summary.traces_url}[/link]"
                )

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[red]Error:[/red] {message}")

    def print_session_result(self, result: ImportResult, dry_run: bool = False) -> None:
        """Print result for a single session (verbose mode only)."""
        if not self.verbose:
            return

        if result.success:
            prefix = (
                "[yellow]Would import[/yellow]"
                if dry_run
                else "[green]Imported[/green]"
            )
            self.console.print(
                f"  {prefix} [dim]{result.session_name}[/dim]: "
                f"{result.turns} turns, {result.tool_calls} tool calls, "
                f"{format_tokens(result.tokens)} tokens"
            )
        else:
            self.console.print(
                f"  [red]Failed[/red] [dim]{result.session_name}[/dim]: {result.error}"
            )


class BasicOutput:
    """Basic terminal output fallback when rich is not available."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose

    def print_starting(self, session_count: int, project: str, dry_run: bool) -> None:
        """Print import starting message."""
        mode = "[DRY RUN] " if dry_run else ""
        if session_count == 1:
            print(f"{mode}Importing 1 session to {project}")
        else:
            print(f"{mode}Importing {session_count} sessions to {project}")

    @contextmanager
    def progress_context(self, total: int) -> Iterator[None]:
        """No-op context for basic output."""
        yield None

    def print_summary(self, summary: ImportSummary) -> None:
        """Print a basic summary."""
        print()
        print("=" * 50)
        title = "Dry Run Summary" if summary.dry_run else "Import Summary"
        print(title)
        print("=" * 50)

        prefix = "Would import" if summary.dry_run else "Imported"
        print(f"Sessions: {prefix} {summary.sessions_imported}")

        if summary.sessions_failed > 0:
            print(f"Failed: {summary.sessions_failed}")

        print(f"Turns: {summary.total_turns}")
        print(f"Tool Calls: {summary.total_tool_calls}")

        if not summary.dry_run:
            print(f"Weave Calls: {summary.total_weave_calls}")

        print(f"Tokens: {summary.total_tokens:,}")

        if summary.total_duration_ms > 0:
            print(f"Duration: {format_duration(summary.total_duration_ms)}")

        if summary.traces_url and not summary.dry_run:
            print()
            # For single session imports with call_id, link directly to the trace
            if len(summary.results) == 1 and summary.results[0].call_id:
                call_id = summary.results[0].call_id
                trace_url = f"{summary.traces_url}?peekPath=%2F%3Aid%2F{call_id}"
                print(f"View trace: {trace_url}")
            else:
                print(f"View traces: {summary.traces_url}")

    def print_error(self, message: str) -> None:
        """Print an error message."""
        print(f"Error: {message}")

    def print_session_result(self, result: ImportResult, dry_run: bool = False) -> None:
        """Print result for a single session (verbose mode only)."""
        if not self.verbose:
            return

        if result.success:
            prefix = "Would import" if dry_run else "Imported"
            print(
                f"  {prefix} {result.session_name}: "
                f"{result.turns} turns, {result.tool_calls} tool calls, "
                f"{result.tokens:,} tokens"
            )
        else:
            print(f"  Failed {result.session_name}: {result.error}")


def get_output(verbose: bool = False) -> RichOutput | BasicOutput:
    """Get the appropriate output handler based on rich availability."""
    if RICH_AVAILABLE:
        return RichOutput(verbose=verbose)
    return BasicOutput(verbose=verbose)


@contextmanager
def suppress_verbose_logging(debug: bool = False) -> Iterator[None]:
    """Suppress verbose logging from weave, httpx, wandb, etc.

    In normal mode, suppresses all INFO-level logs and call link printing.
    In debug mode, logs everything to a file in /tmp.

    Args:
        debug: If True, log to /tmp/weave-import-debug.log instead of suppressing
    """
    import warnings

    # Suppress polyfile deprecation warnings about pkg_resources
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

    if debug:
        # In debug mode, set up file logging
        debug_log_path = Path("/tmp/weave-import-debug.log")
        file_handler = logging.FileHandler(debug_log_path, mode="w")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.DEBUG)

        # Still suppress console output by setting high level for stream handlers
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler != file_handler:
                handler.setLevel(logging.WARNING)

        try:
            yield
        finally:
            root_logger.removeHandler(file_handler)
            file_handler.close()
        return

    # Normal mode: suppress all verbose logs
    # Save original environment state
    original_env = {
        "WEAVE_PRINT_CALL_LINK": os.environ.get("WEAVE_PRINT_CALL_LINK"),
        "WEAVE_LOG_LEVEL": os.environ.get("WEAVE_LOG_LEVEL"),
    }

    # Suppress weave call link printing and set log level
    os.environ["WEAVE_PRINT_CALL_LINK"] = "false"
    os.environ["WEAVE_LOG_LEVEL"] = "WARNING"

    # Suppress httpx, urllib3, wandb, and session parser logging
    loggers_to_suppress = [
        "httpx",
        "httpcore",
        "urllib3",
        "wandb",
        "weave",
        "weave.trace",
        "weave.integrations",
        "weave.integrations.claude_plugin.session.session_parser",
        "polyfile",  # suppress polyfile warnings too
    ]

    original_levels: dict[str, int] = {}
    for logger_name in loggers_to_suppress:
        logger = logging.getLogger(logger_name)
        original_levels[logger_name] = logger.level
        # Set to ERROR to suppress WARNING messages too (like "No session ID found")
        logger.setLevel(logging.ERROR)

    try:
        yield
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        # Restore original logger levels
        for logger_name, level in original_levels.items():
            logging.getLogger(logger_name).setLevel(level)
