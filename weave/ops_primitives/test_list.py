import random

from .. import api as weave
from .. import weave_types as types
from . import list_
from . import dict


def test_unnest():
    data = [{"a": [1, 2], "b": "x", "c": [5, 6]}, {"a": [3, 4], "b": "j", "c": [9, 10]}]
    unnested = weave.use(list_.unnest(data))
    # convert to list so pytest prints nice diffs if there is a mismatch
    assert list(unnested) == [
        {"a": 1, "b": "x", "c": 5},
        {"a": 2, "b": "x", "c": 6},
        {"a": 3, "b": "j", "c": 9},
        {"a": 4, "b": "j", "c": 10},
    ]


def test_op_list():
    node = list_.make_list(a=1, b=2, c=3)
    assert node.type == types.List(types.Int())


def test_typeof_groupresult():
    assert types.TypeRegistry.type_of(
        list_.GroupResult([1, 2, 3], "a")
    ) == list_.GroupResultType(types.Int(), types.String())


def test_sequence1():
    rotate_choices = list(range(5))
    shear_choices = list(range(5))
    l = []
    for i in range(200):
        l.append(
            {
                "rotate": random.choice(rotate_choices),
                "shear": random.choice(shear_choices),
                "y": random.choice(["a", "b", "c"]),
            }
        )
    saved = weave.save(l)
    groupby1_fn = weave.define_fn(
        {"row": types.TypeRegistry.type_of(l).object_type},
        lambda row: dict.dict_(
            **{
                "rotate": row["rotate"],
                "rotate": row["rotate"],
            }
        ),
    )
    res = list_.WeaveJSListInterface.groupby(saved, groupby1_fn)
    print("RESESDFSDf", weave.use(res))
    assert 1 == 2
