"""Display abstraction layer with pluggable viewer system.

This module provides a unified interface for display operations with
a pluggable viewer system that allows users to configure their preferred
display method (rich, print, logger, etc.).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from typing_extensions import Self

from weave.trace import settings
from weave.trace.display.protocols import (
    CaptureContextProtocol,
    ProgressProtocol,
    SyntaxProtocol,
    TableProtocol,
    TextProtocol,
    ViewerProtocol,
)
from weave.trace.display.types import Style

# Since ViewerProtocol is a Protocol, we can't use Type[ViewerProtocol]
# Instead, we use a callable that returns a ViewerProtocol
ViewerFactory = Callable[..., ViewerProtocol]

# Global viewer registry
_viewer_registry: dict[str, ViewerFactory] = {}


# Viewer registration and configuration
def register_viewer(name: str, viewer_class: ViewerFactory) -> None:
    """Register a viewer implementation.

    Args:
        name: Name of the viewer (e.g., "rich", "print", "logger").
        viewer_class: The viewer class to register.
    """
    _viewer_registry[name] = viewer_class


def _get_auto_viewer(**kwargs: Any) -> ViewerProtocol:
    """Get the auto-detected viewer.  Tries to use rich first, then falls back to print.

    Args:
        **kwargs: Additional arguments to pass to the viewer constructor.

    Returns:
        The auto-detected viewer.
    """
    try:
        from weave.trace.display.viewers.rich_viewer import RichViewer

        return RichViewer(**kwargs)
    except ImportError:
        from weave.trace.display.viewers.print_viewer import PrintViewer

        return PrintViewer(**kwargs)


def get_viewer(name: str | None = None, **kwargs: Any) -> ViewerProtocol:
    """Get a viewer instance.

    Args:
        name: Optional name of the viewer to use. If None, uses the setting from weave.trace.settings.
        **kwargs: Additional arguments to pass to the viewer constructor.

    Returns:
        A new viewer instance.
    """
    if name is None:
        name = settings.display_viewer()

    if name == "auto":
        return _get_auto_viewer(**kwargs)
    elif name in _viewer_registry:
        viewer_class = _viewer_registry[name]
        return viewer_class(**kwargs)
    else:
        raise ValueError(f"Unknown viewer: {name}")


class Console:
    """Console abstraction that delegates to the configured viewer.

    This class provides a unified interface for console output operations,
    using the configured viewer for actual display operations.
    """

    def __init__(
        self,
        file: Any = None,
        force_terminal: bool | None = None,
        emoji: bool = True,
        viewer: str | None = None,
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
        # Prepare viewer kwargs
        viewer_kwargs = {
            "file": file,
            "emoji": emoji,
            "force_terminal": force_terminal,
            **kwargs,
        }
        # Create viewer (either specific or from settings)
        self._viewer = get_viewer(viewer, **viewer_kwargs)

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: str | Style | None = None,
        **kwargs: Any,
    ) -> None:
        """Print to the console with optional styling."""
        self._viewer.print(*objects, sep=sep, end=end, style=style, **kwargs)

    def rule(self, title: str = "", style: str | Style | None = None) -> None:
        """Print a horizontal rule."""
        self._viewer.rule(title, style=style)

    def clear(self) -> None:
        """Clear the console."""
        self._viewer.clear()

    def capture(self) -> CaptureContextProtocol:
        """Capture console output."""
        return self._viewer.capture()


class Table:
    """Table abstraction that delegates to the configured viewer."""

    def __init__(
        self,
        title: str | None = None,
        show_header: bool = True,
        header_style: str | None = None,
        **kwargs: Any,
    ):
        """Initialize the table."""
        viewer = get_viewer()
        self._table: TableProtocol = viewer.create_table(
            title=title, show_header=show_header, header_style=header_style, **kwargs
        )

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Add a column to the table."""
        self._table.add_column(header, justify=justify, style=style, **kwargs)

    def add_row(self, *values: Any) -> None:
        """Add a row to the table."""
        self._table.add_row(*values)

    def to_string(self, console: Console | None = None) -> str:
        """Convert the table to a string."""
        return self._table.to_string(console)


class Progress:
    """Progress bar abstraction that delegates to the configured viewer."""

    def __init__(
        self,
        *columns: Any,
        console: Console | None = None,
        refresh_per_second: float = 10,
        **kwargs: Any,
    ):
        """Initialize the progress bar."""
        viewer = get_viewer()
        self._progress: ProgressProtocol = viewer.create_progress(
            console=console, **kwargs
        )

    def add_task(
        self, description: str, total: float | None = None, **kwargs: Any
    ) -> int:
        """Add a task to the progress bar."""
        return self._progress.add_task(description, total=total, **kwargs)

    def update(
        self,
        task_id: int,
        advance: float | None = None,
        completed: float | None = None,
        total: float | None = None,
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

    def __enter__(self) -> Self:
        """Context manager entry."""
        self._progress.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
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
        self._syntax: SyntaxProtocol = viewer.create_syntax(
            code, lexer, theme=theme, line_numbers=line_numbers
        )

    def to_string(self, console: Console | None = None) -> str:
        """Convert to string representation."""
        return self._syntax.to_string(console)


class Text:
    """Text abstraction that delegates to the configured viewer."""

    def __init__(self, text: str = "", style: str | Style | None = None):
        """Initialize the text object."""
        viewer = get_viewer()
        self._text_obj: TextProtocol = viewer.create_text(text, style=style)

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


def get_console() -> Console:
    """Get the default console instance."""
    return console


# Register built-in viewers
# This happens after all module-level definitions to avoid circular imports
def _register_viewers() -> None:
    """Register built-in viewers after module initialization."""
    # Register print viewer (always available)
    from weave.trace.display.viewers import print_viewer

    print_viewer.register()

    # Register rich viewer if available
    try:
        from weave.trace.display.viewers import rich_viewer
    except ImportError:
        pass  # Rich viewer not available
    else:
        rich_viewer.register()


# Register viewers and create default console
_register_viewers()
console = Console()


__all__ = [
    "Console",
    "PaddingWrapper",
    "Progress",
    "Style",
    "SyntaxHighlight",
    "Table",
    "Text",
    "console",
    "get_viewer",
    "register_viewer",
]
