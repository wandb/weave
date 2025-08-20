"""Display abstraction layer with pluggable viewer system.

This module provides a unified interface for display operations with
a pluggable viewer system that allows users to configure their preferred
display method (rich, print, logger, etc.).
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type, Union

# Global viewer registry and configuration
_viewer_registry: Dict[str, Type[BaseViewer]] = {}
_current_viewer: Optional[BaseViewer] = None
_default_viewer_name = "auto"  # Will try rich first, then fallback to print


class ViewerType(Enum):
    """Enumeration of available viewer types."""

    RICH = "rich"
    PRINT = "print"
    AUTO = "auto"


@dataclass
class Style:
    """Style configuration for console output.

    Used by viewers to apply styling to text output.
    """

    color: Optional[str] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False

    def to_ansi(self, text: str) -> str:
        """Apply basic ANSI codes to text (fallback for non-rich viewers)."""
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


class BaseViewer(ABC):
    """Abstract base class for display viewers.

    All viewer implementations must inherit from this class and implement
    the required display methods.
    """

    def __init__(self, file: Any = None, emoji: bool = True, **kwargs: Any):
        """Initialize the viewer.

        Args:
            file: Output file stream (defaults to stdout).
            emoji: Enable emoji support.
            **kwargs: Additional viewer-specific arguments.
        """
        self._file = file or sys.stdout
        self._emoji = emoji

    @abstractmethod
    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[Union[str, Style]] = None,
        **kwargs: Any,
    ) -> None:
        """Print to the output with optional styling."""
        pass

    @abstractmethod
    def rule(self, title: str = "", style: Optional[Union[str, Style]] = None) -> None:
        """Print a horizontal rule."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear the display."""
        pass

    @abstractmethod
    def create_table(
        self, title: Optional[str] = None, show_header: bool = True, **kwargs: Any
    ) -> TableInterface:
        """Create a table object."""
        pass

    @abstractmethod
    def create_progress(
        self, console: Optional[Console] = None, **kwargs: Any
    ) -> ProgressInterface:
        """Create a progress bar object."""
        pass

    @abstractmethod
    def create_syntax(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ) -> SyntaxInterface:
        """Create a syntax highlighting object."""
        pass

    @abstractmethod
    def create_text(
        self, text: str = "", style: Optional[Union[str, Style]] = None
    ) -> TextInterface:
        """Create a styled text object."""
        pass

    @abstractmethod
    def indent(self, content: str, amount: int) -> str:
        """Indent content by the specified amount."""
        pass

    @abstractmethod
    def capture(self) -> CaptureContext:
        """Create a capture context for capturing output."""
        pass


# Interface classes for display objects
class TableInterface(ABC):
    """Interface for table objects."""

    @abstractmethod
    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Add a column to the table."""
        pass

    @abstractmethod
    def add_row(self, *values: Any) -> None:
        """Add a row to the table."""
        pass

    @abstractmethod
    def to_string(self, console: Optional[Console] = None) -> str:
        """Convert the table to a string."""
        pass


class ProgressInterface(ABC):
    """Interface for progress bar objects."""

    @abstractmethod
    def add_task(
        self, description: str, total: Optional[float] = None, **kwargs: Any
    ) -> int:
        """Add a task to the progress bar."""
        pass

    @abstractmethod
    def update(
        self,
        task_id: int,
        advance: Optional[float] = None,
        completed: Optional[float] = None,
        total: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """Update a task's progress."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the progress bar."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the progress bar."""
        pass

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class SyntaxInterface(ABC):
    """Interface for syntax highlighting objects."""

    @abstractmethod
    def to_string(self, console: Optional[Console] = None) -> str:
        """Convert to string representation."""
        pass


class TextInterface(ABC):
    """Interface for styled text objects."""

    @abstractmethod
    def __str__(self) -> str:
        """Get string representation."""
        pass


class CaptureContext:
    """Context manager for capturing output."""

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


