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
    # TODO: we shouldn't have methods in these!
    # But these are necessary to deal with the way the tables stuff
    # works right now.
    def count(self):
        return len(self)

    def index(self, index):
        if index >= len(self):
            return None
        return self.__getitem__(index)

    # Augh, we shouldn't need this here. Will be fixed when I finally fix the
    # proliferation of tables and lists.
    # TODO: Fix.
    def map(self, mapFn):
        from . import weave_internal
        from . import graph
        from . import weave_types as types
        from .ops_primitives import table

        calls = []
        for i, row in enumerate(self):
            calls.append(
                weave_internal.call_fn(
                    mapFn,
                    {
                        "row": graph.ConstNode(types.Any(), row),
                        "index": graph.ConstNode(types.Number(), i),
                    },
                )
            )
        result = weave_internal.use_internal(calls)
        return table.ListTable(result)


# See https://numpy.org/doc/stable/user/basics.subclassing.html
class BoxedNDArray(np.ndarray):
    def __new__(cls, input_array):
        obj = np.asarray(input_array).view(cls)
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return


def box(obj):
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
