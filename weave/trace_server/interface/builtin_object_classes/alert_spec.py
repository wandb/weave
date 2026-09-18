"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.interface.builtin_object_classes.alert_spec import (
    AlertSpec,
    BaseModel,
    ConfigDict,
    Field,
    Literal,
    WeaveMetricThresholdSpec,
    base_object_def,
)

__all__ = [
    "AlertSpec",
    "BaseModel",
    "ConfigDict",
    "Field",
    "Literal",
    "WeaveMetricThresholdSpec",
    "base_object_def",
]
