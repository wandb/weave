import dataclasses
import typing
import numpy as np
import json
import pytest
import re

import wandb

from ..weavejs_fixes import recursively_unwrap_unions

from .. import api as weave
from ..ops_arrow import list_ as arrow
from .. import weave_types as types
from .. import storage
from .. import artifact_wandb
from .. import artifact_mem
from .. import mappers_python
from ..weave_internal import make_const_node


@weave.type()
class SomeObj:
    some_int: int
    some_str: str


@dataclasses.dataclass
class SomeCustomObj:
    obj: typing.Any


class SomeCustomObjType(types.Type):
    name = "test_storage_somecustomobj"
    instance_classes = SomeCustomObj
    instance_class = SomeCustomObj

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.json") as f:
            json.dump(obj.obj, f)

    @classmethod
    def load_instance(cls, artifact, name, extra=None):
        with artifact.open(f"{name}.json") as f:
            return SomeCustomObj(json.load(f))


def test_dict():
    obj = {"x": 14}
    obj_id = storage.save(obj, "my-dict")
    obj2 = storage.get(obj_id)
    assert obj == obj2


def test_nested_dict():
    obj = {"a": 1, "b": {"c": 2}}
    obj_id = storage.save(obj, "my-dict")
    obj2 = storage.get(obj_id)
    assert obj == obj2


def test_doubly_nested_dict():
    np_array = np.array([[4, 5], [6, 7]])
    obj = {"a": np_array, "b": {"c": np_array, "d": 3}}
    obj_id = storage.save(obj, "my-dict")
    obj2 = storage.get(obj_id)
    assert obj.keys() == obj2.keys()
    assert np.array_equal(obj["a"], obj2["a"])
    assert np.array_equal(obj["b"]["c"], obj2["b"]["c"])
    assert obj["b"]["d"] == obj2["b"]["d"]


def test_list_with_arrays():
    obj = [{"a": np.array([4, 5]), "b": "b0"}, {"a": np.array([9, 10]), "b": "b1"}]
    obj_id = storage.save(obj, "my-list-with-arrays")
    obj2 = storage.get(obj_id)
    assert np.array_equal(obj[0]["a"], obj2[0]["a"])
    assert np.array_equal(obj[1]["a"], obj2[1]["a"])
    assert obj[0]["b"] == obj[0]["b"]
    assert obj[1]["b"] == obj[1]["b"]


def test_numpy():
    np_array = np.array([[4, 5], [6, 7]])
    obj_id = storage.save(np_array, "my-arr")
    np_array2 = storage.get(obj_id)
    assert np.array_equal(np_array, np_array2)


def test_custom_obj():
    obj = SomeCustomObj({"a": 5})
    obj_id = storage.save(obj, "my-obj")
    obj2 = storage.get(obj_id)
    assert obj.obj == obj2.obj


@pytest.mark.skip(reason="wb table doesnt work right now")
def test_wandb_table():
    obj = SomeCustomObj({"a": 5})
    obj_id = storage.save(obj, "my-obj")
    obj2 = storage.get(obj_id)
    assert obj.obj == obj2.obj
    table = wandb.Table(["x", "y"])
    table.add_data(1, 2)
    table_id = storage.save(table, "my-table")
    table2 = storage.get(table_id)
    assert table._eq_debug(table2)


def test_cross_obj_ref():
    d1 = {"a": 5, "b": SomeCustomObj(14)}
    d1_id = storage.save(d1, "my-d1")
    d2 = storage.get(d1_id)
    d3 = {"f": 5, "c": d2["b"]}
    d3_id = storage.save(d3, "my-d3")
    d4 = storage.get(d3_id)
    assert d4.keys() == d3.keys()
    assert d3["f"] == d4["f"]
    assert d3["c"].obj == d4["c"].obj


def test_cross_obj_outer_ref():
    d1 = {"a": 5, "b": SomeCustomObj(14)}
    d1_id = storage.save(d1, "my-d1")
    d2 = storage.get(d1_id)
    d3 = {"f": 5, "c": d2}
    d3_id = storage.save(d3, "my-d3")
    d4 = storage.get(str(d3_id))
    assert d4.keys() == d3.keys()
    assert d3["f"] == d4["f"]
    assert d3["c"]["a"] == d4["c"]["a"]
    assert d3["c"]["b"].obj == d4["c"]["b"].obj


def test_ref_to_item_in_list():
    l = [{"a": 5, "b": 6}]
    l_node = weave.save(l, "my-l")
    l_node = l_node[0]["a"]

    dict_with_ref = {"c": l_node}
    d_node = weave.save(dict_with_ref, "my-dict_with_ref")

    assert weave.use(d_node["c"] == 5) == True


def test_list_of_ref_to_item_in_list():
    l = [{"a": 5, "b": 6}, {"a": 7, "b": 9}]
    l_node = weave.save(l, "my-l")

    list_dict_with_ref = [{"c": l_node[0]["a"]}, {"c": l_node[1]["a"]}]
    d_node = weave.save(list_dict_with_ref, "my-dict_with_ref")

    assert weave.use(d_node[0]["c"] == 5) == True
    assert weave.use(d_node[1]["c"] == 7) == True


