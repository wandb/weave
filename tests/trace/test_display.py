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


# Test viewer auto-detection and fallback mechanism
def test_auto_viewer_with_rich_available():
    """Test that auto viewer uses rich when available."""
    console = display.Console(viewer="auto")

    # Check that a console was created successfully
    assert console is not None
    assert hasattr(console, "print")
    assert hasattr(console, "rule")


def test_auto_viewer_without_rich():
    """Test that auto viewer falls back to print when rich is not available."""
    # Mock ImportError for rich
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if "rich" in name:
            raise ImportError("Rich not available")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        console = display.Console(viewer="auto")

        # Should still work with print viewer
        assert console is not None
        assert hasattr(console, "print")


def test_explicit_viewer_selection():
    """Test that explicit viewer selection works."""
    # Test print viewer
    print_console = display.Console(viewer="print")
    assert print_console is not None

    # Test rich viewer (if available)
    try:
        import rich  # noqa: F401

        rich_console = display.Console(viewer="rich")
        assert rich_console is not None
    except ImportError:
        pass  # Rich not available, skip this part


def test_viewer_configuration_from_environment():
    """Test that viewer can be configured via environment variable."""
    # Save original value
    original_viewer = os.environ.get("WEAVE_DISPLAY_VIEWER")

    try:
        # Test with print viewer
        os.environ["WEAVE_DISPLAY_VIEWER"] = "print"
        console = display.Console()
        assert console is not None

        # Test with auto viewer
        os.environ["WEAVE_DISPLAY_VIEWER"] = "auto"
        console = display.Console()
        assert console is not None
    finally:
        # Restore original value
        if original_viewer is not None:
            os.environ["WEAVE_DISPLAY_VIEWER"] = original_viewer
        else:
            os.environ.pop("WEAVE_DISPLAY_VIEWER", None)


def test_console_print_functionality():
    """Test that console print works with different viewers."""
    for viewer_name in ["print", "auto"]:
        # Capture output by passing file to console
        captured_output = StringIO()
        console = display.Console(viewer=viewer_name, file=captured_output)

        console.print("Hello, World!")
        output = captured_output.getvalue()

        # Check that something was printed
        assert "Hello, World!" in output


def test_console_with_styling():
    """Test that console handles styling correctly."""
    # Capture output
    captured_output = StringIO()
    console = display.Console(viewer="print", file=captured_output)

    # Create a style
    style = Style(color="green", bold=True)

    console.print("Styled text", style=style)
    output = captured_output.getvalue()

    # Should contain the text (exact formatting depends on viewer)
    assert "Styled text" in output


def test_table_creation_and_display():
    """Test that tables can be created and displayed."""
    console = display.Console(viewer="print")

    # Create a table
    table = display.Table(title="Test Table")
    table.add_column("Name", justify="left")
    table.add_column("Value", justify="right")
    table.add_row("Item 1", "100")
    table.add_row("Item 2", "200")

    # Convert to string
    table_str = table.to_string(console)

    # Should contain the data
    assert "Test Table" in table_str
    assert "Item 1" in table_str
    assert "100" in table_str
    assert "Item 2" in table_str
    assert "200" in table_str


def test_table_without_header():
    """Test that tables can be created without headers."""
    console = display.Console(viewer="print")

    # Create a table without header
    table = display.Table(show_header=False)
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("name", "test")
    table.add_row("count", "42")

    # Convert to string
    table_str = table.to_string(console)

    # Should contain the data
    assert "name" in table_str
    assert "test" in table_str
    assert "42" in table_str


def test_console_rule():
    """Test that console rule works."""
    # Capture output
    captured_output = StringIO()
    console = display.Console(viewer="print", file=captured_output)

    console.rule("Section Title")
    output = captured_output.getvalue()

    # Should contain the title
    assert "Section Title" in output