# Rich viewer implementation
class RichViewer(BaseViewer):
    """Viewer implementation using the rich library."""

    def __init__(
        self,
        file: Any = None,
        emoji: bool = True,
        force_terminal: Optional[bool] = None,
        **kwargs: Any,
    ):
        super().__init__(file=file, emoji=emoji, **kwargs)
        from rich.console import Console as RichConsole

        self._console = RichConsole(
            file=file, force_terminal=force_terminal, emoji=emoji, **kwargs
        )

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[Union[str, Style]] = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(style, Style):
            kwargs["style"] = self._style_to_rich(style)
        elif style:
            kwargs["style"] = style
        self._console.print(*objects, sep=sep, end=end, **kwargs)

    def rule(self, title: str = "", style: Optional[Union[str, Style]] = None) -> None:
        if isinstance(style, Style):
            style = self._style_to_rich(style)
        self._console.rule(title, style=style)

    def clear(self) -> None:
        self._console.clear()

    def create_table(
        self, title: Optional[str] = None, show_header: bool = True, **kwargs: Any
    ) -> TableInterface:
        return RichTable(title=title, show_header=show_header, **kwargs)

    def create_progress(
        self, console: Optional[Console] = None, **kwargs: Any
    ) -> ProgressInterface:
        return RichProgress(console=self._console, **kwargs)

    def create_syntax(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ) -> SyntaxInterface:
        return RichSyntax(code, lexer, theme=theme, line_numbers=line_numbers)

    def create_text(
        self, text: str = "", style: Optional[Union[str, Style]] = None
    ) -> TextInterface:
        return RichText(text, style=style)

    def indent(self, content: str, amount: int) -> str:
        from rich.padding import Padding

        return Padding.indent(content, amount)

    def capture(self) -> CaptureContext:
        return self._console.capture()

    def _style_to_rich(self, style: Style) -> str:
        """Convert Style object to rich style string."""
        parts = []
        if style.color:
            parts.append(style.color)
        if style.bold:
            parts.append("bold")
        if style.italic:
            parts.append("italic")
        if style.underline:
            parts.append("underline")
        return " ".join(parts)


class RichTable(TableInterface):
    """Rich table implementation."""

    def __init__(
        self, title: Optional[str] = None, show_header: bool = True, **kwargs: Any
    ):
        from rich.table import Table as RichTableBase

        self._table = RichTableBase(title=title, show_header=show_header, **kwargs)

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._table.add_column(header, justify=justify, style=style, **kwargs)

    def add_row(self, *values: Any) -> None:
        self._table.add_row(*values)

    def to_string(self, console: Optional[Console] = None) -> str:
        if (
            console
            and hasattr(console, "_viewer")
            and isinstance(console._viewer, RichViewer)
        ):
            with console._viewer._console.capture() as capture:
                console._viewer._console.print(self._table)
            return capture.get().strip()
        else:
            # Fallback to basic string representation
            from rich.console import Console as RichConsole

            temp_console = RichConsole()
            with temp_console.capture() as capture:
                temp_console.print(self._table)
            return capture.get().strip()


class RichProgress(ProgressInterface):
    """Rich progress bar implementation."""

    def __init__(self, console: Any, **kwargs: Any):
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        # Default columns if not specified
        columns = kwargs.pop("columns", None)
        if not columns:
            columns = (
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
            )

        self._progress = Progress(*columns, console=console, **kwargs)

    def add_task(
        self, description: str, total: Optional[float] = None, **kwargs: Any
    ) -> int:
        return self._progress.add_task(description, total=total, **kwargs)

    def update(
        self,
        task_id: int,
        advance: Optional[float] = None,
        completed: Optional[float] = None,
        total: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        self._progress.update(
            task_id, advance=advance, completed=completed, total=total, **kwargs
        )

    def start(self) -> None:
        self._progress.start()

    def stop(self) -> None:
        self._progress.stop()


class RichSyntax(SyntaxInterface):
    """Rich syntax highlighting implementation."""

    def __init__(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ):
        from rich.syntax import Syntax

        self._syntax = Syntax(code, lexer, theme=theme, line_numbers=line_numbers)

    def to_string(self, console: Optional[Console] = None) -> str:
        if (
            console
            and hasattr(console, "_viewer")
            and isinstance(console._viewer, RichViewer)
        ):
            with console._viewer._console.capture() as capture:
                console._viewer._console.print(self._syntax)
            return capture.get().strip()
        else:
            from rich.console import Console as RichConsole

            temp_console = RichConsole()
            with temp_console.capture() as capture:
                temp_console.print(self._syntax)
            return capture.get().strip()


class RichText(TextInterface):
    """Rich text implementation."""

    def __init__(self, text: str = "", style: Optional[Union[str, Style]] = None):
        from rich.text import Text as RichTextBase

        if isinstance(style, Style):
            style = self._style_to_rich(style)
        self._text = RichTextBase(text, style=style)

    def __str__(self) -> str:
        return str(self._text)

    def _style_to_rich(self, style: Style) -> str:
        """Convert Style object to rich style string."""
        parts = []
        if style.color:
            parts.append(style.color)
        if style.bold:
            parts.append("bold")
        if style.italic:
            parts.append("italic")
        if style.underline:
            parts.append("underline")
        return " ".join(parts)


# Print viewer implementation (fallback)
class PrintViewer(BaseViewer):
    """Viewer implementation using standard print functions."""

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[Union[str, Style]] = None,
        **kwargs: Any,
    ) -> None:
        output = sep.join(str(obj) for obj in objects)
        if isinstance(style, Style):
            output = style.to_ansi(output)
        print(output, end=end, file=self._file)

    def rule(self, title: str = "", style: Optional[Union[str, Style]] = None) -> None:
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
        self, title: Optional[str] = None, show_header: bool = True, **kwargs: Any
    ) -> TableInterface:
        return PrintTable(title=title, show_header=show_header)

    def create_progress(
        self, console: Optional[Console] = None, **kwargs: Any
    ) -> ProgressInterface:
        return PrintProgress(console=console)

    def create_syntax(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ) -> SyntaxInterface:
        return PrintSyntax(code, lexer, line_numbers=line_numbers)

    def create_text(
        self, text: str = "", style: Optional[Union[str, Style]] = None
    ) -> TextInterface:
        return PrintText(text, style=style)

    def indent(self, content: str, amount: int) -> str:
        indent_str = " " * amount
        lines = content.split("\n")
        return "\n".join(indent_str + line if line else line for line in lines)

    def capture(self) -> CaptureContext:
        return CaptureContext()


