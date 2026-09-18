"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.interface.builtin_object_classes.annotation_spec import (
    SUPPORTED_PRIMITIVES,
    AnnotationSpec,
    Any,
    BaseModel,
    Field,
    FieldInfo,
    base_object_def,
    create_model,
    field_validator,
    model_validator,
)

__all__ = [
    "SUPPORTED_PRIMITIVES",
    "AnnotationSpec",
    "Any",
    "BaseModel",
    "Field",
    "FieldInfo",
    "base_object_def",
    "create_model",
    "field_validator",
    "model_validator",
]
