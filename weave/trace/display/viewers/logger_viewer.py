"""Logger viewer implementation for the display abstraction layer.

This viewer outputs all display operations through Python's logging system,
making it useful for applications that prefer logging over direct console output.
"""

import logging
import sys
from typing import Any, Optional, Union

from weave.trace.display.protocols import (
    CaptureContextProtocol,
    ConsoleProtocol,
    ProgressProtocol,
    SyntaxProtocol,
    TableProtocol,
    TextProtocol,
)
from weave.trace.display.types import Style
from weave.trace.display.viewers.print_viewer import CaptureContext


class LoggerViewer:
    """Viewer implementation that outputs through Python's logging system."""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
        **kwargs: Any,
    ):
        """Initialize the logger viewer.

        Args:
            logger: Logger instance to use (defaults to root logger).
            level: Default logging level for output.
            **kwargs: Additional arguments (passed to parent).
        """
        self._file = kwargs.get("file", sys.stdout)
        self._emoji = kwargs.get("emoji", True)
        self.logger = logger or logging.getLogger()
        self.level = level

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[Union[str, Style]] = None,
        **kwargs: Any,
    ) -> None:
        """Log output at the configured level."""
        output = sep.join(str(obj) for obj in objects)
        if isinstance(style, Style):
            # Add style information as structured data
            self.logger.log(
                self.level,
                output,
                extra={
                    "style_color": style.color,
                    "style_bold": style.bold,
                    "style_italic": style.italic,
                    "style_underline": style.underline,
                },
            )
        else:
            self.logger.log(self.level, output)

    def rule(self, title: str = "", style: Optional[Union[str, Style]] = None) -> None:
        """Log a horizontal rule."""
        if title:
            self.logger.log(self.level, f"{'=' * 30} {title} {'=' * 30}")
        else:
            self.logger.log(self.level, "=" * 60)

    def clear(self) -> None:
        """Log a clear screen event."""
        self.logger.debug("Display clear requested")

    def create_table(
        self, title: Optional[str] = None, show_header: bool = True, **kwargs: Any
    ) -> TableProtocol:
        """Create a logger-based table."""
        return LoggerTable(self.logger, self.level, title, show_header)

    def create_progress(
        self, console: Optional[Any] = None, **kwargs: Any
    ) -> ProgressProtocol:
        """Create a logger-based progress tracker."""
        return LoggerProgress(self.logger, self.level)

    def create_syntax(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ) -> SyntaxProtocol:
        """Create a logger-based syntax object."""
        return LoggerSyntax(self.logger, self.level, code, lexer, line_numbers)

    def create_text(
        self, text: str = "", style: Optional[Union[str, Style]] = None
    ) -> TextProtocol:
        """Create a logger-based text object."""
        return LoggerText(self.logger, self.level, text, style)

    def indent(self, content: str, amount: int) -> str:
        """Indent content."""
        indent_str = " " * amount
        lines = content.split("\n")
        return "\n".join(indent_str + line if line else line for line in lines)

    def capture(self) -> CaptureContextProtocol:
        """Return a capture context (uses default implementation)."""
        return CaptureContext()


class LoggerTable:
    """Logger-based table implementation."""

    def __init__(
        self,
        logger: logging.Logger,
        level: int,
        title: Optional[str] = None,
        show_header: bool = True,
    ):
        self.logger = logger
        self.level = level
        self.title = title
        self.show_header = show_header
        self._columns: list[dict[str, Any]] = []
        self._rows: list[list[str]] = []

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Add a column to the table."""
        self._columns.append({"header": header, "justify": justify})

    def add_row(self, *values: Any) -> None:
        """Add a row to the table."""
        self._rows.append([str(v) for v in values])

    def to_string(self, console: Optional[ConsoleProtocol] = None) -> str:
        """Convert table to string and log it."""
        lines = []

        if self.title:
            lines.append(f"Table: {self.title}")

        if self.show_header and self._columns:
            headers = [col["header"] for col in self._columns]
            lines.append(" | ".join(headers))
            lines.append("-" * (sum(len(h) for h in headers) + 3 * (len(headers) - 1)))

        for row in self._rows:
            lines.append(" | ".join(row))

        output = "\n".join(lines)
        self.logger.log(self.level, output)
        return output


class LoggerProgress:
    """Logger-based progress implementation."""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self._tasks: dict[int, dict[str, Any]] = {}
        self._next_task_id = 0

    def add_task(
        self, description: str, total: Optional[float] = None, **kwargs: Any
    ) -> int:
        """Add a task."""
        task_id = self._next_task_id
        self._next_task_id += 1
        self._tasks[task_id] = {
            "description": description,
            "total": total or 100,
            "completed": 0,
        }
        self.logger.log(
            self.level,
            f"Progress started: {description} (0/{total or 100})",
            extra={"task_id": task_id, "progress_type": "start"},
        )
        return task_id

    def update(
        self,
        task_id: int,
        advance: Optional[float] = None,
        completed: Optional[float] = None,
        total: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """Update a task's progress."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            if total is not None:
                task["total"] = total
            if completed is not None:
                task["completed"] = completed
            if advance is not None:
                task["completed"] += advance

            percentage = (
                (task["completed"] / task["total"] * 100) if task["total"] > 0 else 0
            )
            self.logger.log(
                self.level,
                f"Progress update: {task['description']} "
                f"({task['completed']}/{task['total']}) {percentage:.1f}%",
                extra={
                    "task_id": task_id,
                    "progress_type": "update",
                    "percentage": percentage,
                },
            )

    def start(self) -> None:
        """Start progress tracking."""
        self.logger.debug("Progress tracking started")

    def stop(self) -> None:
        """Stop progress tracking."""
        for task_id, task in self._tasks.items():
            percentage = (
                (task["completed"] / task["total"] * 100) if task["total"] > 0 else 0
            )
            self.logger.log(
                self.level,
                f"Progress complete: {task['description']} - {percentage:.1f}%",
                extra={"task_id": task_id, "progress_type": "complete"},
            )


class LoggerSyntax:
    """Logger-based syntax highlighting implementation."""

    def __init__(
        self,
        logger: logging.Logger,
        level: int,
        code: str,
        lexer: str,
        line_numbers: bool = False,
    ):
        self.logger = logger
        self.level = level
        self.code = code
        self.lexer = lexer
        self.line_numbers = line_numbers

    def to_string(self, console: Optional[ConsoleProtocol] = None) -> str:
        """Convert to string."""
        lines = [f"Code ({self.lexer}):"]

        if self.line_numbers:
            code_lines = self.code.split("\n")
            width = len(str(len(code_lines)))
            for i, line in enumerate(code_lines):
                lines.append(f"{i + 1:>{width}} | {line}")
        else:
            lines.append(self.code)

        output = "\n".join(lines)
        self.logger.log(self.level, output, extra={"syntax_lexer": self.lexer})
        return output


class LoggerText:
    """Logger-based text implementation."""

    def __init__(
        self,
        logger: logging.Logger,
        level: int,
        text: str = "",
        style: Optional[Union[str, Style]] = None,
    ):
        self.logger = logger
        self.level = level
        self._text = text
        self._style = style

    def __str__(self) -> str:
        """Get string representation."""
        if isinstance(self._style, Style):
            self.logger.log(
                self.level,
                self._text,
                extra={
                    "text_style": {
                        "color": self._style.color,
                        "bold": self._style.bold,
                        "italic": self._style.italic,
                        "underline": self._style.underline,
                    }
                },
            )
        return self._text

    def __repr__(self) -> str:
        """Get repr string."""
        return f"LoggerText({self._text!r}, style={self._style!r})"
