from __future__ import annotations

from typing import Any, Protocol


class ObjectPreparer(Protocol):
    """An initializer to ensure saved Weave objects are safe to load back to their original types.

    In many cases, this will be some form of deepcopy to ensure all the data is loaded
    into memory before attempting to return the object.
    """

    def should_prepare(self, obj: Any) -> bool: ...
    def prepare(self, obj: Any) -> None: ...


_object_preparers: list[ObjectPreparer] = []


def register(preparer: ObjectPreparer) -> None:
    _object_preparers.append(preparer)


def maybe_get_preparer(obj: Any) -> ObjectPreparer | None:
    for initializer in _object_preparers:
        if initializer.should_prepare(obj):
            return initializer
    return None


def prepare_obj(obj: Any) -> None:
    if preparer := maybe_get_preparer(obj):
        preparer.prepare(obj)
