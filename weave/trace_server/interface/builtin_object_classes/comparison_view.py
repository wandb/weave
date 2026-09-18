"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.interface.builtin_object_classes.comparison_view import (
    BaseModel,
    ComparisonView,
    ComparisonViewDefinition,
    base_object_def,
)

__all__ = ["BaseModel", "ComparisonView", "ComparisonViewDefinition", "base_object_def"]
