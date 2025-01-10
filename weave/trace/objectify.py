from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

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
    def from_uri(cls, uri: str) -> T:
        import weave

        return weave.ref(uri).get()

    cls.from_uri = from_uri

    return cls


def objectify(obj: WeaveObject) -> Any:
    if not (cls_name := getattr(obj, "_class_name", None)):
        return obj

    if cls_name not in _registry:
        return obj

    cls = _registry[cls_name]
    if issubclass(cls, BaseModel):
        params = cls.model_fields
    else:
        params = inspect.signature(cls.__init__).parameters
    fields = {f: getattr(obj, f) for f in params if f != "self" and hasattr(obj, f)}

    obj = cls(**fields)
    obj.__dict__["ref"] = obj.ref
    return obj
