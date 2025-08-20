# Display Abstraction Layer

The display abstraction layer provides a unified interface for console output with a pluggable viewer system. This allows users to configure their preferred display method (rich, print, logger, etc.) without changing their code.

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

class MyCustomViewer(display.BaseViewer):
    def print(self, *objects, sep=" ", end="\n", style=None, **kwargs):
        # Custom implementation
        output = sep.join(str(obj) for obj in objects)
        print(f"[CUSTOM] {output}", end=end)

    def rule(self, title="", style=None):
        # Custom rule implementation
        print(f"=== {title} ===")

    # ... implement other required methods ...

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

### Logger Viewer (Example)

- **Name**: `"logger"` (when registered)
- **Features**: Routes all output through Python's logging system
- **Use Case**: Applications that prefer structured logging

## Viewer Interface

All viewers must implement the `BaseViewer` abstract class:

```python
class BaseViewer(ABC):
    @abstractmethod
    def print(self, *objects, sep=" ", end="\n", style=None, **kwargs):
        """Print to the output with optional styling."""

    @abstractmethod
    def rule(self, title="", style=None):
        """Print a horizontal rule."""

    @abstractmethod
    def clear(self):
        """Clear the display."""

    @abstractmethod
    def create_table(self, title=None, show_header=True, **kwargs):
        """Create a table object."""

    @abstractmethod
    def create_progress(self, console=None, **kwargs):
        """Create a progress bar object."""

    @abstractmethod
    def create_syntax(self, code, lexer, theme="ansi_dark", line_numbers=False):
        """Create a syntax highlighting object."""

    @abstractmethod
    def create_text(self, text="", style=None):
        """Create a styled text object."""

    @abstractmethod
    def indent(self, content, amount):
        """Indent content by the specified amount."""

    @abstractmethod
    def capture(self):
        """Create a capture context for capturing output."""
```

## Display Objects

The abstraction layer provides several display objects that work with any viewer:

- **Console**: Main interface for output operations
- **Table**: Tabular data display
- **Progress**: Progress bar tracking
- **Text**: Styled text
- **SyntaxHighlight**: Code syntax highlighting
- **PaddingWrapper**: Text indentation utilities

## Benefits

1. **Flexibility**: Switch between output methods without code changes
2. **Testing**: Easy to mock or capture output for testing
3. **Compatibility**: Works in environments where rich is not available
4. **Extensibility**: Add new output methods as needed
5. **Future-proof**: New viewers can be added without breaking existing code

## Migration from Direct Rich Usage

If you're currently using rich directly:

```python
# Before (direct rich usage)
from rich.console import Console
from rich.table import Table

console = Console()
console.print("Hello")

# After (display abstraction)
from weave.trace.display import display

console = display.Console()
console.print("Hello")
```

The API is designed to be similar to rich, making migration straightforward.
