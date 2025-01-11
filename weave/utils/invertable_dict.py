from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any, TypeVar

KT = TypeVar("KT")
VT = TypeVar("VT")


class InvertableDict(MutableMapping[KT, VT]):
    """A bijective mapping that behaves like a dict.

    Invert the dict using the `inv` property.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._forward = dict(*args, **kwargs)
        self._backward: dict[VT, KT] = {}
        for key, value in self._forward.items():
            if value in self._backward:
                raise ValueError(f"Duplicate value found: {value}")
            self._backward[value] = key

    def __getitem__(self, key: KT) -> VT:
        return self._forward[key]

    def __setitem__(self, key: KT, value: VT) -> None:
        if key in self._forward:
            del self._backward[self._forward[key]]
        if value in self._backward:
            raise ValueError(f"Duplicate value found: {value}")
        self._forward[key] = value
        self._backward[value] = key

    def __delitem__(self, key: KT) -> None:
        value = self._forward.pop(key)
        del self._backward[value]

    def __iter__(self) -> Iterator[KT]:
        return iter(self._forward)

    def __len__(self) -> int:
        return len(self._forward)

    def __repr__(self) -> str:
        return repr(self._forward)

    def __contains__(self, key: Any) -> bool:
        return key in self._forward

    @property
    def inv(self) -> InvertableDict[VT, KT]:
        res = InvertableDict[VT, KT]()
        res._forward = self._backward
        res._backward = self._forward
        return res
