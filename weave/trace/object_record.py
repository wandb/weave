import inspect
import pydantic

from typing import Any, Callable

from weave.trace.op import Op


class ObjectRecord:
    _class_name: str
    _bases: list[str]

    def __init__(self, attrs: dict[str, Any]) -> None:
        for k, v in attrs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f"ObjectRecord({self.__dict__})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ObjectRecord):
            if self._class_name != other._class_name:
                return False
        else:
            if other.__class__.__name__ != getattr(self, "_class_name"):
                return False
        for k, v in self.__dict__.items():
            if k == "_class_name" or k == "_bases":
                continue
            if getattr(other, k) != v:
                return False
        return True

    def map_values(self, fn: Callable) -> "ObjectRecord":
        return ObjectRecord({k: fn(v) for k, v in self.__dict__.items()})


def pydantic_asdict_one_level(obj: pydantic.BaseModel) -> dict[str, Any]:
    return {k: getattr(obj, k) for k in obj.model_fields}


def class_all_bases_names(cls: type) -> list[str]:
    # Don't include cls and don't include object
    return [c.__name__ for c in cls.mro()[1:-1]]


def pydantic_object_record(obj: pydantic.BaseModel) -> ObjectRecord:
    attrs = pydantic_asdict_one_level(obj)
    for k, v in inspect.getmembers(obj, lambda x: isinstance(x, Op)):
        attrs[k] = v
    attrs["_class_name"] = obj.__class__.__name__
    attrs["_bases"] = class_all_bases_names(obj.__class__)
    return ObjectRecord(attrs)