def test_ref_type(test_artifact_dir):
    obj = {"x": 14}
    ref = storage.save(obj, "my-dict")
    python_ref = storage.to_python(ref)
    assert python_ref == {
        "_type": {
            "_base_type": {"type": "Ref"},
            "type": "LocalArtifactRef",
            "objectType": {"type": "typedDict", "propertyTypes": {"x": "int"}},
        },
        "_val": f"local-artifact:///my-dict:10e1804d2dd19195ac2d236f357b9288/obj",
    }
    ref2 = storage.from_python(python_ref)
    obj2 = storage.deref(ref2)
    assert obj == obj2


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


def test_list_obj():
    list_obj = [SomeObj(1, "a"), SomeObj(2, "b")]
    ref = storage.save(list_obj, "my-listobj")
    list_obj2 = storage.get(ref)
    assert list_obj[0].some_int == list_obj2[0].some_int
    assert list_obj[0].some_str == list_obj2[0].some_str
    assert list_obj[1].some_int == list_obj2[1].some_int
    assert list_obj[1].some_str == list_obj2[1].some_str


def test_cross_artifact_ref():
    owner = {"a": 1, "b": {"c": SomeCustomObj(2)}}
    node = weave.save(owner, "owner-obj")
    assert weave.use(node["b"]) == {"c": SomeCustomObj(2)}
    # TODO: assert that ref is to original object


@weave.type()
class _TestObjType:
    pass


def test_ref_to_node():
    d = weave.save({"a": _TestObjType()})
    node = d["a"]
    # Node a Node with weave type ObjectType
    # We want to make sure dispatch doesn't convert this access to ._ref into
    # a getattr op call (prevented by ref=None on FallbackNodeTypeDispatcherMixin)
    # ref should be None here
    assert node._ref == None


@pytest.mark.parametrize(
    "obj, wb_type, expected",
    [
        ([], None, {"_type": {"type": "list", "objectType": "unknown"}, "_val": []}),
        (
            [{"a": []}, {"a": [1]}],
            None,
            {
                "_type": {
                    "type": "list",
                    "objectType": {
                        "type": "typedDict",
                        "propertyTypes": {"a": {"type": "list", "objectType": "int"}},
                    },
                },
                "_val": [{"a": []}, {"a": [1]}],
            },
        ),
        (
            [{"a": []}, {"a": [1]}, {"a": [None]}],
            None,
            {
                "_type": {
                    "type": "list",
                    "objectType": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "list",
                                "objectType": {
                                    "type": "union",
                                    "members": ["int", "none"],
                                },
                            }
                        },
                    },
                },
                "_val": [{"a": []}, {"a": [1]}, {"a": [None]}],
            },
        ),
    ],
)
def test_to_python_object(obj, wb_type, expected):
    assert recursively_unwrap_unions(storage.to_python(obj, wb_type)) == expected


class MockStats:
    call_count = 0


@pytest.fixture
def mock_get_wandb_read_artifact_uri():
    orig = artifact_wandb.get_wandb_read_artifact_uri

    stats = MockStats()

    def _mock_get_wandb_read_artifact_uri(path: str):
        stats.call_count += 1
        return artifact_wandb.WeaveWBArtifactURI(
            "my-uri", "a_specific_version", "entity", "project", None, "path"
        )

    artifact_wandb.get_wandb_read_artifact_uri = _mock_get_wandb_read_artifact_uri
    yield stats
    artifact_wandb.get_wandb_read_artifact_uri = orig


def test_to_conversion_uri_resolution(
    mock_get_wandb_read_artifact_uri: MockStats,
):
    def make_art():
        return artifact_wandb.WandbArtifact(
            "my-art",
            "my-type",
            artifact_wandb.WeaveWBArtifactURI(
                "my-uri", "latest", "entity", "project", None, "path"
            ),
        )

    wb_type = types.TypeRegistry.type_of(make_art())

    # Construct the mapper manually. Default should be to resolve
    mapper = mappers_python.map_to_python(wb_type, artifact_mem.MemArtifact())
    res = mapper.apply(make_art())
    assert mock_get_wandb_read_artifact_uri.call_count == 1
    assert res == "wandb-artifact:///entity/project/my-uri:a_specific_version"

    # to_python uses the resolve behavior
    res = storage.to_python(make_art())
    assert mock_get_wandb_read_artifact_uri.call_count == 2
    assert res == {
        "_type": {
            "_base_type": {"type": "FilesystemArtifact"},
            "type": "WandbArtifact",
        },
        "_val": "wandb-artifact:///entity/project/my-uri:a_specific_version",
    }

    # Tell the mapper not to resolve
    mapper = mappers_python.map_to_python(
        wb_type, artifact_mem.MemArtifact(), mapper_options={"use_stable_refs": False}
    )
    assert mock_get_wandb_read_artifact_uri.call_count == 2
    res = mapper.apply(make_art())
    assert res == "wandb-artifact:///entity/project/my-uri:latest"

    # to_weavejs doesn't resolve
    assert mock_get_wandb_read_artifact_uri.call_count == 2
    res = storage.to_weavejs(make_art())
    assert res == "wandb-artifact:///entity/project/my-uri:latest"
