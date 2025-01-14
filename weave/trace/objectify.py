from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from weave.flow.obj import Object
    from weave.trace.vals import WeaveObject

T_co = TypeVar("T_co", bound="Object", covariant=True)


@runtime_checkable
class Objectifyable(Protocol[T_co]):
    @classmethod
    def from_obj(cls, obj: WeaveObject) -> T_co: ...


_registry: dict[str, type[Object]] = {}


def register_object(cls: type[T_co]) -> type[T_co]:
    _registry[cls.__name__] = cls
    return cls


def maybe_objectify(obj: WeaveObject) -> T_co | WeaveObject:
    if (cls_name := getattr(obj, "_class_name", None)) is None:
        return obj

    if (cls := _registry.get(cls_name)) is None:
        return obj

    res = cls.from_obj(obj)
    if ref := getattr(obj, "ref", None):
        res.ref = ref

    return res
