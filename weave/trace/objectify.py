from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from weave.trace.vals import WeaveObject

_registry: dict[str, type] = {}


T = TypeVar("T")


def register(cls: type[T]) -> type[T]:
    """Decorator to register a class with the objectify function.

    Registered classes will be able to be deserialized directly into their base objects
    instead of into a WeaveObject."""
    _registry[cls.__name__] = cls

    @classmethod
    def from_uri(cls: type[T], uri: str) -> T:
        import weave

        obj = weave.ref(uri).get()
        if isinstance(obj, cls):
            return obj
        return cls(**obj.model_dump())

    cls.from_uri = from_uri

    return cls


def objectify(obj: WeaveObject) -> Any:
    if not (cls_name := getattr(obj, "_class_name", None)):
        return obj

    if cls_name not in _registry:
        return obj

    cls = _registry[cls_name]
    if hasattr(cls, "from_uri"):
        return cls.from_uri(obj.ref.uri())

    return obj
