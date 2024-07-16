"""Alternate boxing implementation for Weave Trace.

This copies many things from weave/legacy/box.py, but it notably
does not box None and bool which simplify checks for trace users."""

from __future__ import annotations

import datetime
from typing import Any, TypeVar

import numpy as np

T = TypeVar("T")


class HasBoxedRepr:
    val: Any

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} ({self.val})>"


class BoxedBool(HasBoxedRepr):
    _id: int | None = None

    def __init__(self, val: bool) -> None:
        self.val = val

    def __bool__(self) -> bool:
        return self.val

    def __hash__(self) -> int:
        return hash(self.val)

    def __eq__(self, other: Any) -> bool:
        return self.val == other


class BoxedInt(int):
    _id: int | None = None


class BoxedFloat(float):
    _id: int | None = None


class BoxedStr(str):
    _id: int | None = None


class BoxedDatetime(datetime.datetime):
    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, datetime.datetime)
            and self.timestamp() == other.timestamp()
        )


class BoxedTimedelta(datetime.timedelta):
    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, datetime.timedelta)
            and self.total_seconds() == other.total_seconds()
        )


# See https://numpy.org/doc/stable/user/basics.subclassing.html
class BoxedNDArray(np.ndarray):
    def __new__(cls, input_array: Any) -> BoxedNDArray:
        obj = np.asarray(input_array).view(cls)
        return obj

    def __array_finalize__(self, obj: Any) -> None:
        if obj is None:
            return


def box(
    obj: T,
) -> (
    T | BoxedInt | BoxedFloat | BoxedStr | BoxedNDArray | BoxedDatetime | BoxedTimedelta
):
    if type(obj) == int:
        return BoxedInt(obj)
    elif type(obj) == float:
        return BoxedFloat(obj)
    elif type(obj) == str:
        return BoxedStr(obj)
    elif type(obj) == np.ndarray:
        return BoxedNDArray(obj)
    elif type(obj) == datetime.datetime:
        return BoxedDatetime.fromtimestamp(obj.timestamp(), tz=datetime.timezone.utc)
    elif type(obj) == datetime.timedelta:
        return BoxedTimedelta(seconds=obj.total_seconds())
    return obj


def unbox(
    obj: T,
) -> T | int | float | str | np.ndarray | datetime.datetime | datetime.timedelta:
    if type(obj) == BoxedInt:
        return int(obj)
    elif type(obj) == BoxedFloat:
        return float(obj)
    elif type(obj) == BoxedStr:
        return str(obj)
    elif type(obj) == BoxedNDArray:
        return np.array(obj)
    elif type(obj) == BoxedDatetime:
        return datetime.datetime.fromtimestamp(obj.timestamp())
    elif type(obj) == BoxedTimedelta:
        return datetime.timedelta(seconds=obj.total_seconds())
    return obj
