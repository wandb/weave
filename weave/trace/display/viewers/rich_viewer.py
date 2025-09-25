"""Rich library viewer implementation."""

from __future__ import annotations

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


class RichViewer:
    """Viewer implementation using the rich library."""

    def __init__(
        self,
        file: Any = None,
        emoji: bool = True,
        force_terminal: bool | None = None,
        **kwargs: Any,
    ):
        from rich.console import Console as RichConsole

        self._file = file
        self._emoji = emoji
        self._console = RichConsole(
            file=file, force_terminal=force_terminal, emoji=emoji, **kwargs
        )

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: str | Style | None = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(style, Style):
            kwargs["style"] = style.to_rich_style()
        elif style:
            kwargs["style"] = style
        self._console.print(*objects, sep=sep, end=end, **kwargs)

    def rule(self, title: str = "", style: str | Style | None = None) -> None:
        if isinstance(style, Style):
            style = style.to_rich_style()
        self._console.rule(title, style=style)

    def clear(self) -> None:
        self._console.clear()

    def create_table(
        self,
        title: str | None = None,
        show_header: bool = True,
        header_style: str | None = None,
        **kwargs: Any,
    ) -> TableProtocol:
        return RichTable(
            title=title, show_header=show_header, header_style=header_style, **kwargs
        )

    def create_progress(
        self, console: ConsoleProtocol | None = None, **kwargs: Any
    ) -> ProgressProtocol:
        return RichProgress(console=self._console, **kwargs)

    def create_syntax(
        self,
        code: str,
        lexer: str,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
    ) -> SyntaxProtocol:
        return RichSyntax(code, lexer, theme=theme, line_numbers=line_numbers)

    def create_text(
        self, text: str = "", style: str | Style | None = None
    ) -> TextProtocol:
        return RichText(text, style=style)

    def indent(self, content: str, amount: int) -> str:
        # Rich's Padding.indent returns a Padding object, but we need a string
        # So we'll manually indent the content
        indent_str = " " * amount
        lines = content.split("\n")
        return "\n".join(indent_str + line if line else line for line in lines)

    def capture(self) -> CaptureContextProtocol:
        return self._console.capture()


class RichTable:
    """Rich table implementation."""

    def __init__(
        self,
        title: str | None = None,
        show_header: bool = True,
        header_style: str | None = None,
        **kwargs: Any,
    ):
        from rich.table import Table as RichTableBase

        self._table = RichTableBase(
            title=title, show_header=show_header, header_style=header_style, **kwargs
        )

    def add_column(
        self,
        header: str,
        justify: str = "left",
        style: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._table.add_column(header, justify=justify, style=style, **kwargs)

    def add_row(self, *values: Any) -> None:
        # Convert any weave Table objects to their Rich representation
        processed_values = []
        for value in values:
            # Check if this is a weave Table object
            if hasattr(value, "_table") and hasattr(value._table, "_table"):
                # If it's a RichTable, use the underlying Rich table
                if isinstance(value._table, RichTable):
                    processed_values.append(value._table._table)
                else:
                    # Otherwise convert to string
                    processed_values.append(value.to_string())
            else:
                processed_values.append(value)
        self._table.add_row(*processed_values)

    def to_string(self, console: ConsoleProtocol | None = None) -> str:
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


class RichProgress:
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
        self, description: str, total: float | None = None, **kwargs: Any
    ) -> int:
        return self._progress.add_task(description, total=total, **kwargs)

    def update(
        self,
        task_id: int,
        advance: float | None = None,
        completed: float | None = None,
        total: float | None = None,
        **kwargs: Any,
    ) -> None:
        self._progress.update(
            task_id, advance=advance, completed=completed, total=total, **kwargs
        )

    def start(self) -> None:
        self._progress.start()

    def stop(self) -> None:
        self._progress.stop()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


class RichSyntax:
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

    def to_string(self, console: ConsoleProtocol | None = None) -> str:
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


class RichText:
    """Rich text implementation."""

    def __init__(self, text: str = "", style: str | Style | None = None):
        from rich.text import Text as RichTextBase

        if isinstance(style, Style):
            style = style.to_rich_style()
        self._text = RichTextBase(text, style=style)

    def __str__(self) -> str:
        return str(self._text)

    def __repr__(self) -> str:
        return repr(self._text)


# Registration function to be called by display module
def register() -> None:
    """Register the rich viewer with the display system.

    This function is called by the display module after initialization
    to avoid circular import issues.
    """
    from weave.trace.display import display

    display.register_viewer("rich", RichViewer)