class PrintTable(TableInterface):
    """Print-based table implementation."""

    def __init__(self, title: Optional[str] = None, show_header: bool = True):
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
        self._columns.append({"header": header, "justify": justify, "style": style})

    def add_row(self, *values: Any) -> None:
        self._rows.append([str(v) for v in values])

    def to_string(self, console: Optional[Console] = None) -> str:
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


class PrintProgress(ProgressInterface):
    """Print-based progress bar implementation."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or get_console()
        self._tasks: dict[int, dict[str, Any]] = {}
        self._next_task_id = 0

    def add_task(
        self, description: str, total: Optional[float] = None, **kwargs: Any
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
        advance: Optional[float] = None,
        completed: Optional[float] = None,
        total: Optional[float] = None,
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

        self.console.print(
            f"{status} {task['description']}: {percentage:.1f}% "
            f"({task['completed']}/{task['total']})"
        )


class PrintSyntax(SyntaxInterface):
    """Print-based syntax highlighting implementation."""

    def __init__(self, code: str, lexer: str, line_numbers: bool = False):
        self.code = code
        self.line_numbers = line_numbers

    def to_string(self, console: Optional[Console] = None) -> str:
        if self.line_numbers:
            lines = self.code.split("\n")
            width = len(str(len(lines)))
            numbered_lines = [
                f"{i + 1:>{width}} | {line}" for i, line in enumerate(lines)
            ]
            return "\n".join(numbered_lines)
        return self.code


class PrintText(TextInterface):
    """Print-based text implementation."""

    def __init__(self, text: str = "", style: Optional[Union[str, Style]] = None):
        self._text = text
        self._style = style

    def __str__(self) -> str:
        if isinstance(self._style, Style):
            return self._style.to_ansi(self._text)
        return self._text

    def __repr__(self) -> str:
        return f"Text({self._text!r}, style={self._style!r})"


# Viewer registration and configuration
def register_viewer(name: str, viewer_class: Type[BaseViewer]) -> None:
    """Register a viewer implementation.

    Args:
        name: Name of the viewer (e.g., "rich", "print", "logger").
        viewer_class: The viewer class to register.
    """
    _viewer_registry[name] = viewer_class


def set_viewer(name: str, **kwargs: Any) -> None:
    """Set the current viewer by name.

    Args:
        name: Name of the viewer to use.
        **kwargs: Additional arguments to pass to the viewer constructor.
    """
    global _current_viewer

    if name == "auto":
        # Auto-detect: try rich first, fallback to print
        try:
            _current_viewer = _create_rich_viewer(**kwargs)
        except ImportError:
            _current_viewer = PrintViewer(**kwargs)
    elif name in _viewer_registry:
        _current_viewer = _viewer_registry[name](**kwargs)
    else:
        raise ValueError(f"Unknown viewer: {name}")


def get_viewer() -> BaseViewer:
    """Get the current viewer instance.

    Returns:
        The current viewer instance.
    """
    global _current_viewer

    if _current_viewer is None:
        set_viewer(_default_viewer_name)

    return _current_viewer


def _create_rich_viewer(**kwargs: Any) -> RichViewer:
    """Create a rich viewer, raising ImportError if rich is not available."""
    try:
        import rich  # noqa: F401

        return RichViewer(**kwargs)
    except ImportError:
        raise ImportError("Rich library is not available")


# Register default viewers
register_viewer("rich", RichViewer)
register_viewer("print", PrintViewer)


# Public API classes that delegate to the viewer
class Console:
    """Console abstraction that delegates to the configured viewer.

    This class provides a unified interface for console output operations,
    using the configured viewer for actual display operations.
    """

    def __init__(
        self,
        file: Any = None,
        force_terminal: Optional[bool] = None,
        emoji: bool = True,
        viewer: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize the console.

        Args:
            file: Output file stream (defaults to stdout).
            force_terminal: Force terminal mode.
            emoji: Enable emoji support.
            viewer: Specific viewer to use (overrides global setting).
            **kwargs: Additional arguments passed to the viewer.
        """
        if viewer:
            # Create a specific viewer for this console
            if viewer == "auto":
                try:
                    self._viewer = _create_rich_viewer(
                        file=file, emoji=emoji, force_terminal=force_terminal, **kwargs
                    )
                except ImportError:
                    self._viewer = PrintViewer(file=file, emoji=emoji, **kwargs)
            elif viewer in _viewer_registry:
                self._viewer = _viewer_registry[viewer](
                    file=file, emoji=emoji, **kwargs
                )
            else:
                raise ValueError(f"Unknown viewer: {viewer}")
        else:
            # Use the global viewer
            self._viewer = get_viewer()

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: Optional[Union[str, Style]] = None,
        **kwargs: Any,
    ) -> None:
        """Print to the console with optional styling."""
        self._viewer.print(*objects, sep=sep, end=end, style=style, **kwargs)

    def rule(self, title: str = "", style: Optional[Union[str, Style]] = None) -> None:
        """Print a horizontal rule."""
        self._viewer.rule(title, style=style)

    def clear(self) -> None:
        """Clear the console."""
        self._viewer.clear()

    def capture(self) -> CaptureContext:
        """Capture console output."""
        return self._viewer.capture()


