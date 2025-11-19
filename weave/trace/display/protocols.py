"""Display system protocols.

This module defines the protocol interfaces that all viewer implementations
must follow. Using protocols provides better type checking and documentation
of the expected interface.
"""

from typing import Any, Optional, Protocol, runtime_checkable

from typing_extensions import Self

from weave.trace.display.types import Style


@runtime_checkable
class CaptureContextProtocol(Protocol):
    """Protocol for capture context objects."""

    def __enter__(self) -> "CaptureContextProtocol":
        """Enter the context."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context."""
        ...

    def get(self) -> str:
        """Get the captured output."""
        ...


@runtime_checkable
class TextProtocol(Protocol):
    """Protocol for styled text objects."""

    def __str__(self) -> str:
        """Get string representation."""
        ...


@runtime_checkable
class SyntaxProtocol(Protocol):
    """Protocol for syntax highlighting objects."""

    def to_string(self, console: Optional["ConsoleProtocol"] = None) -> str:
        """Convert to string representation."""
        ...


@runtime_checkable
class TableProtocol(Protocol):
    """Protocol for table objects."""

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Add a column to the table."""
        ...

    def add_row(self, *values: Any) -> None:
        """Add a row to the table."""
        ...

    def to_string(self, console: Optional["ConsoleProtocol"] = None) -> str:
        """Convert the table to a string."""
        ...


@runtime_checkable
class ProgressProtocol(Protocol):
    """Protocol for progress bar objects."""

    def add_task(
        self, description: str, total: float | None = None, **kwargs: Any
    ) -> int:
        """Add a task to the progress bar."""
        ...

    def update(
        self,
        task_id: int,
        advance: float | None = None,
        completed: float | None = None,
        total: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Update a task's progress."""
        ...

    def start(self) -> None:
        """Start the progress bar."""
        ...

    def stop(self) -> None:
        """Stop the progress bar."""
        ...

    def __enter__(self) -> Self:
        """Context manager entry."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        ...


@runtime_checkable
class ViewerProtocol(Protocol):
    """Protocol for display viewers.

    All viewer implementations must follow this protocol to ensure
    compatibility with the display system.
    """

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: str | Style | None = None,
        **kwargs: Any,
    ) -> None:
        """Print to the output with optional styling."""
        ...

    def rule(self, title: str = "", style: str | Style | None = None) -> None:
        """Print a horizontal rule."""
        ...

    def clear(self) -> None:
        """Clear the display."""
        ...

    def create_table(
        self,
        title: str | None = None,
        show_header: bool = True,
        header_style: str | None = None,
        **kwargs: Any,
    ) -> TableProtocol:
        """Create a table object."""
        ...

    def create_progress(
        self, console: Optional["ConsoleProtocol"] = None, **kwargs: Any
    ) -> ProgressProtocol:
        """Create a progress bar object."""
        ...

    def create_syntax(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ) -> SyntaxProtocol:
        """Create a syntax highlighting object."""
        ...

    def create_text(
        self, text: str = "", style: str | Style | None = None
    ) -> TextProtocol:
        """Create a styled text object."""
        ...

    def indent(self, content: str, amount: int) -> str:
        """Indent content by the specified amount."""
        ...

    def capture(self) -> CaptureContextProtocol:
        """Create a capture context for capturing output."""
        ...


@runtime_checkable
class ConsoleProtocol(Protocol):
    """Protocol for console objects."""

    _viewer: ViewerProtocol

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: str | Style | None = None,
        **kwargs: Any,
    ) -> None:
        """Print to the console with optional styling."""
        ...

    def rule(self, title: str = "", style: str | Style | None = None) -> None:
        """Print a horizontal rule."""
        ...

    def clear(self) -> None:
        """Clear the console."""
        ...

    def capture(self) -> CaptureContextProtocol:
        """Capture console output."""
        ...
