"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.interface.builtin_object_classes.test_only_example import (
    BaseModel,
    Field,
    TestOnlyExample,
    TestOnlyInheritedBaseObject,
    TestOnlyNestedBaseModel,
    TestOnlyNestedBaseObject,
    base_object_def,
)

__all__ = [
    "BaseModel",
    "Field",
    "TestOnlyExample",
    "TestOnlyInheritedBaseObject",
    "TestOnlyNestedBaseModel",
    "TestOnlyNestedBaseObject",
    "base_object_def",
]
