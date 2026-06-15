"""High-level tests for the display abstraction layer.

These tests verify the public API and behavior of the display module
without testing implementation details.
"""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from weave.trace.display import display
from weave.trace.display.types import Style


def test_viewer_selection_auto_explicit_and_env():
    """auto/print/rich selection works directly and via WEAVE_DISPLAY_VIEWER."""
    auto_console = display.Console(viewer="auto")
    assert auto_console is not None
    assert hasattr(auto_console, "print")
    assert hasattr(auto_console, "rule")

    assert display.Console(viewer="print") is not None
    try:
        import rich  # noqa: F401

        assert display.Console(viewer="rich") is not None
    except ImportError:
        pass

    original_viewer = os.environ.get("WEAVE_DISPLAY_VIEWER")
    try:
        os.environ["WEAVE_DISPLAY_VIEWER"] = "print"
        assert display.Console() is not None
        os.environ["WEAVE_DISPLAY_VIEWER"] = "auto"
        assert display.Console() is not None
    finally:
        if original_viewer is not None:
            os.environ["WEAVE_DISPLAY_VIEWER"] = original_viewer
        else:
            os.environ.pop("WEAVE_DISPLAY_VIEWER", None)


def test_auto_viewer_falls_back_to_print():
    """auto viewer survives a rich ImportError, both at construction and in get."""
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if "rich" in name:
            raise ImportError("Rich not available")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        console = display.Console(viewer="auto")
        assert console is not None
        assert hasattr(console, "print")

    from weave.trace.display.display import _get_auto_viewer

    with patch(
        "weave.trace.display.viewers.rich_viewer.RichViewer", side_effect=ImportError
    ):
        viewer = _get_auto_viewer()
        assert viewer is not None
        assert hasattr(viewer, "print")
        assert hasattr(viewer, "rule")


