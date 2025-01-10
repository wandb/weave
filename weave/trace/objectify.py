from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from weave.trace.vals import WeaveObject

_registry: dict[str, type] = {}


def register(cls: type) -> type:
    _registry[cls.__name__] = cls
    return cls


def objectify(obj: WeaveObject) -> Any:
    if not (cls_name := getattr(obj, "_class_name", None)):
        return obj

    cls = _registry[cls_name]
    if issubclass(cls, BaseModel):
        params = cls.model_fields
    else:
        params = inspect.signature(cls.__init__).parameters
    fields = {f: getattr(obj, f) for f in params if f != "self" and hasattr(obj, f)}

    return cls(**fields)
