"""Display abstraction layer that can dispatch to rich or standard print.

This module provides a unified interface for display operations, automatically
falling back to standard print functions when rich is not available.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Optional, Union

# Try to import rich components, but make them optional
try:
    from rich.console import Console as RichConsole
    from rich.padding import Padding
    from rich.progress import (
        BarColumn,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.progress import (
        Progress as RichProgress,
    )
    from rich.syntax import Syntax
    from rich.table import Table as RichTable
    from rich.text import Text as RichText

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Create dummy types for type checking
    RichConsole = Any
    RichProgress = Any
    RichTable = Any
    RichText = Any
    Syntax = Any
    Padding = Any


@dataclass
class Style:
    """Style configuration for console output.

    When rich is available, these map to rich styles.
    When rich is not available, they are ignored or mapped to basic ANSI codes.
    """

    color: Optional[str] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False

    def to_rich_style(self) -> str:
        """Convert to rich style string."""
        if not RICH_AVAILABLE:
            return ""

        parts = []
        if self.color:
            parts.append(self.color)
        if self.bold:
            parts.append("bold")
        if self.italic:
            parts.append("italic")
        if self.underline:
            parts.append("underline")
        return " ".join(parts)

    def to_ansi(self, text: str) -> str:
        """Apply basic ANSI codes to text (fallback when rich is not available)."""
        if not any([self.color, self.bold, self.italic, self.underline]):
            return text

        # Basic ANSI color mapping
        ansi_colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "black": "\033[90m",
        }

        codes = []
        if self.bold:
            codes.append("\033[1m")
        if self.italic:
            codes.append("\033[3m")
        if self.underline:
            codes.append("\033[4m")
        if self.color and self.color.lower() in ansi_colors:
            codes.append(ansi_colors[self.color.lower()])

        if codes:
            return "".join(codes) + text + "\033[0m"
        return text


class Console:
    """Console abstraction that dispatches to rich.Console or standard print.

    This class provides a unified interface for console output operations,
    automatically falling back to standard print when rich is not available.
    """

    def __init__(
        self,
        file: Any = None,
        force_terminal: Optional[bool] = None,
        emoji: bool = True,
        **kwargs: Any,
    ):
        """Initialize the console.

        Args:
            file: Output file stream (defaults to stdout).
            force_terminal: Force terminal mode.
            emoji: Enable emoji support.
            **kwargs: Additional arguments passed to rich.Console if available.
        """
        self._file = file or sys.stdout
        self._emoji = emoji

        if RICH_AVAILABLE:
            self._rich_console: Optional[RichConsole] = RichConsole(
                file=file, force_terminal=force_terminal, emoji=emoji, **kwargs
            )
        else:
            self._rich_console = None

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[Union[str, Style]] = None,
        **kwargs: Any,
    ) -> None:
        """Print to the console with optional styling.

        Args:
            *objects: Objects to print.
            sep: Separator between objects.
            end: String to append after.
            style: Style to apply (ignored if rich is not available).
            **kwargs: Additional arguments passed to rich.print if available.
        """
        if self._rich_console:
            # Convert Style to rich style string
            if isinstance(style, Style):
                kwargs["style"] = style.to_rich_style()
            elif style:
                kwargs["style"] = style

            self._rich_console.print(*objects, sep=sep, end=end, **kwargs)
        else:
            # Fallback to standard print
            output = sep.join(str(obj) for obj in objects)

            # Apply basic ANSI styling if Style object provided
            if isinstance(style, Style):
                output = style.to_ansi(output)

            print(output, end=end, file=self._file)

    def rule(self, title: str = "", style: Optional[Union[str, Style]] = None) -> None:
        """Print a horizontal rule.

        Args:
            title: Optional title for the rule.
            style: Style to apply.
        """
        if self._rich_console:
            if isinstance(style, Style):
                style = style.to_rich_style()
            self._rich_console.rule(title, style=style)
        else:
            # Simple fallback rule
            width = 80  # Default width
            if title:
                padding = (width - len(title) - 2) // 2
                rule = "─" * padding + f" {title} " + "─" * padding
            else:
                rule = "─" * width

            if isinstance(style, Style):
                rule = style.to_ansi(rule)

            print(rule, file=self._file)

    def clear(self) -> None:
        """Clear the console."""
        if self._rich_console:
            self._rich_console.clear()
        else:
            # ANSI clear screen
            print("\033[2J\033[H", end="", file=self._file)

    def capture(self) -> CaptureContext:
        """Capture console output.

        Returns:
            A context manager for capturing output.
        """
        if self._rich_console:
            return self._rich_console.capture()
        else:
            return CaptureContext()


class CaptureContext:
    """Context manager for capturing console output (fallback implementation)."""

    def __init__(self):
        self._original_stdout = None
        self._capture_buffer = None

    def __enter__(self):
        import io

        self._original_stdout = sys.stdout
        self._capture_buffer = io.StringIO()
        sys.stdout = self._capture_buffer
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._original_stdout

    def get(self) -> str:
        """Get the captured output."""
        if self._capture_buffer:
            return self._capture_buffer.getvalue()
        return ""


class Text:
    """Text abstraction that can use rich.Text or plain strings.

    This class provides styled text functionality, falling back to
    plain strings with optional ANSI codes when rich is not available.
    """

    def __init__(self, text: str = "", style: Optional[Union[str, Style]] = None):
        """Initialize the text object.

        Args:
            text: The text content.
            style: Style to apply to the text.
        """
        self._text = text
        self._style = style

        if RICH_AVAILABLE and RichText:
            if isinstance(style, Style):
                style = style.to_rich_style()
            self._rich_text: Optional[RichText] = RichText(text, style=style)
        else:
            self._rich_text = None

    def __str__(self) -> str:
        """Get string representation."""
        if self._rich_text:
            return str(self._rich_text)
        elif isinstance(self._style, Style):
            return self._style.to_ansi(self._text)
        else:
            return self._text

    def __repr__(self) -> str:
        """Get repr string."""
        return f"Text({self._text!r}, style={self._style!r})"


class Table:
    """Table abstraction that can use rich.Table or format as plain text.

    This class provides table functionality, falling back to simple
    text-based table formatting when rich is not available.
    """

    def __init__(
        self,
        title: Optional[str] = None,
        show_header: bool = True,
        header_style: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize the table.

        Args:
            title: Optional table title.
            show_header: Whether to show column headers.
            header_style: Style for headers (rich only).
            **kwargs: Additional arguments for rich.Table.
        """
        self.title = title
        self.show_header = show_header
        self._columns: list[dict[str, Any]] = []
        self._rows: list[list[str]] = []

        if RICH_AVAILABLE and RichTable:
            self._rich_table: Optional[RichTable] = RichTable(
                title=title,
                show_header=show_header,
                header_style=header_style,
                **kwargs,
            )
        else:
            self._rich_table = None

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Add a column to the table.

        Args:
            header: Column header text.
            justify: Column justification (left, right, center).
            style: Column style (rich only).
            **kwargs: Additional arguments for rich.Table.add_column.
        """
        self._columns.append(
            {
                "header": header,
                "justify": justify,
                "style": style,
            }
        )

        if self._rich_table:
            self._rich_table.add_column(header, justify=justify, style=style, **kwargs)

    def add_row(self, *values: Any) -> None:
        """Add a row to the table.

        Args:
            *values: Values for each column in the row.
        """
        self._rows.append([str(v) for v in values])

        if self._rich_table:
            self._rich_table.add_row(*values)

    def to_string(self, console: Optional[Console] = None) -> str:
        """Convert the table to a string.

        Args:
            console: Console to use for rendering (rich only).

        Returns:
            String representation of the table.
        """
        if self._rich_table and console and console._rich_console:
            with console.capture() as capture:
                console.print(self._rich_table)
            return capture.get().strip()
        else:
            # Fallback to simple text table
            return self._format_text_table()

    def _format_text_table(self) -> str:
        """Format table as plain text."""
        if not self._columns:
            return ""

        # Calculate column widths
        widths = []
        for i, col in enumerate(self._columns):
            width = len(col["header"])
            for row in self._rows:
                if i < len(row):
                    width = max(width, len(row[i]))
            widths.append(width)

        lines = []

        # Add title if present
        if self.title:
            lines.append(self.title)
            lines.append("")

        # Add header
        if self.show_header:
            header_parts = []
            for i, col in enumerate(self._columns):
                text = col["header"]
                if col["justify"] == "right":
                    text = text.rjust(widths[i])
                elif col["justify"] == "center":
                    text = text.center(widths[i])
                else:
                    text = text.ljust(widths[i])
                header_parts.append(text)
            lines.append(" │ ".join(header_parts))
            lines.append("─" * (sum(widths) + 3 * (len(widths) - 1)))

        # Add rows
        for row in self._rows:
            row_parts = []
            for i, col in enumerate(self._columns):
                if i < len(row):
                    text = row[i]
                else:
                    text = ""

                if col["justify"] == "right":
                    text = text.rjust(widths[i])
                elif col["justify"] == "center":
                    text = text.center(widths[i])
                else:
                    text = text.ljust(widths[i])
                row_parts.append(text)
            lines.append(" │ ".join(row_parts))

        return "\n".join(lines)


class Progress:
    """Progress bar abstraction that can use rich.Progress or simple text output.

    This class provides progress bar functionality, falling back to simple
    percentage-based progress updates when rich is not available.
    """

    def __init__(
        self,
        *columns: Any,
        console: Optional[Console] = None,
        refresh_per_second: float = 10,
        **kwargs: Any,
    ):
        """Initialize the progress bar.

        Args:
            *columns: Progress bar columns (rich only).
            console: Console to use for output.
            refresh_per_second: Refresh rate (rich only).
            **kwargs: Additional arguments for rich.Progress.
        """
        self.console = console or Console()
        self._tasks: dict[int, dict[str, Any]] = {}
        self._next_task_id = 0

        if RICH_AVAILABLE and RichProgress:
            # If no columns specified, use defaults
            if not columns:
                columns = (
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                )

            self._rich_progress: Optional[RichProgress] = RichProgress(
                *columns,
                console=console._rich_console
                if console and console._rich_console
                else None,
                refresh_per_second=refresh_per_second,
                **kwargs,
            )
        else:
            self._rich_progress = None

    def add_task(
        self, description: str, total: Optional[float] = None, **kwargs: Any
    ) -> int:
        """Add a task to the progress bar.

        Args:
            description: Task description.
            total: Total number of steps.
            **kwargs: Additional arguments for rich.Progress.add_task.

        Returns:
            Task ID.
        """
        if self._rich_progress:
            return self._rich_progress.add_task(description, total=total, **kwargs)
        else:
            task_id = self._next_task_id
            self._next_task_id += 1
            self._tasks[task_id] = {
                "description": description,
                "total": total or 100,
                "completed": 0,
            }
            self._print_progress(task_id)
            return task_id

    def update(
        self,
        task_id: int,
        advance: Optional[float] = None,
        completed: Optional[float] = None,
        total: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """Update a task's progress.

        Args:
            task_id: ID of the task to update.
            advance: Amount to advance the progress.
            completed: Set the completed amount directly.
            total: Update the total amount.
            **kwargs: Additional arguments for rich.Progress.update.
        """
        if self._rich_progress:
            self._rich_progress.update(
                task_id, advance=advance, completed=completed, total=total, **kwargs
            )
        else:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                if total is not None:
                    task["total"] = total
                if completed is not None:
                    task["completed"] = completed
                if advance is not None:
                    task["completed"] += advance
                self._print_progress(task_id)

    def start(self) -> None:
        """Start the progress bar."""
        if self._rich_progress:
            self._rich_progress.start()

    def stop(self) -> None:
        """Stop the progress bar."""
        if self._rich_progress:
            self._rich_progress.stop()
        else:
            # Print final state for all tasks
            for task_id in self._tasks:
                self._print_progress(task_id, final=True)

    def _print_progress(self, task_id: int, final: bool = False) -> None:
        """Print progress for text-based fallback.

        Args:
            task_id: Task ID to print progress for.
            final: Whether this is the final update.
        """
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]
        percentage = (
            (task["completed"] / task["total"] * 100) if task["total"] > 0 else 0
        )
        status = "✓" if final and percentage >= 100 else "→"

        self.console.print(
            f"{status} {task['description']}: {percentage:.1f}% "
            f"({task['completed']}/{task['total']})"
        )

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class SyntaxHighlight:
    """Syntax highlighting abstraction.

    Uses rich.Syntax when available, falls back to plain text.
    """

    def __init__(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ):
        """Initialize syntax highlighting.

        Args:
            code: Code to highlight.
            lexer: Language/lexer name.
            theme: Color theme (rich only).
            line_numbers: Whether to show line numbers.
        """
        self.code = code
        self.lexer = lexer
        self.line_numbers = line_numbers

        if RICH_AVAILABLE and Syntax:
            self._rich_syntax: Optional[Syntax] = Syntax(
                code, lexer, theme=theme, line_numbers=line_numbers
            )
        else:
            self._rich_syntax = None

    def to_string(self, console: Optional[Console] = None) -> str:
        """Convert to string representation.

        Args:
            console: Console to use for rendering.

        Returns:
            Highlighted code string.
        """
        if self._rich_syntax and console and console._rich_console:
            with console.capture() as capture:
                console.print(self._rich_syntax)
            return capture.get().strip()
        else:
            # Fallback: plain text with optional line numbers
            if self.line_numbers:
                lines = self.code.split("\n")
                width = len(str(len(lines)))
                numbered_lines = [
                    f"{i + 1:>{width}} | {line}" for i, line in enumerate(lines)
                ]
                return "\n".join(numbered_lines)
            return self.code


class PaddingWrapper:
    """Padding abstraction for indenting content.

    Uses rich.Padding when available, falls back to manual indentation.
    """

    @staticmethod
    def indent(content: str, amount: int) -> str:
        """Indent content by the specified amount.

        Args:
            content: Content to indent.
            amount: Number of spaces to indent.

        Returns:
            Indented content.
        """
        if RICH_AVAILABLE and Padding:
            return Padding.indent(content, amount)
        else:
            # Manual indentation
            indent_str = " " * amount
            lines = content.split("\n")
            return "\n".join(indent_str + line if line else line for line in lines)


# Create default console instance
console = Console()
