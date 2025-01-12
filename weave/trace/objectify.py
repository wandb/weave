from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from weave.trace.vals import WeaveObject

T = TypeVar("T")


@runtime_checkable
class Objectifyable(Protocol):
    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Any: ...
