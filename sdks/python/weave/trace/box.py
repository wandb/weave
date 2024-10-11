"""Alternate boxing implementation for Weave Trace.

This copies many things from query service's box.py, but it notably
does not box None and bool which simplify checks for trace users."""

from __future__ import annotations

import datetime
from typing import Any, TypeVar

import numpy as np

from weave.trace.refs import Ref

T = TypeVar("T")


class BoxedInt(int):
    _id: int | None = None
    ref: Ref | None = None


class BoxedFloat(float):
    _id: int | None = None
    ref: Ref | None = None


class BoxedStr(str):
    _id: int | None = None
    ref: Ref | None = None


class BoxedDatetime(datetime.datetime):
    ref: Ref | None = None

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, datetime.datetime)
            and self.timestamp() == other.timestamp()
        )


class BoxedTimedelta(datetime.timedelta):
    ref: Ref | None = None

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, datetime.timedelta)
            and self.total_seconds() == other.total_seconds()
        )


# See https://numpy.org/doc/stable/user/basics.subclassing.html
class BoxedNDArray(np.ndarray):
    ref: Ref | None = None

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
