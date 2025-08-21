# Display Module

The display module provides a unified interface for console output with a pluggable viewer system. This allows users to configure their preferred display method (rich, print, etc.) without changing their code.

The APIs are primarily intended for internal use by the weave library. `set_viewer` is the only public API and allows users to configure their preferred viewer.

## Features

- **Pluggable Viewer System**: Easy to add new output backends
- **Auto-detection**: Automatically uses the best available viewer
- **Graceful Fallback**: Falls back to basic print when rich is not available
- **Per-Console Configuration**: Different consoles can use different viewers
- **Extensible**: Easy to create custom viewers for specific needs

## Usage

### Basic Usage

```python
from weave.trace.display import display

# Create a console (uses auto-detected viewer by default)
console = display.Console()

# Print with optional styling
console.print("Hello, World!")

style = display.Style(color="green", bold=True)
console.print("Styled text", style=style)

# Create and display a table
table = display.Table(title="My Table")
table.add_column("Name", justify="left")
table.add_column("Value", justify="right")
table.add_row("Item 1", "100")
table.add_row("Item 2", "200")
print(table.to_string(console))
```

### Configuring Viewers

```python
from weave.trace.display import display

# Set the global viewer
display.set_viewer("print")  # Use print viewer
display.set_viewer("rich")   # Use rich viewer (if available)
display.set_viewer("auto")   # Auto-detect (default)

# Create a console with a specific viewer
console = display.Console(viewer="print")  # Always uses print
```

### Creating Custom Viewers

```python
from weave.trace.display import display
from weave.trace.display.protocols import TableProtocol, ProgressProtocol
from weave.trace.display.types import Style

class MyCustomViewer:
    """Custom viewer implementation."""

    def print(self, *objects, sep=" ", end="\n", style=None, **kwargs):
        # Custom implementation
        output = sep.join(str(obj) for obj in objects)
        if isinstance(style, Style):
            output = style.to_ansi(output)
        print(f"[CUSTOM] {output}", end=end)

    def rule(self, title="", style=None):
        # Custom rule implementation
        print(f"=== {title} ===")

    def create_table(self, title=None, show_header=True, **kwargs) -> TableProtocol:
        # Return an object that implements TableProtocol
        return MyCustomTable(title, show_header)

    # ... implement other required protocol methods ...

# Register the custom viewer
display.register_viewer("custom", MyCustomViewer)

# Use it
display.set_viewer("custom")
```

## Available Viewers

### Rich Viewer

- **Name**: `"rich"`
- **Features**: Full rich library support with colors, tables, progress bars
- **Requirements**: `pip install rich`

### Print Viewer

- **Name**: `"print"`
- **Features**: Basic print output with ANSI color support
- **Requirements**: None (built-in)

## Architecture

### Viewer Protocol

All viewers must implement the `ViewerProtocol` defined in `protocols.py`.

```python
@runtime_checkable
class ViewerProtocol(Protocol):
    def print(self, *objects, sep=" ", end="\n", style=None, **kwargs) -> None:
        """Print to the output with optional styling."""
        ...

    def rule(self, title="", style=None) -> None:
        """Print a horizontal rule."""
        ...

    def clear(self) -> None:
        """Clear the display."""
        ...

    def create_table(self, title=None, show_header=True, **kwargs) -> TableProtocol:
        """Create a table object."""
        ...

    def create_progress(self, console=None, **kwargs) -> ProgressProtocol:
        """Create a progress bar object."""
        ...

    def create_syntax(self, code, lexer, theme="ansi_dark", line_numbers=False) -> SyntaxProtocol:
        """Create a syntax highlighting object."""
        ...

    def create_text(self, text="", style=None) -> TextProtocol:
        """Create a styled text object."""
        ...

    def indent(self, content, amount) -> str:
        """Indent content by the specified amount."""
        ...

    def capture(self) -> CaptureContextProtocol:
        """Create a capture context for capturing output."""
        ...
```

Similar protocols exist for `TableProtocol`, `ProgressProtocol`, `SyntaxProtocol`, and `TextProtocol`.

## Display Objects

The abstraction layer provides several display objects that work with any viewer:

- **Console**: Main interface for output operations
- **Table**: Tabular data display
- **Progress**: Progress bar tracking
- **Text**: Styled text
- **SyntaxHighlight**: Code syntax highlighting
- **PaddingWrapper**: Text indentation utilities
