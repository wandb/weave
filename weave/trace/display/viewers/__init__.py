"""Display viewer implementations.

This package contains various viewer implementations for the display abstraction layer.
"""

# Optional imports - viewers may not all be available
__all__ = []

try:
    from weave.trace.display.viewers.rich_viewer import RichViewer
    __all__.append("RichViewer")
except ImportError:
    pass  # Rich viewer not available

from weave.trace.display.viewers.print_viewer import PrintViewer
__all__.append("PrintViewer")

# Logger viewer is optional and should be imported explicitly if needed
# from weave.trace.display.viewers.logger_viewer import LoggerViewer
