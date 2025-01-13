from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from weave.trace.vals import WeaveObject

if TYPE_CHECKING:
    from weave.flow.obj import Object

T_co = TypeVar("T_co", bound="Object", covariant=True)


@runtime_checkable
class Objectifyable(Protocol[T_co]):
    @classmethod
    def from_obj(cls, obj: WeaveObject) -> T_co: ...


_registry: dict[str, type[Object]] = {}


def register_object(cls: type[T_co]) -> type[T_co]:
    _registry[cls.__name__] = cls
    return cls


def get_cls(cls_name: str) -> type[Object]:
    if cls_name not in _registry:
        raise ValueError(f"No objectifyable class found for `{cls_name}`")
    return _registry[cls_name]