class Table:
    """Table abstraction that delegates to the configured viewer."""

    def __init__(
        self,
        title: Optional[str] = None,
        show_header: bool = True,
        header_style: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize the table."""
        viewer = get_viewer()
        self._table = viewer.create_table(
            title=title, show_header=show_header, **kwargs
        )

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Add a column to the table."""
        self._table.add_column(header, justify=justify, style=style, **kwargs)

    def add_row(self, *values: Any) -> None:
        """Add a row to the table."""
        self._table.add_row(*values)

    def to_string(self, console: Optional[Console] = None) -> str:
        """Convert the table to a string."""
        return self._table.to_string(console)


class Progress:
    """Progress bar abstraction that delegates to the configured viewer."""

    def __init__(
        self,
        *columns: Any,
        console: Optional[Console] = None,
        refresh_per_second: float = 10,
        **kwargs: Any,
    ):
        """Initialize the progress bar."""
        viewer = get_viewer()
        self._progress = viewer.create_progress(console=console, **kwargs)

    def add_task(
        self, description: str, total: Optional[float] = None, **kwargs: Any
    ) -> int:
        """Add a task to the progress bar."""
        return self._progress.add_task(description, total=total, **kwargs)

    def update(
        self,
        task_id: int,
        advance: Optional[float] = None,
        completed: Optional[float] = None,
        total: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """Update a task's progress."""
        self._progress.update(
            task_id, advance=advance, completed=completed, total=total, **kwargs
        )

    def start(self) -> None:
        """Start the progress bar."""
        self._progress.start()

    def stop(self) -> None:
        """Stop the progress bar."""
        self._progress.stop()

    def __enter__(self):
        """Context manager entry."""
        return self._progress.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return self._progress.__exit__(exc_type, exc_val, exc_tb)


class SyntaxHighlight:
    """Syntax highlighting abstraction that delegates to the configured viewer."""

    def __init__(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ):
        """Initialize syntax highlighting."""
        viewer = get_viewer()
        self._syntax = viewer.create_syntax(
            code, lexer, theme=theme, line_numbers=line_numbers
        )

    def to_string(self, console: Optional[Console] = None) -> str:
        """Convert to string representation."""
        return self._syntax.to_string(console)


class Text:
    """Text abstraction that delegates to the configured viewer."""

    def __init__(self, text: str = "", style: Optional[Union[str, Style]] = None):
        """Initialize the text object."""
        viewer = get_viewer()
        self._text_obj = viewer.create_text(text, style=style)

    def __str__(self) -> str:
        """Get string representation."""
        return str(self._text_obj)

    def __repr__(self) -> str:
        """Get repr string."""
        return (
            repr(self._text_obj)
            if hasattr(self._text_obj, "__repr__")
            else str(self._text_obj)
        )


class PaddingWrapper:
    """Padding abstraction for indenting content."""

    @staticmethod
    def indent(content: str, amount: int) -> str:
        """Indent content by the specified amount."""
        viewer = get_viewer()
        return viewer.indent(content, amount)


# Helper function for getting console instance
def get_console() -> Console:
    """Get the default console instance."""
    return console


# Create default console instance
console = Console()
