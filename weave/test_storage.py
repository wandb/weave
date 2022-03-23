import numpy as np
import json
import pytest

import wandb

from . import api as weave
from . import weave_types as types
from . import storage
from .weave_internal import make_const_node


class SomeObj(object):
    def __init__(self, obj):
        self.obj = obj


class SomeObjType(types.Type):
    name = "test-storage-some-obj"
    instance_classes = SomeObj
    instance_class = SomeObj

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.json") as f:
            json.dump(obj.obj, f)
        return self

    @classmethod
    def load_instance(cls, artifact, name):
        with artifact.open(f"{name}.json") as f:
            return SomeObj(json.load(f))


# STORAGE_TYPES = ['local_file', 'hdf5']
STORAGE_TYPES = ["local_file"]
# STORAGE_TYPES = ['hdf5']


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_dict(storage_type):
    with storage.WeaveContext(storage_type):
        obj = {"x": 14}
        obj_id = storage.save(obj, "my-dict")
        obj2 = storage.get(obj_id)
        assert obj == obj2


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_nested_dict(storage_type):
    with storage.WeaveContext(storage_type):
        obj = {"a": 1, "b": {"c": 2}}
        obj_id = storage.save(obj, "my-dict")
        obj2 = storage.get(obj_id)
        assert obj == obj2


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_doubly_nested_dict(storage_type):
    with storage.WeaveContext(storage_type):
        np_array = np.array([[4, 5], [6, 7]])
        obj = {"a": np_array, "b": {"c": np_array, "d": 3}}
        obj_id = storage.save(obj, "my-dict")
        obj2 = storage.get(obj_id)
        assert obj.keys() == obj2.keys()
        assert np.array_equal(obj["a"], obj2["a"])
        assert np.array_equal(obj["b"]["c"], obj2["b"]["c"])
        assert obj["b"]["d"] == obj2["b"]["d"]


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_numpy(storage_type):
    with storage.WeaveContext(storage_type):
        np_array = np.array([[4, 5], [6, 7]])
        obj_id = storage.save(np_array, "my-arr")
        np_array2 = storage.get(obj_id)
        assert np.array_equal(np_array, np_array2)


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_custom_obj(storage_type):
    with storage.WeaveContext(storage_type):
        obj = SomeObj({"a": 5})
        obj_id = storage.save(obj, "my-obj")
        obj2 = storage.get(obj_id)
        assert obj.obj == obj2.obj


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
@pytest.mark.skip(reason="wb table doesnt work right now")
def test_wandb_table(storage_type):
    with storage.WeaveContext(storage_type):
        obj = SomeObj({"a": 5})
        obj_id = storage.save(obj, "my-obj")
        obj2 = storage.get(obj_id)
        assert obj.obj == obj2.obj
        table = wandb.Table(["x", "y"])
        table.add_data(1, 2)
        table_id = storage.save(table, "my-table")
        table2 = storage.get(table_id)
        assert table._eq_debug(table2)


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
@pytest.mark.skip(reason="cross obj refs dont work right now")
def test_cross_obj_ref(storage_type):
    with storage.WeaveContext(storage_type):
        d1 = {"a": 5, "b": SomeObj(14)}
        d1_id = storage.save(d1, "my-d1")
        d2 = storage.get(d1_id)
        d3 = {"f": 5, "c": d2["b"]}
        d3_id = storage.save(d3, "my-d3")
        d4 = storage.get(d3_id)
        assert d4.keys() == d3.keys()
        assert d3["f"] == d4["f"]
        assert d3["c"].obj == d4["c"].obj


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
@pytest.mark.skip(reason="cross obj refs dont work right now")
def test_cross_obj_outer_ref(storage_type):
    with storage.WeaveContext(storage_type):
        d1 = {"a": 5, "b": SomeObj(14)}
        d1_id = storage.save(d1, "my-d1")
        d2 = storage.get(d1_id)
        d3 = {"f": 5, "c": d2}
        d3_id = storage.save(d3, "my-d3")
        d4 = storage.get(d3_id)
        assert d4.keys() == d3.keys()
        assert d3["f"] == d4["f"]
        assert d3["c"]["a"] == d4["c"]["a"]
        assert d3["c"]["b"].obj == d4["c"]["b"].obj


@pytest.mark.parametrize("storage_type", STORAGE_TYPES)
def test_ref_type(storage_type):
    with storage.WeaveContext(storage_type):
        obj = {"x": 14}
        ref = storage.save(obj, "my-dict")
        python_ref = storage.to_python(ref)
        assert python_ref == {
            "_type": {
                "objectType": {"propertyTypes": {"x": "int"}, "type": "typedDict"},
                "type": "ref-type",
            },
            "_val": "my-dict/6036cbf3a05809f1a3f174a1485b1770",
        }
        ref2 = storage.from_python(python_ref)
        obj2 = storage.deref(ref2)
        assert obj == obj2


def test_trace():
    nine = make_const_node(storage.types.Number(), 9)
    res = weave.use((nine + 3) * 4)
    assert res == 48
    mult_run = storage.get_obj_creator(storage._get_ref(res))
    assert mult_run._op_name == "number-mult"
    assert (
        str(mult_run._inputs["lhs"])
        == "run-number-add-0160f0cff26fd543021cf0b6c12e4fe6-output/6298d0a1e1f13057a03865a1c4512981"
    )
    assert mult_run._inputs["rhs"] == 4
    add_run = storage.get_obj_creator(mult_run._inputs["lhs"])
    assert add_run._op_name == "number-add"
    assert add_run._inputs == {"lhs": 9, "rhs": 3}


def test_boxing():
    ref = storage.save(5)
    val = storage.get(str(ref))
    assert val == 5
    assert val._ref is not None


def test_saveload_type():
    t = types.TypedDict({"a": types.Int(), "b": types.String()})
    t_type = types.TypeRegistry.type_of(t)
    ref = storage.save(t)
    t2 = ref.get()
    assert t == t2
