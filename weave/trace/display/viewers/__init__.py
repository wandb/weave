"""Display viewer implementations.

This package contains various viewer implementations for the display abstraction layer.
"""

# Optional imports - viewers may not all be available
__all__ = ["PrintViewer"]

try:
    from weave.trace.display.viewers.rich_viewer import RichViewer  # noqa: F401

    __all__.append("RichViewer")
except ImportError:
    pass  # Rich viewer not available

from weave.trace.display.viewers.print_viewer import PrintViewer

__all__.append("PrintViewer")
