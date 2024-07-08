"""Alternate boxing implementation for Weave Trace.

Currently it just replaces BoxedNone with None"""

from __future__ import annotations

import datetime

import numpy as np

from weave.legacy.box import (
    BoxedBool,
    BoxedDatetime,
    BoxedDict,
    BoxedFloat,
    BoxedInt,
    BoxedList,
    BoxedNDArray,
    BoxedNone,
    BoxedStr,
    BoxedTimedelta,
    T,
)
from weave.legacy.box import box as box_legacy
from weave.legacy.box import unbox as unbox_legacy


def box(
    obj: T,
) -> (
    T
    | BoxedInt
    | BoxedFloat
    | BoxedStr
    | BoxedBool
    | BoxedDict
    | BoxedList
    | BoxedNDArray
    | BoxedDatetime
    | BoxedTimedelta
):
    res = box_legacy(obj)
    if isinstance(res, BoxedNone):
        return None


def unbox(
    obj: T,
) -> (
    T
    | int
    | float
    | str
    | bool
    | dict
    | list
    | np.ndarray
    | datetime.datetime
    | datetime.timedelta
    | None
):
    res = unbox_legacy(obj)
    return res
