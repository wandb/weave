from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from weave.trace.vals import WeaveObject

T = TypeVar("T")


_registry: dict[str, T] = {}


@runtime_checkable
class Objectifyable(Protocol):
    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Any: ...


def register_object(cls: type) -> type:
    _registry[cls.__name__] = cls
    return cls


def get_cls(cls_name: str) -> T:
    if cls_name not in _registry:
        raise ValueError(f"No objectifyable class found for {cls_name}")
    return _registry[cls_name]
