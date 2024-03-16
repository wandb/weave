import typing
import random
import datetime
import numpy as np

from . import context_state
from . import ref_util


def make_id() -> int:
    return random.randint(-(2**63), 2**63 - 1)


class HasBoxedRepr:
    val: typing.Any

    def __repr__(self):
        return f"<{self.__class__.__name__} ({self.val})>"


# Watch out, can't do "is None" on this!
# TODO: fix?
class BoxedNone(HasBoxedRepr):
    _id: typing.Optional[int] = None

    def __init__(self, val):
        self.val = val

    def __bool__(self):
        return bool(self.val)

    def __eq__(self, other):
        return self.val == other


def is_none(val):
    return val is None or isinstance(val, BoxedNone)


class BoxedBool(HasBoxedRepr):
    _id: typing.Optional[int] = None

    def __init__(self, val):
        self.val = val

    def __bool__(self):
        return self.val

    def __hash__(self):
        return hash(self.val)

    def __eq__(self, other):
        return self.val == other


class BoxedInt(int):
    _id: typing.Optional[int] = None


class BoxedFloat(float):
    _id: typing.Optional[int] = None


class BoxedStr(str):
    _id: typing.Optional[int] = None


class BoxedDict(dict):
    _id: typing.Optional[int] = None

    def _lookup_path(self, path: typing.List[str]):
        assert len(path) > 1
        edge_type = path[0]
        edge_path = path[1]
        assert edge_type == ref_util.DICT_KEY_EDGE_TYPE

        res = self[edge_path]
        remaining_path = path[2:]
        if remaining_path:
            return res._lookup_path(remaining_path)
        return res

    def __getitem__(self, __key: typing.Any) -> typing.Any:
        val = super().__getitem__(__key)
        return ref_util.val_with_relative_ref(
            self, val, [ref_util.DICT_KEY_EDGE_TYPE, str(__key)]
        )


class BoxedList(list):
    def _lookup_path(self, path: typing.List[str]):
        assert len(path) > 1
        edge_type = path[0]
        edge_path = path[1]
        assert edge_type == ref_util.LIST_INDEX_EDGE_TYPE

        res = self[int(edge_path)]
        remaining_path = path[2:]
        if remaining_path:
            return res._lookup_path(remaining_path)
        return res

    def __iter__(self):
        # Needed to make list-comprehensions work with our custom __getitem__,
        # otherwise, list.__iter__ uses the parent class __getitem__.
        for i in range(len(self)):
            yield self[i]

    def __getitem__(self, __index: typing.Any) -> typing.Any:
        val = super().__getitem__(__index)
        return ref_util.val_with_relative_ref(
            self, val, [ref_util.LIST_INDEX_EDGE_TYPE, str(__index)]
        )


class BoxedDatetime(datetime.datetime):
    def __eq__(self, other):
        return (
            isinstance(other, datetime.datetime)
            and self.timestamp() == other.timestamp()
        )


class BoxedTimedelta(datetime.timedelta):
    def __eq__(self, other):
        return (
            isinstance(other, datetime.timedelta)
            and self.total_seconds() == other.total_seconds()
        )


def cannot_have_weakref(obj: typing.Any):
    return isinstance(obj, (BoxedInt, BoxedFloat, BoxedStr, BoxedBool, BoxedNone))


# See https://numpy.org/doc/stable/user/basics.subclassing.html
class BoxedNDArray(np.ndarray):
    def __new__(cls, input_array):
        obj = np.asarray(input_array).view(cls)
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return


T = typing.TypeVar("T")


def box(
    obj: T,
) -> typing.Union[
    T,
    BoxedInt,
    BoxedFloat,
    BoxedStr,
    BoxedBool,
    BoxedDict,
    BoxedList,
    BoxedNDArray,
    BoxedNone,
    BoxedDatetime,
    BoxedTimedelta,
]:
    if type(obj) == int:
        return BoxedInt(obj)
    elif type(obj) == float:
        return BoxedFloat(obj)
    elif type(obj) == str:
        return BoxedStr(obj)
    elif type(obj) == bool:
        return BoxedBool(obj)
    elif type(obj) == dict:
        return BoxedDict(obj)
    elif type(obj) == list:
        return BoxedList(obj)
    elif type(obj) == np.ndarray:
        return BoxedNDArray(obj)
    elif type(obj) == datetime.datetime:
        return BoxedDatetime.fromtimestamp(obj.timestamp(), tz=datetime.timezone.utc)
    elif type(obj) == datetime.timedelta:
        return BoxedTimedelta(seconds=obj.total_seconds())
    elif obj is None:
        return BoxedNone(obj)
    return obj


def unbox(
    obj: T,
) -> typing.Union[
    T,
    int,
    float,
    str,
    bool,
    dict,
    list,
    np.ndarray,
    datetime.datetime,
    datetime.timedelta,
    None,
]:
    if type(obj) == BoxedInt:
        return int(obj)
    elif type(obj) == BoxedFloat:
        return float(obj)
    elif type(obj) == BoxedStr:
        return str(obj)
    elif type(obj) == BoxedBool:
        return bool(obj)
    elif type(obj) == BoxedDict:
        return dict(obj)
    elif type(obj) == BoxedList:
        return list(obj)
    elif type(obj) == BoxedNDArray:
        return np.array(obj)
    elif type(obj) == BoxedDatetime:
        return datetime.datetime.fromtimestamp(obj.timestamp())
    elif type(obj) == BoxedTimedelta:
        return datetime.timedelta(seconds=obj.total_seconds())
    elif type(obj) == BoxedNone:
        return None
    return obj


def is_boxed(obj: typing.Any) -> bool:
    return id(obj) == id(box(obj))
