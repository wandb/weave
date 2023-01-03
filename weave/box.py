import typing
import numpy as np

# Watch out, can't do "is None" on this!
# TODO: fix?
class BoxedNone:
    def __init__(self, val):
        self.val = val

    def __bool__(self):
        return self.val

    def __eq__(self, other):
        return self.val == other


class BoxedBool:
    def __init__(self, val):
        self.val = val

    def __bool__(self):
        return self.val

    def __eq__(self, other):
        return self.val == other


class BoxedInt(int):
    pass


class BoxedFloat(float):
    pass


class BoxedStr(str):
    pass


class BoxedDict(dict):
    pass


class BoxedList(list):
    pass


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
    elif obj is None:
        return BoxedNone(obj)
    return obj


def unbox(
    obj: T,
) -> typing.Union[T, int, float, str, bool, dict, list, np.ndarray, None]:

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
    elif type(obj) == BoxedNone:
        return None
    return obj


def is_boxed(obj: typing.Any) -> bool:
    return id(obj) == id(box(obj))
