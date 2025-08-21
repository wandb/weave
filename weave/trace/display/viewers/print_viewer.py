"""Print-based viewer implementation (fallback)."""

from __future__ import annotations

import sys
from typing import Any

from typing_extensions import Self

from weave.trace.display.protocols import (
    CaptureContextProtocol,
    ConsoleProtocol,
    ProgressProtocol,
    SyntaxProtocol,
    TableProtocol,
    TextProtocol,
)
from weave.trace.display.types import Style


class CaptureContext:
    """Context manager for capturing output."""

    def __init__(self) -> None:
        self._original_stdout: Any = None
        self._capture_buffer: Any = None

    def __enter__(self) -> Self:
        import io

        self._original_stdout = sys.stdout
        self._capture_buffer = io.StringIO()
        sys.stdout = self._capture_buffer
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        sys.stdout = self._original_stdout

    def get(self) -> str:
        """Get the captured output."""
        if self._capture_buffer:
            return self._capture_buffer.getvalue()
        return ""


class PrintViewer:
    """Viewer implementation using standard print functions."""

    def __init__(self, file: Any = None, emoji: bool = True, **kwargs: Any):
        self._file = file or sys.stdout
        self._emoji = emoji

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: str | Style | None = None,
        **kwargs: Any,
    ) -> None:
        output = sep.join(str(obj) for obj in objects)
        if isinstance(style, Style):
            output = style.to_ansi(output)
        print(output, end=end, file=self._file)

    def rule(self, title: str = "", style: str | Style | None = None) -> None:
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
        # ANSI clear screen
        print("\033[2J\033[H", end="", file=self._file)

    def create_table(
        self,
        title: str | None = None,
        show_header: bool = True,
        header_style: str | None = None,
        **kwargs: Any,
    ) -> TableProtocol:
        return PrintTable(
            title=title, show_header=show_header, header_style=header_style, **kwargs
        )

    def create_progress(
        self, console: ConsoleProtocol | None = None, **kwargs: Any
    ) -> ProgressProtocol:
        return PrintProgress(console=console, file=self._file)

    def create_syntax(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ) -> SyntaxProtocol:
        return PrintSyntax(code, lexer, line_numbers=line_numbers)

    def create_text(
        self, text: str = "", style: str | Style | None = None
    ) -> TextProtocol:
        return PrintText(text, style=style)

    def indent(self, content: str, amount: int) -> str:
        indent_str = " " * amount
        lines = content.split("\n")
        return "\n".join(indent_str + line if line else line for line in lines)

    def capture(self) -> CaptureContextProtocol:
        return CaptureContext()


class PrintTable:
    """Print-based table implementation."""

    def __init__(
        self,
        title: str | None = None,
        show_header: bool = True,
        header_style: str | None = None,
        **kwargs: Any,
    ):
        self.title = title
        self.show_header = show_header
        self.header_style = header_style
        self._columns: list[dict[str, Any]] = []
        self._rows: list[list[str]] = []

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._columns.append({"header": header, "justify": justify, "style": style})

    def add_row(self, *values: Any) -> None:
        # Convert any weave Table objects to their string representation
        processed_values = []
        for value in values:
            # Check if this is a weave Table object with to_string method
            if hasattr(value, "to_string") and callable(value.to_string):
                processed_values.append(value.to_string())
            else:
                processed_values.append(str(value))
        self._rows.append(processed_values)

    def to_string(self, console: ConsoleProtocol | None = None) -> str:
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


class PrintProgress:
    """Print-based progress bar implementation."""

    def __init__(self, console: ConsoleProtocol | None = None, file: Any = None):
        self.console = console
        self._file = file or sys.stdout
        self._tasks: dict[int, dict[str, Any]] = {}
        self._next_task_id = 0

    def add_task(
        self, description: str, total: float | None = None, **kwargs: Any
    ) -> int:
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
        advance: float | None = None,
        completed: float | None = None,
        total: float | None = None,
        **kwargs: Any,
    ) -> None:
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
        pass  # No-op for print viewer

    def stop(self) -> None:
        # Print final state for all tasks
        for task_id in self._tasks:
            self._print_progress(task_id, final=True)

    def _print_progress(self, task_id: int, final: bool = False) -> None:
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]
        percentage = (
            (task["completed"] / task["total"] * 100) if task["total"] > 0 else 0
        )
        status = "✓" if final and percentage >= 100 else "→"

        if self.console:
            self.console.print(
                f"{status} {task['description']}: {percentage:.1f}% "
                f"({task['completed']}/{task['total']})"
            )
        else:
            print(
                f"{status} {task['description']}: {percentage:.1f}% "
                f"({task['completed']}/{task['total']})",
                file=self._file,
            )

    def __enter__(self) -> Self:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()


class PrintSyntax:
    """Print-based syntax highlighting implementation."""

    def __init__(self, code: str, lexer: str, line_numbers: bool = False):
        self.code = code
        self.lexer = lexer
        self.line_numbers = line_numbers

    def to_string(self, console: ConsoleProtocol | None = None) -> str:
        if self.line_numbers:
            lines = self.code.split("\n")
            width = len(str(len(lines)))
            numbered_lines = [
                f"{i + 1:>{width}} | {line}" for i, line in enumerate(lines)
            ]
            return "\n".join(numbered_lines)
        return self.code


class PrintText:
    """Print-based text implementation."""

    def __init__(self, text: str = "", style: str | Style | None = None):
        self._text = text
        self._style = style

    def __str__(self) -> str:
        if isinstance(self._style, Style):
            return self._style.to_ansi(self._text)
        return self._text

    def __repr__(self) -> str:
        return f"Text({self._text!r}, style={self._style!r})"


# Registration function to be called by display module
def register() -> None:
    """Register the print viewer with the display system.

    This function is called by the display module after initialization
    to avoid circular import issues.
    """
    from weave.trace.display import display

    display.register_viewer("print", PrintViewer)