def test_error_handling_for_unknown_viewer():
    """An unknown viewer name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown viewer"):
        display.Console(viewer="nonexistent_viewer")


def test_console_print_styling_objects_and_end():
    """Console print handles plain text, styling, multiple objects, and custom end."""
    captured_output = StringIO()
    console = display.Console(viewer="print", file=captured_output)

    console.print("Hello, World!")
    console.print("Styled text", style=Style(color="green", bold=True))
    console.print("First", "Second", "Third", sep=" | ")
    console.print("Line 1", end=" -> ")
    console.print("Line 2")

    output = captured_output.getvalue()
    assert "Hello, World!" in output
    assert "Styled text" in output
    assert "First | Second | Third" in output
    assert "Line 1 -> Line 2" in output


def test_multiple_console_instances():
    """Test that multiple console instances can coexist."""
    # Both should work independently
    captured1 = StringIO()
    captured2 = StringIO()

    console1 = display.Console(viewer="print", file=captured1)
    console2 = display.Console(viewer="auto", file=captured2)

    console1.print("Console 1")
    console2.print("Console 2")

    assert "Console 1" in captured1.getvalue()
    assert "Console 2" in captured2.getvalue()


def test_console_rule():
    """Console rule prints its title."""
    captured_output = StringIO()
    console = display.Console(viewer="print", file=captured_output)

    console.rule("Section Title")
    assert "Section Title" in captured_output.getvalue()


def test_table_with_and_without_header():
    """Tables render their data with a header and with show_header=False."""
    console = display.Console(viewer="print")

    table = display.Table(title="Test Table")
    table.add_column("Name", justify="left")
    table.add_column("Value", justify="right")
    table.add_row("Item 1", "100")
    table.add_row("Item 2", "200")
    table_str = table.to_string(console)
    assert "Test Table" in table_str
    assert "Item 1" in table_str
    assert "100" in table_str
    assert "Item 2" in table_str
    assert "200" in table_str

    headerless = display.Table(show_header=False)
    headerless.add_column("Key")
    headerless.add_column("Value")
    headerless.add_row("name", "test")
    headerless.add_row("count", "42")
    headerless_str = headerless.to_string(console)
    assert "name" in headerless_str
    assert "test" in headerless_str
    assert "42" in headerless_str


def test_progress_bar_operations():
    """Progress start/add_task/update/stop run without error."""
    console = display.Console(viewer="print")
    progress = display.Progress(console=console)

    progress.start()
    task_id = progress.add_task("Processing", total=100)
    assert task_id is not None
    progress.update(task_id, completed=50)
    progress.stop()


def test_text_and_style_creation():
    """Text wraps a string; Style records attributes and renders ANSI."""
    text = display.Text("Hello", style=Style(color="blue"))
    assert "Hello" in str(text)

    style1 = Style(color="red")
    assert style1.color == "red"

    style2 = Style(color="blue", bold=True, italic=True, underline=True)
    assert style2.color == "blue"
    assert style2.bold is True
    assert style2.italic is True
    assert style2.underline is True

    ansi_text = Style(color="green", bold=True).to_ansi("Hello")
    assert "Hello" in ansi_text
    assert "\033[" in ansi_text


def test_syntax_highlighting():
    """Syntax highlighting preserves the raw code text."""
    code = """def hello():
    print("Hello, World!")"""

    syntax = display.SyntaxHighlight(code=code, lexer="python")
    console = display.Console(viewer="print")
    syntax_str = syntax.to_string(console)
    assert "hello" in syntax_str
    assert "print" in syntax_str
    assert "Hello, World!" in syntax_str


def test_padding_wrapper():
    """PaddingWrapper.indent prefixes every non-empty line with spaces."""
    indented = display.PaddingWrapper.indent("Line 1\nLine 2", 4)

    lines = indented.split("\n")
    assert all(line.startswith("    ") or line == "" for line in lines if line)
    assert "Line 1" in indented
    assert "Line 2" in indented


def test_capture_context():
    """Test that capture context can be created and used."""
    console = display.Console(viewer="print")

    # Test that capture context can be created
    capture_ctx = console.capture()
    assert capture_ctx is not None

    # Test capture with rich viewer if available
    try:
        import rich  # noqa: F401

        rich_console = display.Console(viewer="rich")
        with rich_console.capture() as capture:
            rich_console.print("Captured text")
        output = capture.get()
        assert "Captured text" in output
    except ImportError:
        # If rich is not available, just test that capture context works
        # Note: print viewer's capture has limitations due to how file handles are stored
        with capture_ctx as capture:
            # The capture context should work without errors
            pass
        output = capture.get()
        # Output may be empty due to print viewer limitations
        assert output is not None


def test_viewer_registry():
    """A custom viewer can be registered and used by name."""
    display.register_viewer("custom_test", _CustomViewer)

    old_stdout = sys.stdout
    try:
        sys.stdout = StringIO()
        console = display.Console(viewer="custom_test")
        console.print("Test message")
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    assert "[CUSTOM]" in output
    assert "Test message" in output


class _CustomViewer:
    """A minimal custom viewer for registry testing."""

    def __init__(self, **kwargs):
        pass

    def print(self, *objects, sep=" ", end="\n", style=None, **kwargs):
        output = sep.join(str(obj) for obj in objects)
        print(f"[CUSTOM] {output}", end=end)

    def rule(self, title="", style=None):
        print(f"=== {title} ===")

    def clear(self):
        pass

    def create_table(self, title=None, show_header=True, header_style=None, **kwargs):
        return MagicMock()

    def create_progress(self, console=None, **kwargs):
        return MagicMock()

    def create_syntax(self, code, lexer, theme="ansi_dark", line_numbers=False):
        return MagicMock()

    def create_text(self, text="", style=None):
        return MagicMock()

    def indent(self, content, amount):
        return " " * amount + content.replace("\n", "\n" + " " * amount)

    def capture(self):
        return MagicMock()