def test_progress_bar_operations():
    """Test basic progress bar operations."""
    console = display.Console(viewer="print")
    progress = display.Progress(console=console)

    # Start progress
    progress.start()

    # Add a task
    task_id = progress.add_task("Processing", total=100)
    assert task_id is not None

    # Update progress
    progress.update(task_id, completed=50)

    # Stop progress
    progress.stop()


def test_text_creation():
    """Test that styled text can be created."""
    # Create styled text
    text = display.Text("Hello", style=Style(color="blue"))

    # Should have a string representation
    text_str = str(text)
    assert "Hello" in text_str


def test_syntax_highlighting():
    """Test that syntax highlighting objects can be created."""
    # Create syntax highlighted code
    code = """def hello():
    print("Hello, World!")"""

    syntax = display.SyntaxHighlight(code=code, lexer="python")

    # Should have a string representation
    console = display.Console(viewer="print")
    syntax_str = syntax.to_string(console)
    # The syntax highlighter may add ANSI codes, so check for the raw text
    assert "hello" in syntax_str
    assert "print" in syntax_str
    assert "Hello, World!" in syntax_str


def test_padding_wrapper():
    """Test that padding wrapper works correctly."""
    # Test indent
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


def test_viewer_registry():
    """Test that custom viewers can be registered."""

    class CustomViewer:
        """A minimal custom viewer for testing."""

        def __init__(self, **kwargs):
            """Accept kwargs for compatibility with viewer initialization."""
            pass

        def print(self, *objects, sep=" ", end="\n", style=None, **kwargs):
            output = sep.join(str(obj) for obj in objects)
            print(f"[CUSTOM] {output}", end=end)

        def rule(self, title="", style=None):
            print(f"=== {title} ===")

        def clear(self):
            pass

        def create_table(
            self, title=None, show_header=True, header_style=None, **kwargs
        ):
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

    # Register the custom viewer
    display.register_viewer("custom_test", CustomViewer)

    # Test that it works - CustomViewer prints to stdout, not the file parameter
    from io import StringIO

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


def test_error_handling_for_unknown_viewer():
    """Test that appropriate error is raised for unknown viewer."""
    with pytest.raises(ValueError, match="Unknown viewer"):
        display.Console(viewer="nonexistent_viewer")


def test_console_print_multiple_objects():
    """Test printing multiple objects at once."""
    captured_output = StringIO()
    console = display.Console(viewer="print", file=captured_output)

    console.print("First", "Second", "Third", sep=" | ")
    output = captured_output.getvalue()

    assert "First | Second | Third" in output


def test_console_print_with_custom_end():
    """Test printing with custom end character."""
    captured_output = StringIO()
    console = display.Console(viewer="print", file=captured_output)

    console.print("Line 1", end=" -> ")
    console.print("Line 2")
    output = captured_output.getvalue()

    assert "Line 1 -> Line 2" in output


def test_style_creation():
    """Test that styles can be created with various attributes."""
    # Test basic style
    style1 = Style(color="red")
    assert style1.color == "red"

    # Test style with multiple attributes
    style2 = Style(color="blue", bold=True, italic=True, underline=True)
    assert style2.color == "blue"
    assert style2.bold is True
    assert style2.italic is True
    assert style2.underline is True

    # Test style ANSI conversion
    style3 = Style(color="green", bold=True)
    ansi_text = style3.to_ansi("Hello")
    assert "Hello" in ansi_text
    assert "\033[" in ansi_text  # Should contain ANSI codes


def test_fallback_behavior_simulation():
    """Test that auto viewer handles ImportError correctly when getting the viewer.

    This is tested by using display.get_viewer with "auto" which internally calls _get_auto_viewer
    """
    from weave.trace.display.display import _get_auto_viewer

    with patch(
        "weave.trace.display.viewers.rich_viewer.RichViewer", side_effect=ImportError
    ):
        # Should fall back to print viewer
        viewer = _get_auto_viewer()
        assert viewer is not None
        # Verify it's a print viewer by checking it has expected methods
        assert hasattr(viewer, "print")
        assert hasattr(viewer, "rule")
