from __future__ import annotations

from typing import Any, TypeVar

from typing_extensions import TypeGuard

from weave.trace.object_record import ObjectRecord
from weave.trace.vals import WeaveObject

C = TypeVar("C")


def weave_isinstance(obj: Any, cls: type[C] | tuple[type[C], ...]) -> TypeGuard[C]:
    if isinstance(cls, tuple):
        return any(weave_isinstance(obj, c) for c in cls)
    if isinstance(obj, cls):  # type: ignore
        return True
    if isinstance(obj, ObjectRecord):
        return obj._class_name == cls.__name__ or any(
            b == cls.__name__ for b in obj._bases
        )
    if isinstance(obj, WeaveObject):
        return obj._class_name == cls.__name__ or any(
            b == cls.__name__ for b in obj._bases
        )
    return False
