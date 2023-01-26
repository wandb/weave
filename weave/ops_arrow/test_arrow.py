import datetime
import pytest
import itertools
import hashlib
import pyarrow as pa
import string
from PIL import Image
import typing

from weave.tests import list_arrow_test_helpers as lath

from ..tests import weavejs_ops


from .. import box
from .. import errors
from .. import storage
from ..ops_primitives import Number
from .. import api as weave
from .. import ops
from .. import artifact_util
from .. import weave_types as types
from .. import weave_internal
from .. import context_state
from .. import graph
from ..ops_primitives import dict_, list_

from ..language_features.tagging import tag_store, tagged_value_type, make_tag_getter_op

from . import arrow as arrow_type
from . import list_ as arrow
from . import dict as arrow_dict


_loading_builtins_token = context_state.set_loading_built_ins()
# T in `conftest::pre_post_each_test` we set a custom artifact directory for each test for isolation
# Puting this import in the context allows the test execution to access these ops
@weave.type()
class Point2:
    x: float
    y: float

    @weave.op()
    def get_x(self) -> float:
        return self.x


context_state.clear_loading_built_ins(_loading_builtins_token)


def simple_hash(n, b):
    return int.from_bytes(hashlib.sha256(str(n).encode()).digest(), "little") % b


def create_arrow_data(n_rows, n_extra_cols=0, images=False):
    inner_count = int(n_rows / 25)
    base_im = Image.linear_gradient("L")
    x_choices = string.ascii_lowercase
    extra_cols = [chr(ord("a") + i) for i in range(n_extra_cols)]
    ims = []
    for i, (rotate, shear, _) in enumerate(
        itertools.product(range(5), range(5), range(inner_count))
    ):
        im = {
            "rotate": rotate,
            "shear": shear,
            "x": x_choices[simple_hash(i**13, 3)],
            "y": simple_hash(i, 10),
        }
        if images:
            im["image"] = base_im.rotate(rotate * 4).transform(
                (256, 256), Image.AFFINE, (1, shear / 10, 0, 0, 1, 0), Image.BICUBIC
            )
        for j, col in enumerate(extra_cols):
            im[col] = x_choices[simple_hash(i * 13**j, 11)]
        ims.append(im)
    arr = arrow.to_arrow(ims)
    return storage.save(arr)


def test_groupby_index_count():
    ref = create_arrow_data(1000)
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"]))[1]
        .count()
    )
    assert weave.use(node) == 40


@pytest.mark.parametrize(
    "sort_lambda, sort_dirs, exp_rotation_avg",
    [
        (lambda row: list_.make_list(a=row.groupkey().pick("rotate")), ["asc"], 0),
        (lambda row: list_.make_list(a=row.groupkey().pick("rotate")), ["desc"], 4),
        # This does not work yet since vectorized groupby does not know how to pick
        # (or many ops for that matter. The only sort operations that work right now
        # are those on the key itself. Luckily, that is the only thing you can construct
        # in the UI anyway)
        # (lambda row: list_.make_list(a=row.pick("rotate").avg()), ["desc"], 4),
        (
            lambda row: list_.make_list(
                a=row.groupkey().pick("shear"), b=row.groupkey().pick("rotate")
            ),
            ["asc", "desc"],
            4,
        ),
    ],
)
def test_groupby_sort(sort_lambda, sort_dirs, exp_rotation_avg):
    ref = create_arrow_data(1000)
    grouped_node = weave.get(ref).groupby(
        lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"])
    )
    sorted_node = grouped_node.sort(sort_lambda, sort_dirs)
    first_group = sorted_node[0]
    first_group_rotations = first_group.pick("rotate")
    first_group_rotation_avg = first_group_rotations.avg()
    assert weave.use(first_group_rotation_avg) == exp_rotation_avg


def test_js_groupby_sort():
    list_data = [{"a": 1, "b": 1}, {"a": 1, "b": 2}, {"a": 2, "b": 1}, {"a": 2, "b": 2}]
    list_node = list_.make_list(**{f"{n}": v for n, v in enumerate(list_data)})
    arrow_node = weave.save(arrow.to_arrow(list_data))
    node = weavejs_ops.groupby(
        list_node,
        weave.define_fn(
            {"row": list_node.type.object_type},
            lambda row: ops.dict_(
                a=graph.OutputNode(
                    types.String(),
                    "pick",
                    {"obj": row, "key": graph.ConstNode(types.String(), "a")},
                )
            ),
        ),
    )
    # Critical replacement of the input to use arrow!
    node.from_op.inputs["arr"] = arrow_node
    node = weavejs_ops.sort(
        node,
        weave.define_fn(
            {"row": node.type.object_type},
            lambda row: ops.make_list(
                a=graph.OutputNode(
                    types.String(),
                    "pick",
                    {
                        "obj": graph.OutputNode(
                            types.TypedDict({"a": types.String()}),
                            "group-groupkey",
                            {"obj": row},
                        ),
                        "key": graph.ConstNode(types.String(), "a"),
                    },
                )
            ),
        ),
        ops.make_list(a="asc"),
    )
    assert weave.use(node) != None


def test_group_key():
    data = weave.save(arrow.to_arrow([1, 2, 3]))
    res = data.groupby(lambda row: row + 1)[0].groupkey()
    assert weave.use(res) == 2


def test_map_scalar_map():
    ref = create_arrow_data(100)

    node = weave.get(ref).map(lambda row: row["y"] + 1).map(lambda row: row + 9)
    assert weave.use(node[0]) == 15
    assert weave.use(node[4]) == 17


def test_groupby_mapped_groupby():
    ref = create_arrow_data(1000)
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"]))
        .map(lambda row: row.groupby(lambda row: row["y"]))
        .dropna()
        .count()
    )
    assert weave.use(node) == 25


def test_table_string_histogram():
    ref = create_arrow_data(1000)
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"]))[0]
        .pick("x")
        .groupby(lambda row: ops.dict_(row=row))
        .map(lambda row: row.groupkey().merge(ops.dict_(count=row.count())))
        .count()
    )
    assert weave.use(node) == 3


def test_custom_types():
    data_node = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    assert weave.use(data_node[0]["im"].width_()) == 256

    assert weave.use(data_node.map(lambda row: row["im"].width_())).to_pylist() == [
        256,
        256,
    ]


def test_custom_types_tagged():

    im1 = tag_store.add_tags(Image.linear_gradient("L").rotate(0), {"a": 1})
    im2 = tag_store.add_tags(Image.linear_gradient("L").rotate(4), {"a": 2})

    data_node = weave.save(arrow.to_arrow([{"a": 5, "im": im1}, {"a": 6, "im": im2}]))
    width_node = data_node[0]["im"].width_()
    assert weave.use(width_node) == 256

    assert width_node.type == tagged_value_type.TaggedValueType(
        types.TypedDict({"a": types.Int()}), types.Int()
    )

    mapped_width_node = data_node.map(lambda row: row["im"].width_())
    assert weave.use(mapped_width_node).to_pylist() == [
        256,
        256,
    ]

    assert mapped_width_node.type == arrow.ArrowWeaveListType(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"a": types.Int()}), types.Int()
        )
    )


def test_custom_saveload():
    data = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    ref = storage.save(data)
    data2 = storage.get(str(ref))
    # print("data2", data2._artifact)
    assert weave.use(data2[0]["im"].width_()) == 256


def test_custom_in_list_saveload():
    data = arrow.to_arrow(
        [
            {"a": 5, "im": [Image.linear_gradient("L").rotate(0)]},
            {"a": 6, "im": [Image.linear_gradient("L").rotate(4)]},
        ]
    )
    ref = storage.save(data)
    data2 = storage.get(str(ref))
    # print("data2", data2._artifact)
    assert weave.use(data2[0]["im"].width_()) == [256]


def test_custom_tagged_groupby1():

    im1 = tag_store.add_tags(Image.linear_gradient("L").rotate(0), {"a": 1})
    im2 = tag_store.add_tags(Image.linear_gradient("L").rotate(4), {"a": 2})
    raw_data = box.box([{"a": 5, "im": im1}, {"a": 6, "im": im2}])
    data_node = weave.save(arrow.to_arrow(raw_data))
    grouped_node = data_node.groupby(lambda row: ops.dict_(a=row["a"]))
    group1_node = grouped_node[0]

    assert grouped_node.type == arrow.awl_group_by_result_type(
        types.TypedDict(
            {
                "a": types.Int(),
                "im": tagged_value_type.TaggedValueType(
                    types.TypedDict({"a": types.Int()}),
                    weave.type_of(Image.linear_gradient("L").rotate(4)),
                ),
            }
        ),
        types.TypedDict({"a": types.Int()}),
    )

    assert group1_node.type == arrow.awl_group_by_result_object_type(
        types.TypedDict(
            {
                "a": types.Int(),
                "im": tagged_value_type.TaggedValueType(
                    types.TypedDict({"a": types.Int()}),
                    weave.type_of(Image.linear_gradient("L").rotate(4)),
                ),
            }
        ),
        types.TypedDict({"a": types.Int()}),
    )

    assert (
        weave.use(
            data_node.groupby(lambda row: ops.dict_(a=row["a"]))[0]
            .pick("im")
            .offset(0)[0]
            .width_()
        )
        == 256
    )


def test_custom_tagged_groupby2():
    im1 = tag_store.add_tags(Image.linear_gradient("L").rotate(0), {"a": 1})
    im2 = tag_store.add_tags(Image.linear_gradient("L").rotate(4), {"a": 2})
    raw_data = box.box([{"a": 5, "im": im1}, {"a": 6, "im": im2}])

    tag_store.add_tags(raw_data, {"list_tag": 3})

    data_node = weave.save(arrow.to_arrow(raw_data))
    grouped_node = data_node.groupby(lambda row: ops.dict_(inner_group_key=row["a"]))
    target = tagged_value_type.TaggedValueType(
        types.TypedDict(
            {
                "list_tag": types.Int(),
            }
        ),
        arrow.awl_group_by_result_type(
            types.TypedDict(
                {
                    "a": types.Int(),
                    "im": tagged_value_type.TaggedValueType(
                        types.TypedDict({"a": types.Int()}),
                        weave.type_of(Image.linear_gradient("L").rotate(4)),
                    ),
                }
            ),
            # types.TypedDict({"a": types.Int()}),
            types.TypedDict(
                {
                    "inner_group_key": tagged_value_type.TaggedValueType(
                        types.TypedDict({"list_tag": types.Int()}), types.Int()
                    )
                }
            ),
        ),
    )
    assert grouped_node.type == target

    get_list_tag = make_tag_getter_op.make_tag_getter_op("list_tag", types.Int())
    assert weave.use(get_list_tag(grouped_node)) == 3


def test_custom_groupby_1():
    data = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )

    assert (
        weave.use(
            data.groupby(lambda row: ops.dict_(a=row["a"]))[0]
            .pick("im")
            .offset(0)[0]
            .width_()
        )
        == 256
    )


def test_custom_groupby_intermediate_save():
    data = arrow.to_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    node = data.groupby(lambda row: ops.dict_(a=row["a"]))[0]
    saved_node = weave.save(node, "test_custom_groupby_intermediate_save")
    weave.use(saved_node)
    loaded_node = ops.get(
        f"local-artifact:///test_custom_groupby_intermediate_save:latest/obj"
    )
    assert weave.use(loaded_node.pick("im").offset(0)[0].width_()) == 256


def test_map_array():
    data = arrow.to_arrow([1, 2, 3])
    assert weave.use(data.map(lambda i: i + 1)).to_pylist() == [2, 3, 4]


def test_map_typeddict():
    data = arrow.to_arrow([{"a": 1, "b": 2}, {"a": 3, "b": 5}])
    assert weave.use(data.map(lambda row: row["a"])).to_pylist() == [1, 3]


@pytest.mark.parametrize(
    "data",
    [
        # ELEMENT TYPE:
        ## 0 Depth
        ### Primitive
        [1, 2],
        ## 1 Depth
        ### list
        [[1], [2]],
        ### dict
        [{"outer_a": 1}, {"outer_a": 2}],
        ## 2 Depth
        ### dict of list
        [{"outer_a": [1]}, {"outer_a": [2]}],
        ### dict of dict
        [{"outer_a": {"inner_a": 1}}, {"outer_a": {"inner_a": 2}}],
        ### list of list
        # [[[1]], [[2]]],
        ### list of dict
        [[{"outer_a": 1}], [{"outer_a": 1}]],
        ## 3 Depth
        ### dict of list of list
        [{"outer_a": [[1]]}, {"outer_a": [[2]]}],
        ### dict of list of dict
        [{"outer_a": [{"inner_a": 1}]}, {"outer_a": [{"inner_a": 2}]}],
        ### dict of dict of list
        [{"outer_a": {"inner_a": [1]}}, {"outer_a": {"inner_a": [2]}}],
        ### dict of dict of dict
        [
            {"outer_a": {"inner_a": {"inner_inner_a": 1}}},
            {"outer_a": {"inner_a": {"inner_inner_a": 2}}},
        ],
        ### list of list of list
        [[[[1]]], [[[2]]]],
        ### list of list of dict
        [[[{"outer_a": 1}]], [[{"outer_a": 2}]]],
        ### list of dict of list
        [[{"outer_a": [1]}], [{"outer_a": [2]}]],
        ### list of dict of dict
        [[{"outer_a": {"inner_a": 1}}], [{"outer_a": {"inner_a": 2}}]],
    ],
)
def test_arrow_nested_identity(data):
    assert weave.use(weave.save(arrow.to_arrow(data))[0]) == data[0]


def test_arrow_nested_with_refs():
    # As of this writing, the first time we call `to_arrow`, the underlying
    # `save` operation does not convert relative artifact paths to URIs. This is
    # in `ArrowWeaveList::save_instance`.
    data_node = arrow.to_arrow(
        [{"outer": [{"inner": Image.linear_gradient("L").rotate(0)}]}]
    )

    raw_path = data_node._arrow_data[0]["outer"][0]["inner"].as_py()

    raw_data = weave.use(weave.save(data_node))
    img_entry_data = raw_data._arrow_data[0]["outer"][0]["inner"].as_py()

    # Next, we get a derive node from the data_node, and assert that the path is
    # converted to an artifact reference when appropriate.
    col_node = arrow_dict.pick(data_node, "outer")
    # Note: we don't need to save the `col_node` because
    # they are already converted to the node representation via dispatch
    raw_col_data = weave.use(col_node)
    img_entry_col = raw_col_data._arrow_data[0][0]["inner"].as_py()
    # For this case we want the entry to be the short-form - since the underlying artifact is the same
    assert raw_path == img_entry_col
    assert data_node._artifact == raw_col_data._artifact

    # Finally, when we have a new artifact (we can force this by saving)
    # the path is converted to an artifact reference
    raw_col_data = weave.use(weave.save(col_node, "NewArtifact"))
    img_entry_col = raw_col_data._arrow_data[0][0]["inner"].as_py()
    assert img_entry_data == img_entry_col
    assert data_node._artifact != raw_col_data._artifact


def test_map_object():
    data = arrow.to_arrow([Point2(1, 2), Point2(5, 6)])
    assert weave.use(data.map(lambda row: row.get_x())).to_pylist() == [1, 5]


@pytest.mark.skip("not working yet")
def test_map_typeddict_object():
    data = arrow.to_arrow([{"a": 0, "p": Point2(1, 2)}, {"a": 3, "p": Point2(9, 12)}])
    assert weave.use(data.map(lambda row: row["p"])).to_pylist() == []


def test_arrow_list_of_ref_to_item_in_list():
    l = [{"a": 5, "b": 6}, {"a": 7, "b": 9}]
    l_node = weave.save(l, "my-l")

    list_dict_with_ref = arrow.to_arrow([{"c": l_node[0]["a"]}, {"c": l_node[1]["a"]}])
    d_node = weave.save(list_dict_with_ref, "my-dict_with_ref")

    assert weave.use(d_node[0]["c"] == 5) == True
    assert weave.use(d_node[1]["c"] == 7) == True


def test_arrow_tag_propagation():
    list = box.box([1, 2, 3])
    awl = arrow.to_arrow(list)
    tag_store.add_tags(awl, {"mytag": "test"})

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("mytag", types.String())

    awl_node = weave.save(awl)
    element_node = awl_node[0]
    assert isinstance(element_node.type, tagged_value_type.TaggedValueType)
    tag_value = weave.use(tag_getter_op(element_node))
    assert tag_value == "test"


def test_arrow_element_tagging():
    list = [1, 2, 3]
    for i, elem in enumerate(list):
        taggable = box.box(elem)
        list[i] = tag_store.add_tags(taggable, {"mytag": f"test{elem}"})

    awl = arrow.to_arrow(list)
    tag_getter_op = make_tag_getter_op.make_tag_getter_op("mytag", types.String())

    awl_node = weave.save(awl)
    element_node = awl_node[0]
    assert isinstance(element_node.type, tagged_value_type.TaggedValueType)
    tag_value = weave.use(tag_getter_op(element_node))
    assert tag_value == "test1"


def test_nested_arrow_element_tagging():
    list = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    for i, elem in enumerate(list):
        taggable = box.box(elem["a"])
        list[i]["a"] = tag_store.add_tags(taggable, {"mytag": f"test{elem['a'] + 1}"})

    awl = arrow.to_arrow(list)
    tag_getter_op = make_tag_getter_op.make_tag_getter_op("mytag", types.String())
    awl_node = weave.save(awl)
    element_node = awl_node[0]
    assert isinstance(
        element_node.type.property_types["a"], tagged_value_type.TaggedValueType
    )
    tag_value = weave.use(tag_getter_op(element_node["a"]))
    assert tag_value == "test2"
    assert weave.use(element_node) == list[0]


def test_tagging_concat():
    awls = []
    for index in range(2):
        list = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        for i, elem in enumerate(list):
            taggable = box.box(elem["a"])
            list[i]["a"] = tag_store.add_tags(
                taggable, {"element_tag": f"test{elem['a'] + 1}"}
            )

        awl = arrow.to_arrow(list)
        tag_store.add_tags(awl, {"list_tag": f"index{index}"})
        awls.append(weave.save(awl))

    list_nodes = weave._ops.make_list(l1=awls[0], l2=awls[1])
    concatenated = arrow.concat(list_nodes)

    assert weave.use(concatenated.to_py()) == [{"a": 1, "b": 2}, {"a": 3, "b": 4}] * 2
    assert concatenated.type == arrow.ArrowWeaveListType(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"list_tag": types.String()}),
            types.TypedDict(
                {
                    "a": tagged_value_type.TaggedValueType(
                        types.TypedDict({"element_tag": types.String()}),
                        types.Int(),
                    ),
                    "b": types.Int(),
                }
            ),
        )
    )

    get_element_tag = make_tag_getter_op.make_tag_getter_op(
        "element_tag", types.String()
    )

    assert weave.use(get_element_tag(concatenated[0]["a"])) == "test2"

    # test tag merging
    assert concatenated[0]["a"].type == tagged_value_type.TaggedValueType(
        types.TypedDict({"element_tag": types.String(), "list_tag": types.String()}),
        types.Int(),
    )

    get_list_tag = make_tag_getter_op.make_tag_getter_op("list_tag", types.String())
    assert weave.use(get_list_tag(concatenated[0]["a"])) == "index0"


def test_arrow_unnest():
    data = arrow.to_arrow([{"a": [1, 2, 3], "b": "c"}, {"a": [4, 5, 6], "b": "d"}])
    assert weave.type_of(data) == arrow.ArrowWeaveListType(
        types.TypedDict({"a": types.List(types.Int()), "b": types.String()})
    )
    unnest_node = data.unnest()
    assert unnest_node.type == arrow.ArrowWeaveListType(
        types.TypedDict({"a": types.Int(), "b": types.String()})
    )
    assert weave.use(data.unnest()).to_pylist() == [
        {"a": 1, "b": "c"},
        {"a": 2, "b": "c"},
        {"a": 3, "b": "c"},
        {"a": 4, "b": "d"},
        {"a": 5, "b": "d"},
        {"a": 6, "b": "d"},
    ]


def test_arrow_nullable_concat():
    ca1 = pa.chunked_array([[1, 2], [3, 4]])
    ca2 = pa.compute.add(ca1, 1)
    awl1 = arrow.ArrowWeaveList(ca1)
    awl2 = arrow.ArrowWeaveList(ca2)
    list_of_awl = weave._ops.make_list(A=awl1, B=awl2, C=weave.save(None))
    result = list_of_awl.concat()
    assert weave.use(result)._arrow_data.to_pylist() == [1, 2, 3, 4, 2, 3, 4, 5]

    # Second pass - forcing none type to be first in member list
    list_of_awl.type = types.List(
        types.union(types.NoneType(), arrow.ArrowWeaveListType(types.Int()))
    )
    result = list_of_awl.concat()
    assert weave.use(result)._arrow_data.to_pylist() == [1, 2, 3, 4, 2, 3, 4, 5]


def test_arrow_weave_list_groupby_struct_type_table():

    table = pa.Table.from_pylist(
        [{"d": {"a": 1, "b": 2}, "c": 1}, {"d": {"a": 3, "b": 4}, "c": 2}]
    )
    awl = arrow.ArrowWeaveList(table)

    def group_func_body(row):
        return ops.dict_(**{"d": row["d"]})

    # note: access more than 1 level deep is broken, should work, fix
    # def group_func_body(row):
    #    return ops.dict_(**{"d.a": row["d"]["a"]})

    group_func = weave_internal.define_fn({"row": awl.object_type}, group_func_body)
    grouped = awl.groupby(group_func)
    assert weave.use(grouped[0]) == [{"d": {"a": 1, "b": 2}, "c": 1}]


def test_arrow_weave_list_groupby_struct_chunked_array_type():
    ref = create_arrow_data(1000)

    # chunkedarray is used when there are two levels of nesting
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"]))
        .map(lambda row: row.groupby(lambda row: row["y"]))
        .dropna()[0][0]
    )

    assert weave.use(node) == [{"rotate": 0, "shear": 0, "x": "a", "y": 5}] * 5


string_ops_test_cases = [
    ("eq-scalar", lambda x: x == "bc", [True, False, False]),
    ("ne-scalar", lambda x: x != "bc", [False, True, True]),
    ("contains-scalar", lambda x: x.__contains__("b"), [True, False, False]),
    ("in-scalar", lambda x: x.in_("bcd"), [True, True, False]),
    ("len-scalar", lambda x: x.len(), [2, 2, 2]),
    ("add-scalar", lambda x: x + "q", ["bcq", "cdq", "dfq"]),
    ("append-scalar", lambda x: x.append("qq"), ["bcqq", "cdqq", "dfqq"]),
    ("prepend-scalar", lambda x: x.prepend("qq"), ["qqbc", "qqcd", "qqdf"]),
    ("split-scalar", lambda x: x.split("c"), [["b", ""], ["", "d"], ["df"]]),
    (
        "partition-scalar",
        lambda x: x.partition("c"),
        [["b", "c", ""], ["", "c", "d"], ["df", "", ""]],
    ),
    ("startswith-scalar", lambda x: x.startswith("b"), [True, False, False]),
    ("endswith-scalar", lambda x: x.endswith("f"), [False, False, True]),
    ("replace-scalar", lambda x: x.replace("c", "q"), ["bq", "qd", "df"]),
    ("nest-list", lambda x: list_.make_list(a=x), [["bc"], ["cd"], ["df"]]),
    ("nest-dict", lambda x: dict_(a=x), [{"a": "bc"}, {"a": "cd"}, {"a": "df"}]),
]


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    string_ops_test_cases
    + [
        ("pick", lambda x: dict_(bc=1, cd=2, df=3)[x], [1, 2, 3]),
    ],
)
def test_arrow_vectorizer_string_scalar(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow(["bc", "cd", "df"]))
    fn = weave_internal.define_fn({"x": weave.types.String()}, weave_func).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert list(weave.use(called)) == expected_output


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    string_ops_test_cases,
)
def test_arrow_vectorizer_string_scalar_tagged(name, weave_func, expected_output):

    expected_value_type = weave.type_of(expected_output[0])

    list = ["bc", "cd", "df"]
    for i, elem in enumerate(list):
        taggable = box.box(elem)
        list[i] = tag_store.add_tags(taggable, {"mytag": f"test{i + 1}"})

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("mytag", types.String())

    awl = arrow.to_arrow(list)
    l = weave.save(awl)
    fn = weave_internal.define_fn({"x": awl.object_type}, weave_func).val
    vec_fn = arrow.vectorize(fn)

    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist_notags() == expected_output

    item_node = arrow.ArrowWeaveList.__getitem__(called, 0)

    def make_exp_tag(t: types.Type):
        return tagged_value_type.TaggedValueType(
            types.TypedDict({"mytag": types.String()}),
            t,
        )

    expected_type_obj_type = make_exp_tag(expected_value_type)
    # The general test here is not general enough to check these properly.
    # Specifcially, the general test assumes the vecotrize lambdas contians all
    # tag flow ops. However, list and dict constructors are explicitly (and
    # correctly) not tag flow ops and therefore the tags are only present on the
    # elements of the list and dict.
    if name == "nest-dict":
        item_node = item_node["a"]
        expected_type_obj_type = types.TypedDict(
            {
                "a": make_exp_tag(expected_value_type.property_types["a"]),
                **expected_value_type.property_types,
            }
        )
    elif name == "nest-list":
        item_node = item_node[0]
        expected_type_obj_type = types.List(
            make_exp_tag(expected_value_type.object_type)
        )

    # check that tags are propagated
    assert weave.use(tag_getter_op(item_node)) == "test1"

    # NOTE: This optionality is needed because some arrow ops eagerly declare
    # optional returns. See number.py and string.py for commentary on the subject.
    assert arrow.ArrowWeaveListType(types.optional(expected_type_obj_type)).assign_type(
        called.type
    )


string_alnum_test_cases = [
    (
        "isAlpha-scalar",
        lambda x: x.isalpha(),
        [False, True, False, False, False, False],
    ),
    (
        "isNumeric-scalar",
        lambda x: x.isnumeric(),
        [False, False, False, True, False, False],
    ),
    (
        "isAlnum-scalar",
        lambda x: x.isalnum(),
        [False, True, True, True, False, False],
    ),
    (
        "lower-scalar",
        lambda x: x.lower(),
        ["b22?c", "cd", "df2", "212", "", "?>!@#"],
    ),
    (
        "upper-scalar",
        lambda x: x.upper(),
        ["B22?C", "CD", "DF2", "212", "", "?>!@#"],
    ),
    (
        "slice-scalar",
        lambda x: x.slice(1, 2),
        ["2", "d", "F", "1", "", ">"],
    ),
]


@pytest.mark.parametrize("name,weave_func,expected_output", string_alnum_test_cases)
def test_arrow_vectorizer_string_alnum(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow(["B22?c", "cd", "DF2", "212", "", "?>!@#"]))
    fn = weave_internal.define_fn({"x": weave.types.String()}, weave_func).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist() == expected_output


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    string_alnum_test_cases,
)
def test_arrow_vectorizer_string_alnum_tagged(name, weave_func, expected_output):

    # NOTE: This optionality is needed because some arrow ops eagerly declare
    # optional returns. See number.py and string.py for commentary on the subject.
    expected_value_type = types.optional(weave.type_of(expected_output[0]))

    list = ["B22?c", "cd", "DF2", "212", "", "?>!@#"]
    for i, elem in enumerate(list):
        taggable = box.box(elem)
        list[i] = tag_store.add_tags(taggable, {"mytag": f"test{i + 1}"})

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("mytag", types.String())

    awl = arrow.to_arrow(list)
    l = weave.save(awl)
    fn = weave_internal.define_fn({"x": awl.object_type}, weave_func).val
    vec_fn = arrow.vectorize(fn)

    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist_notags() == expected_output

    # check that tags are propagated
    assert (
        weave.use(tag_getter_op(arrow.ArrowWeaveList.__getitem__(called, 0))) == "test1"
    )

    assert arrow.ArrowWeaveListType(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"mytag": types.String()}),
            expected_value_type,
        )
    ).assign_type(called.type)


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    [
        ("strip-scalar", lambda x: x.strip(), ["c", "cd", "DF2", "212", ""]),
        ("lstrip-scalar", lambda x: x.lstrip(), ["c ", "cd", "DF2", "212 ", ""]),
        ("rstrip-scalar", lambda x: x.rstrip(), ["  c", "cd", " DF2", "212", ""]),
    ],
)
def test_arrow_vectorizer_string_strip(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow(["  c ", "cd", " DF2", "212 ", ""]))
    fn = weave_internal.define_fn({"x": weave.types.String()}, weave_func).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist() == expected_output


number_ops_test_cases = [
    ("add", lambda x: x + 2, [3.0, 4.0, 5.0]),
    ("add-vec", lambda x: x + x, [2.0, 4.0, 6.0]),
    ("subtract", lambda x: x - 1, [0.0, 1.0, 2.0]),
    ("multiply", lambda x: x * 2, [2.0, 4.0, 6.0]),
    ("divide", lambda x: x / 2, [0.5, 1.0, 1.5]),
    ("pow", lambda x: x**2, [1.0, 4.0, 9.0]),
    ("ne", lambda x: x != 2, [True, False, True]),
    ("eq", lambda x: x == 2, [False, True, False]),
    ("gt", lambda x: x > 2, [False, False, True]),
    ("lt", lambda x: x < 2, [True, False, False]),
    ("ge", lambda x: x >= 2, [False, True, True]),
    ("le", lambda x: x <= 2, [True, True, False]),
    ("neg", lambda x: -x, [-1.0, -2.0, -3.0]),
    ("toString", lambda x: x.toString(), ["1", "2", "3"]),
]


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    number_ops_test_cases,
)
def test_arrow_vectorizer_number_ops(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow([1.0, 2.0, 3.0]))

    fn = weave_internal.define_fn({"x": weave.types.Float()}, weave_func).val

    vec_fn = arrow.vectorize(fn)

    # TODO:  make it nicer to call vec_fn, we shouldn't need to jump through hoops here

    called = weave_internal.call_fn(vec_fn, {"x": l})

    assert weave.use(called).to_pylist() == expected_output


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    number_ops_test_cases,
)
def test_arrow_vectorizer_number_ops_tagged(name, weave_func, expected_output):

    expected_value_type = weave.type_of(expected_output[0])

    # This special condition is needed because the expected output is a list of
    # booleans is optional booleans. See the comment at the top of `ops_arrow/number.py`
    # for more details.
    if types.Boolean().assign_type(expected_value_type):
        expected_value_type = types.optional(expected_value_type)

    list = [1.0, 2.0, 3.0]
    for i, elem in enumerate(list):
        taggable = box.box(elem)
        list[i] = tag_store.add_tags(taggable, {"mytag": f"test{i + 1}"})

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("mytag", types.String())

    awl = arrow.to_arrow(list)
    l = weave.save(awl)
    fn = weave_internal.define_fn({"x": awl.object_type}, weave_func).val
    vec_fn = arrow.vectorize(fn)

    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist_notags() == expected_output

    # check that tags are propagated
    assert (
        weave.use(tag_getter_op(arrow.ArrowWeaveList.__getitem__(called, 0))) == "test1"
    )

    assert arrow.ArrowWeaveListType(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"mytag": types.String()}),
            expected_value_type,
        )
    ).assign_type(called.type)


string_vector_ops_test_cases = [
    ("eq-vector", lambda x, y: x == y, [False, False, True]),
    ("ne-vector", lambda x, y: x != y, [True, True, False]),
    ("contains-vector", lambda x, y: x.__contains__(y), [False, False, True]),
    ("in-vector", lambda x, y: x.in_(y), [True, False, True]),
    ("add-vector", lambda x, y: x + y, ["bccbc", "cdaef", "dfdf"]),
    ("append-vector", lambda x, y: x.append(y), ["bccbc", "cdaef", "dfdf"]),
    ("prepend-vector", lambda x, y: x.prepend(y), ["cbcbc", "aefcd", "dfdf"]),
    ("split-vector", lambda x, y: y.split(x), [["c", ""], ["aef"], ["", ""]]),
    (
        "partition-vector",
        lambda x, y: y.partition(x),
        [["c", "bc", ""], ["aef", "", ""], ["", "df", ""]],
    ),
    (
        "startswith-vector",
        lambda x, y: y.startswith(x),
        [False, False, True],
    ),
    ("endswith-vector", lambda x, y: y.endswith(x), [True, False, True]),
]


@pytest.mark.parametrize(
    "name,weave_func,expected_output", string_vector_ops_test_cases
)
def test_arrow_vectorizer_string_vector(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow(["bc", "cd", "df"]))
    l2 = weave.save(arrow.to_arrow(["cbc", "aef", "df"]))

    fn = weave_internal.define_fn(
        {"x": weave.types.String(), "y": weave.types.String()}, weave_func
    ).val

    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l, "y": l2})
    assert weave.use(called).to_pylist() == expected_output


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    string_vector_ops_test_cases,
)
def test_arrow_vectorizer_string_vector_ops_tagged(name, weave_func, expected_output):

    # NOTE: This optionality is needed because some arrow ops eagerly declare
    # optional returns. See number.py and string.py for commentary on the subject.
    expected_value_type = types.optional(weave.type_of(expected_output[0]))

    list = ["bc", "cd", "df"]
    for i, elem in enumerate(list):
        taggable = box.box(elem)
        list[i] = tag_store.add_tags(taggable, {"mytag": f"test{i + 1}"})

    list2 = ["cbc", "aef", "df"]
    for i, elem in enumerate(list2):
        taggable = box.box(elem)
        list2[i] = tag_store.add_tags(taggable, {"mytag2": f"test{i + 1}"})

    awl = arrow.to_arrow(list)
    awl2 = arrow.to_arrow(list2)

    l = weave.save(awl)
    l2 = weave.save(awl2)
    fn = weave_internal.define_fn(
        {"x": awl.object_type, "y": awl2.object_type}, weave_func
    ).val
    vec_fn = arrow.vectorize(fn)

    called = weave_internal.call_fn(vec_fn, {"x": l, "y": l2})
    assert weave.use(called).to_pylist_notags() == expected_output

    # if x is first, expect x tag to be propagated. if y is first, expect y tag to be propagated.
    tag_name: typing.Optional[str] = None
    for name, node in called.iteritems_op_inputs():
        if name == "self":
            tag_name = next(k for k in node.type.object_type.tag.property_types)

    if tag_name is None:
        raise ValueError("tag_getter_op not found")

    tag_getter_op = make_tag_getter_op.make_tag_getter_op(
        tag_name,
        types.String(),
    )

    # check that tags are propagated
    assert (
        weave.use(tag_getter_op(arrow.ArrowWeaveList.__getitem__(called, 0))) == "test1"
    )

    assert arrow.ArrowWeaveListType(
        tagged_value_type.TaggedValueType(
            types.TypedDict({tag_name: types.String()}),
            expected_value_type,
        )
    ).assign_type(called.type)


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    [
        ("floor", lambda x: Number.floor(x), [1.0, 2.0, 3.0]),
        ("ceil", lambda x: Number.ceil(x), [2.0, 3.0, 4.0]),
    ],
)
def test_arrow_floor_ceil_vectorized(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow([1.1, 2.5, 3.9]))
    fn = weave_internal.define_fn({"x": weave.types.Float()}, weave_func).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist() == expected_output


pick_cases = [
    (
        "pick",
        [{"a": 1.0, "b": "c"}, {"a": 2.0, "b": "G"}, {"a": 3.0, "b": "q"}],
        lambda x: x.pick("a"),
        [1.0, 2.0, 3.0],
    ),
    (
        "pick-nested",
        [
            {"a": {"b": 1.0}, "c": "d"},
            {"a": {"b": 2.0}, "c": "G"},
            {"a": {"b": 3.0}, "c": "q"},
        ],
        lambda x: x.pick("a").pick("b"),
        [1.0, 2.0, 3.0],
    ),
]


@pytest.mark.parametrize("name,input_data,weave_func,expected_output", pick_cases)
def test_arrow_typeddict_pick(input_data, name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow(input_data))
    fn = weave_internal.define_fn(
        {"x": weave.type_of(input_data).object_type}, weave_func
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist() == expected_output
    assert called.type == arrow.ArrowWeaveListType(
        weave.type_of(expected_output).object_type
    )


@pytest.mark.parametrize("name,input_data,weave_func,expected_output", pick_cases)
def test_arrow_typeddict_pick_tagged(input_data, name, weave_func, expected_output):

    # tag each dict and one of its values
    for i, elem in enumerate(input_data):
        taggable = box.box(elem)
        input_data[i] = tag_store.add_tags(
            taggable, {"dict_tag": f"{input_data}[{i}] = {elem}"}
        )
        input_data[i]["a"] = tag_store.add_tags(
            box.box(input_data[i]["a"]),
            {"first_level_tag": f"{input_data}[{i}]['a'] = {elem['a']}"},
        )
        if name == "pick-nested":
            input_data[i]["a"]["b"] = tag_store.add_tags(
                box.box(input_data[i]["a"]["b"]),
                {"second_level_tag": f"{input_data}[{i}]['a']['b'] = {elem['a']['b']}"},
            )

    l = weave.save(arrow.to_arrow(input_data))
    fn = weave_internal.define_fn(
        {"x": weave.type_of(input_data).object_type}, weave_func
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})

    assert weave.use(called).to_pylist_notags() == expected_output
    expected_output_object_type = tagged_value_type.TaggedValueType(
        types.TypedDict(
            property_types={
                "dict_tag": types.String(),
                "first_level_tag": types.String(),
                **(
                    {"second_level_tag": types.String()}
                    if name == "pick-nested"
                    else {}
                ),
            }
        ),
        types.Float(),
    )
    assert called.type == arrow.ArrowWeaveListType(expected_output_object_type)

    tag_getter_op = make_tag_getter_op.make_tag_getter_op(
        "first_level_tag", types.String()
    )

    for i, elem in enumerate(input_data):
        tag = f"{input_data}[{i}]['a'] = {elem['a']}"
        assert (
            weave.use(tag_getter_op(arrow.ArrowWeaveList.__getitem__(called, i))) == tag
        )


@pytest.mark.parametrize(
    "name,input_datal,input_datar,weave_func,expected_output",
    [
        (
            "merge",
            [{"b": "c"}, {"b": "G"}, {"b": "q"}],
            [{"c": 4}, {"c": 5}, {"c": 6}],
            lambda x, y: x.merge(y),
            [{"b": "c", "c": 4}, {"b": "G", "c": 5}, {"b": "q", "c": 6}],
        ),
        (
            "merge-overwrite",
            [{"b": "c"}, {"b": "G"}, {"b": "q"}],
            [{"b": "g"}, {"b": "q"}, {"b": "a"}],
            lambda x, y: x.merge(y),
            [{"b": "g"}, {"b": "q"}, {"b": "a"}],
        ),
        (
            "merge-dicts",
            [{"b": "c"}, {"b": "G"}, {"b": "q"}],
            [{"c": {"a": 2}}, {"c": {"a": 3}}, {"c": {"a": 4}}],
            lambda x, y: x.merge(y),
            [
                {"b": "c", "c": {"a": 2}},
                {"b": "G", "c": {"a": 3}},
                {"b": "q", "c": {"a": 4}},
            ],
        ),
    ],
)
def test_arrow_typeddict_merge(
    input_datal, input_datar, name, weave_func, expected_output
):
    l = weave.save(arrow.to_arrow(input_datal))
    r = weave.save(arrow.to_arrow(input_datar))
    fn = weave_internal.define_fn(
        {
            "x": weave.type_of(input_datal).object_type,
            "y": weave.type_of(input_datar).object_type,
        },
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l, "y": r})
    awl = weave.use(called)
    assert awl.to_pylist() == expected_output
    assert called.type == arrow.ArrowWeaveListType(
        weave.type_of(expected_output).object_type
    )
    assert awl.object_type == weave.type_of(expected_output).object_type


def test_arrow_typeddict_simple_merge_tagged():

    input_datal = [{"b": "c"}, {"b": "G"}, {"b": "q"}]
    input_datar = [{"c": 4}, {"c": 5}, {"c": 6}]
    weave_func = lambda x, y: x.merge(y)
    expected_output = [{"b": "c", "c": 4}, {"b": "G", "c": 5}, {"b": "q", "c": 6}]

    for i, elem in enumerate(input_datal):
        input_datal[i]["b"] = tag_store.add_tags(box.box(elem["b"]), {"tag": "a"})

    l = weave.save(arrow.to_arrow(input_datal))
    r = weave.save(arrow.to_arrow(input_datar))
    fn = weave_internal.define_fn(
        {
            "x": types.TypedDict({"b": types.String()}),
            "y": types.TypedDict({"c": types.Int()}),
        },
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    # here we call refine graph so we can have called be a RuntimeOutputNode,
    # which allows the dispatch we us in the tag getter op assert
    called = weave_internal.refine_graph(
        weave_internal.call_fn(vec_fn, {"x": l, "y": r})
    )
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("tag", types.String())
    tag = weave.use(tag_getter_op(called[0]["b"]))
    assert tag == "a"

    assert called.type == arrow.ArrowWeaveListType(
        types.TypedDict(
            {
                "b": tagged_value_type.TaggedValueType(
                    types.TypedDict({"tag": types.String()}), types.String()
                ),
                "c": types.Int(),
            }
        )
    )


def test_arrow_typeddict_overwrite_merge_tagged():

    input_datal = [{"b": "c"}, {"b": "G"}, {"b": "q"}]
    input_datar = [{"b": "g"}, {"b": "q"}, {"b": "a"}]
    weave_func = lambda x, y: x.merge(y)
    expected_output = [{"b": "g"}, {"b": "q"}, {"b": "a"}]

    for i, elem in enumerate(input_datar):
        input_datar[i]["b"] = tag_store.add_tags(box.box(elem["b"]), {"tag": "a"})

    l = weave.save(arrow.to_arrow(input_datal))
    r = weave.save(arrow.to_arrow(input_datar))
    fn = weave_internal.define_fn(
        {
            "x": types.TypedDict({"b": types.String()}),
            "y": types.TypedDict({"b": types.String()}),
        },
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    # here we call refine graph so we can have called be a RuntimeOutputNode,
    # which allows the dispatch we us in the tag getter op assert
    called = weave_internal.refine_graph(
        weave_internal.call_fn(vec_fn, {"x": l, "y": r})
    )
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("tag", types.String())
    tag = weave.use(tag_getter_op(called[0]["b"]))
    assert tag == "a"

    assert called.type == arrow.ArrowWeaveListType(
        types.TypedDict(
            {
                "b": tagged_value_type.TaggedValueType(
                    types.TypedDict({"tag": types.String()}), types.String()
                ),
            }
        )
    )


def test_arrow_typeddict_dicts_merge_tagged():
    input_datal = [{"b": "c"}, {"b": "G"}, {"b": "q"}]
    input_datar = [{"c": {"a": 2}}, {"c": {"a": 3}}, {"c": {"a": 4}}]
    weave_func = lambda x, y: x.merge(y)
    expected_output = [
        {"b": "c", "c": {"a": 2}},
        {"b": "G", "c": {"a": 3}},
        {"b": "q", "c": {"a": 4}},
    ]

    for i, elem in enumerate(input_datar):
        input_datar[i]["c"]["a"] = tag_store.add_tags(
            box.box(elem["c"]["a"]), {"tag": "a"}
        )

    l = weave.save(arrow.to_arrow(input_datal))
    r = weave.save(arrow.to_arrow(input_datar))
    fn = weave_internal.define_fn(
        {
            "x": types.TypedDict({"b": types.String()}),
            "y": types.TypedDict({"c": types.TypedDict({"a": types.Int()})}),
        },
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    # here we call refine graph so we can have called be a RuntimeOutputNode,
    # which allows the dispatch we us in the tag getter op assert
    called = weave_internal.refine_graph(
        weave_internal.call_fn(vec_fn, {"x": l, "y": r})
    )
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("tag", types.String())
    tag = weave.use(tag_getter_op(called[0]["c"]["a"]))
    assert tag == "a"

    assert called.type == arrow.ArrowWeaveListType(
        types.TypedDict(
            {
                "b": types.String(),
                "c": types.TypedDict(
                    {
                        "a": tagged_value_type.TaggedValueType(
                            types.TypedDict({"tag": types.String()}), types.Int()
                        )
                    }
                ),
            }
        )
    )


def test_arrow_typeddict_nested_merge_tagged():
    """Tests that nested merging is disabled."""
    input_datal = [{"a": {"c": 1}}, {"a": {"c": 2}}, {"a": {"c": 3}}]
    input_datar = [{"a": {"b": 2}}, {"a": {"b": 4}}, {"a": {"b": 6}}]
    weave_func = lambda x, y: x.merge(y)
    expected_output = [
        {"a": {"b": 2}},
        {"a": {"b": 4}},
        {"a": {"b": 6}},
    ]

    for i, elem in enumerate(input_datal):
        input_datal[i]["a"]["c"] = tag_store.add_tags(
            box.box(elem["a"]["c"]), {"tag": "a"}
        )

    l = weave.save(arrow.to_arrow(input_datal))
    r = weave.save(arrow.to_arrow(input_datar))
    fn = weave_internal.define_fn(
        {
            "x": weave.type_of(input_datal).object_type,
            "y": weave.type_of(input_datar).object_type,
        },
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l, "y": r})
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    assert called.type == arrow.ArrowWeaveListType(
        types.TypedDict(
            {
                "a": types.TypedDict(
                    {
                        "b": types.Int(),
                    }
                )
            }
        )
    )


def test_arrow_dict_tagged():
    to_tag = box.box([1, 2, 3])
    for i, elem in enumerate(to_tag):
        taggable = box.box(elem)
        to_tag[i] = tag_store.add_tags(taggable, {"a": f"{elem}"})
    tag_store.add_tags(to_tag, {"outer": "tag"})
    a = weave.save(arrow.to_arrow(to_tag))
    b = weave.save(arrow.to_arrow(["a", "b", "c"]))
    expected_output = [{"a": 1, "b": "a"}, {"a": 2, "b": "b"}, {"a": 3, "b": "c"}]
    weave_func = lambda a, b: ops.dict_(a=a, b=b)
    fn = weave_internal.define_fn(
        {"a": a.type.object_type, "b": b.type.object_type},
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"a": a, "b": b})

    # this is needed becasue the argtypes of fn do not include the tag types on a and b. so when we call
    # vec fn on a and b, the type of called does not include the tags on a and b. refining the graph
    # causes the type system to look at the types of a and b and recompute the type of called accordingly.
    called = weave_internal.refine_graph(called)
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    # tags should not flow to output list because the op has no named arguments,
    # just varargs.
    assert not isinstance(weave.type_of(awl), tagged_value_type.TaggedValueType)

    assert called.type == arrow.ArrowWeaveListType(
        types.TypedDict(
            {
                "a": tagged_value_type.TaggedValueType(
                    types.TypedDict({"outer": types.String(), "a": types.String()}),
                    types.Int(),
                ),
                "b": types.String(),
            }
        )
    )

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("a", types.String())
    tag_node = tag_getter_op(called[0]["a"])
    assert weave.use(tag_node) == "1"

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("outer", types.String())
    tag_node = tag_getter_op(called[0]["a"])
    assert weave.use(tag_node) == "tag"


def _make_tagged_awl():
    to_tag = box.box(["a", "b", "c"])
    for i, elem in enumerate(to_tag):
        taggable = box.box(elem)
        to_tag[i] = tag_store.add_tags(taggable, {"a": f"{elem}"})
    to_tag = tag_store.add_tags(to_tag, {"outer": "tag"})
    return weave.save(arrow.to_arrow(to_tag))


def test_arrow_dict_map_tagged():
    tagged_awl = _make_tagged_awl()
    expected_output = [{"a": "a", "b": 1}, {"a": "b", "b": 1}, {"a": "c", "b": 1}]
    weave_func = lambda row: ops.dict_(a=row, b=1)
    fn = weave_internal.define_fn(
        {"row": tagged_awl.type.object_type},
        weave_func,
    )

    called = tagged_awl.map(fn)
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("outer", types.String())
    tag_node = tag_getter_op(called[0]["a"])
    assert weave.use(tag_node) == "tag"

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("a", types.String())
    tag_node = tag_getter_op(called[0]["a"])
    assert weave.use(tag_node) == "a"


def test_arrow_filter_tagged():
    tagged_awl = _make_tagged_awl()
    expected_output = ["b", "c"]
    weave_func = lambda row: (row != "a")
    fn = weave_internal.define_fn(
        {"row": tagged_awl.type.object_type},
        weave_func,
    )

    called = tagged_awl.filter(fn)
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("outer", types.String())
    tag_node = tag_getter_op(called[0])
    assert weave.use(tag_node) == "tag"

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("a", types.String())
    tag_node = tag_getter_op(called[0])
    assert weave.use(tag_node) == "b"


def test_arrow_sort_tagged():
    tagged_awl = _make_tagged_awl()
    expected_output = ["c", "b", "a"]
    weave_func = lambda row: list_.make_list(a=row)
    fn = weave_internal.define_fn(
        {"row": tagged_awl.type.object_type},
        weave_func,
    )

    called = tagged_awl.sort(fn, ["desc"])
    awl = weave.use(called)
    assert awl.to_pylist_notags() == expected_output

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("outer", types.String())
    tag_node = tag_getter_op(called[0])
    assert weave.use(tag_node) == "tag"

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("a", types.String())
    tag_node = tag_getter_op(called[0])
    assert weave.use(tag_node) == "c"


def test_arrow_filter_nulls():
    awl = weave.save(arrow.to_arrow([-1, 0, 1, None]))
    weave_func = lambda row: row < 1
    fn = weave_internal.define_fn(
        {"row": awl.type.object_type},
        weave_func,
    )

    called = awl.filter(fn)
    awl = weave.use(called)
    assert awl.to_pylist_notags() == [-1, 0]


def test_arrow_dict():
    a = weave.save(arrow.to_arrow([1, 2, 3]))
    b = weave.save(arrow.to_arrow(["a", "b", "c"]))
    expected_output = [{"a": 1, "b": "a"}, {"a": 2, "b": "b"}, {"a": 3, "b": "c"}]
    weave_func = lambda a, b: ops.dict_(a=a, b=b)
    fn = weave_internal.define_fn(
        {"a": weave.types.Int(), "b": weave.types.String()},
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"a": a, "b": b})
    awl = weave.use(called)
    assert awl.to_pylist() == expected_output
    assert called.type == arrow.ArrowWeaveListType(
        weave.type_of(expected_output).object_type
    )
    assert awl.object_type == weave.type_of(expected_output).object_type


def test_vectorize_works_recursively_on_weavifiable_op():

    # this op is weavifiable because it just calls add
    @weave.op()
    def add_one(x: int) -> int:
        return x + 1

    weave_fn = weave_internal.define_fn(
        {"x": weave.types.Int()}, lambda x: add_one(x)
    ).val
    vectorized = arrow.vectorize(weave_fn)
    expected = vectorized.to_json()
    print("test_vectorize_works_recursively_on_weavifiable_op.expected", expected)
    assert expected == {
        "nodeType": "output",
        "type": {
            "type": "ArrowWeaveList",
            "_base_type": {"type": "list"},
            "objectType": "int",
        },
        "fromOp": {
            "name": "ArrowWeaveListNumber-add",
            "inputs": {
                "self": {
                    "nodeType": "var",
                    "type": {
                        "type": "ArrowWeaveList",
                        "_base_type": {"type": "list"},
                        "objectType": "int",
                    },
                    "varName": "x",
                },
                "other": {"nodeType": "const", "type": "int", "val": 1},
            },
        },
    }


def test_grouped_typed_dict_assign():
    assert types.List(types.TypedDict(property_types={})).assign_type(
        arrow.awl_group_by_result_object_type(
            object_type=types.TypedDict(
                property_types={"a": types.Int(), "im": types.Int()}
            ),
            _key=types.TypedDict(property_types={"a": types.String()}),
        )
    )


def test_arrow_index_var():
    data = arrow.to_arrow([1, 2, 3])
    result = data.map(lambda row, index: row + index)
    assert weave.use(result).to_pylist() == [1, 3, 5]


def test_concat_multiple_table_types():
    datal = weave.save(
        arrow.to_arrow([{"prompt": "a"}, {"prompt": None}, {"prompt": "b"}])
    )
    datar = weave.save(
        arrow.to_arrow(
            [
                {"prompt": None, "generation_prompt": "a"},
                {"prompt": "d", "generation_prompt": None},
                {"prompt": "e", "generation_prompt": "f"},
            ]
        )
    )

    to_concat = ops.make_list(l=datal, r=datar)
    result = arrow.concat(to_concat)

    assert result.type == arrow.ArrowWeaveListType(
        object_type=types.TypedDict(
            property_types={
                "prompt": types.UnionType(types.String(), types.NoneType()),
                "generation_prompt": types.UnionType(types.String(), types.NoneType()),
            }
        )
    )

    result = weave.use(result)

    assert result.to_pylist_notags() == [
        {"prompt": "a", "generation_prompt": None},
        {"prompt": None, "generation_prompt": None},
        {"prompt": "b", "generation_prompt": None},
        {"prompt": None, "generation_prompt": "a"},
        {"prompt": "d", "generation_prompt": None},
        {"prompt": "e", "generation_prompt": "f"},
    ]


def test_concat_multiple_table_types_tagged():
    raw_datal = [{"prompt": "a"}, {"prompt": None}, {"prompt": "b"}]
    raw_datar = [
        {"prompt": None, "generation_prompt": "a"},
        {"prompt": "d", "generation_prompt": None},
        {"prompt": "e", "generation_prompt": "f"},
    ]

    tagged_datal = tag_store.add_tags(box.box(raw_datal), {"tag": "datal"})
    tagged_datar = tag_store.add_tags(box.box(raw_datar), {"tag": "datar"})

    datal = weave.save(arrow.to_arrow(tagged_datal))
    datar = weave.save(arrow.to_arrow(tagged_datar))

    to_concat = ops.make_list(l=datal, r=datar)
    result = arrow.concat(to_concat)

    expected = arrow.ArrowWeaveListType(
        object_type=tagged_value_type.TaggedValueType(
            types.TypedDict({"tag": types.String()}),
            types.TypedDict(
                property_types={
                    "prompt": types.UnionType(types.String(), types.NoneType()),
                    "generation_prompt": types.UnionType(
                        types.String(), types.NoneType()
                    ),
                }
            ),
        )
    )

    assert result.type == expected

    result = weave.use(result)
    assert result.to_pylist_notags() == [
        {"prompt": "a", "generation_prompt": None},
        {"prompt": None, "generation_prompt": None},
        {"prompt": "b", "generation_prompt": None},
        {"prompt": None, "generation_prompt": "a"},
        {"prompt": "d", "generation_prompt": None},
        {"prompt": "e", "generation_prompt": "f"},
    ]


def test_arrow_union_int_string():
    data = [1, "a", 2]
    result = weave.save(arrow.to_arrow(data))
    assert result.type == arrow.ArrowWeaveListType(
        object_type=types.UnionType(types.Int(), types.String())
    )

    assert weave.use(result).to_pylist() == data


def test_arrow_union_int_string_custom_type():
    data = [1, "a", 2, Point2(1, 2)]
    result = weave.save(arrow.to_arrow(data))
    assert result.type == arrow.ArrowWeaveListType(
        object_type=types.UnionType(types.Int(), types.String(), Point2.WeaveType())
    )

    awl = weave.use(result)
    assert [awl._index(i) for i in range(len(data))] == data


def test_arrow_union_two_struct_types_as_single_struct_type():
    data = [{"a": 1}, {"b": 2, "a": 1}, {"b": 3}]
    result = weave.save(arrow.to_arrow(data))
    assert result.type == arrow.ArrowWeaveListType(
        object_type=types.TypedDict(
            {
                "a": types.UnionType(types.Int(), types.NoneType()),
                "b": types.UnionType(types.Int(), types.NoneType()),
            }
        )
    )

    awl = weave.use(result)
    assert awl.to_pylist_notags() == [
        {"a": 1, "b": None},
        {"b": 2, "a": 1},
        {"b": 3, "a": None},
    ]


def test_arrow_concat_nested_union():

    raw_datal = [{"b": 1}]
    raw_datar = [{"b": "c"}]

    datal = weave.save(arrow.to_arrow(raw_datal))
    datar = weave.save(arrow.to_arrow(raw_datar))

    to_concat = ops.make_list(l=datal, r=datar)
    result = arrow.concat(to_concat)

    expected = arrow.ArrowWeaveListType(
        object_type=types.TypedDict(
            property_types={
                "b": types.UnionType(types.String(), types.Int()),
            }
        ),
    )

    assert result.type == expected

    result = weave.use(result)
    assert result.to_pylist_notags() == [
        {"b": 1},
        {"b": "c"},
    ]


def test_arrow_concat_nested_union_with_optional_type():

    raw_datal = [{"b": 1}]
    raw_datar = [{"b": "c", "c": 3.3}]

    datal = weave.save(arrow.to_arrow(raw_datal))
    datar = weave.save(arrow.to_arrow(raw_datar))

    to_concat = ops.make_list(l=datal, r=datar)
    result = arrow.concat(to_concat)

    expected = arrow.ArrowWeaveListType(
        object_type=types.TypedDict(
            property_types={
                "b": types.UnionType(types.String(), types.Int()),
                "c": types.UnionType(types.Float(), types.NoneType()),
            }
        ),
    )

    assert result.type == expected

    result = weave.use(result)
    assert result.to_pylist_notags() == [
        {"b": 1, "c": None},
        {"b": "c", "c": 3.3},
    ]


def test_arrow_concat_nested_union_with_optional_type_and_custom_type():

    raw_datal = [{"b": 1, "x": Point2(1, 2)}]
    raw_datar = [{"b": "c", "c": 3.3}]

    datal = weave.save(arrow.to_arrow(raw_datal))
    datar = weave.save(arrow.to_arrow(raw_datar))

    to_concat = ops.make_list(l=datal, r=datar)
    result = arrow.concat(to_concat)

    expected = arrow.ArrowWeaveListType(
        object_type=types.TypedDict(
            property_types={
                "b": types.UnionType(types.String(), types.Int()),
                "c": types.UnionType(types.Float(), types.NoneType()),
                "x": types.UnionType(Point2.WeaveType(), types.NoneType()),
            }
        ),
    )

    assert result.type == expected

    result = weave.use(result)
    assert [result._index(i) for i in range(len(result))] == [
        {"b": 1, "c": None, "x": Point2(1, 2)},
        {"b": "c", "c": 3.3, "x": None},
    ]


def test_arrow_concat_degenerate_types():

    raw_datal = [{"b": 1, "x": Point2(1, 2)}]
    raw_datar = [{"b": "c", "x": {"x": 1, "y": 2}}]

    datal = weave.save(arrow.to_arrow(raw_datal))
    datar = weave.save(arrow.to_arrow(raw_datar))

    to_concat = ops.make_list(l=datal, r=datar)
    result = arrow.concat(to_concat)

    expected = arrow.ArrowWeaveListType(
        object_type=types.TypedDict(
            property_types={
                "b": types.UnionType(types.String(), types.Int()),
                "x": types.UnionType(
                    Point2.WeaveType(),
                    types.TypedDict({"x": types.Int(), "y": types.Int()}),
                ),
            }
        ),
    )

    assert result.type == expected

    result = weave.use(result)
    assert [result._index(i) for i in range(len(result))] == [
        {"b": 1, "x": Point2(1, 2)},
        {"b": "c", "x": {"x": 1, "y": 2}},
    ]


@pytest.mark.parametrize("li", lath.ListInterfaces)
def test_arrow_timestamp_conversion(li):
    dates = [
        datetime.datetime(2020, 1, 2, 3, 4, 5),
        datetime.datetime(2020, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
    ]
    utc_dates = [d.astimezone(datetime.timezone.utc) for d in dates]
    timestamps = [d.timestamp() for d in utc_dates]

    # Direct datetime type
    data = li.make_node(dates)
    if li == lath.ArrowNode:
        # Arrow converts to UTC on read out
        assert li.use_node(data) == utc_dates
    else:
        assert li.use_node(data) == dates

    # Basic Floats to datetime conversion
    data = li.make_node(timestamps)
    assert li.use_node(data) == timestamps

    # We are always representing timestamps as UTC
    assert li.use_node(data.toTimestamp()) == utc_dates


def test_mapeach_with_tags():
    data = [[2, 3, 4], [2, 3, 4], [2, 3, 4]]
    for i, row in enumerate(data):
        for j, elem in enumerate(row):
            row[j] = tag_store.add_tags(box.box(elem), {"tag": f"row{i}_col{j}"})
        data[i] = tag_store.add_tags(box.box(row), {"tag": f"row{i}"})
    tagged = tag_store.add_tags(box.box(data), {"tag": "top"})

    awl = arrow.to_arrow(tagged)
    node = weave.save(awl)

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("tag", types.String())

    result = arrow.ArrowWeaveList.map_each(node, lambda row: row + 1)
    assert arrow.ArrowWeaveListType(types.List(types.Number())).assign_type(result.type)
    assert weave.use(result).to_pylist_notags() == [[3, 4, 5]] * 3
    assert weave.use(tag_getter_op(result)) == "top"
    assert weave.use(tag_getter_op(result[0])) == "row0"
    assert weave.use(tag_getter_op(result[0][0])) == "row0_col0"


nullable_number_ops_test_cases = [
    ("add", lambda x: x + 2, [3.0, None, 5.0]),
    ("add-vec", lambda x: x + x, [2.0, None, 6.0]),
    ("subtract", lambda x: x - 1, [0.0, None, 2.0]),
    ("multiply", lambda x: x * 2, [2.0, None, 6.0]),
    ("divide", lambda x: x / 2, [0.5, None, 1.5]),
    ("pow", lambda x: x**2, [1.0, None, 9.0]),
    ("ne", lambda x: x != 2, [True, None, True]),
    ("eq", lambda x: x == 2, [False, None, False]),
    ("gt", lambda x: x > 2, [False, None, True]),
    ("lt", lambda x: x < 2, [True, None, False]),
    ("ge", lambda x: x >= 2, [False, None, True]),
    ("le", lambda x: x <= 2, [True, None, False]),
    ("neg", lambda x: -x, [-1.0, None, -3.0]),
    ("toString", lambda x: x.toString(), ["1", None, "3"]),
]


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    nullable_number_ops_test_cases,
)
def test_arrow_vectorizer_nullable_number_ops(name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow([1.0, None, 3.0]))

    fn = weave_internal.define_fn({"x": weave.types.Float()}, weave_func).val

    vec_fn = arrow.vectorize(fn)

    # TODO:  make it nicer to call vec_fn, we shouldn't need to jump through hoops here

    called = weave_internal.call_fn(vec_fn, {"x": l})

    assert weave.use(called).to_pylist() == expected_output


string_ops_nullable_test_cases = [
    ("eq-scalar", lambda x: x == "bc", [True, None, False]),
    ("ne-scalar", lambda x: x != "bc", [False, None, True]),
    ("contains-scalar", lambda x: x.__contains__("b"), [True, None, False]),
    ("in-scalar", lambda x: x.in_("bcd"), [True, None, False]),
    ("len-scalar", lambda x: x.len(), [2, None, 2]),
    ("add-scalar", lambda x: x + "q", ["bcq", None, "dfq"]),
    ("append-scalar", lambda x: x.append("qq"), ["bcqq", None, "dfqq"]),
    ("prepend-scalar", lambda x: x.prepend("qq"), ["qqbc", None, "qqdf"]),
    ("split-scalar", lambda x: x.split("c"), [["b", ""], None, ["df"]]),
    (
        "partition-scalar",
        lambda x: x.partition("c"),
        [["b", "c", ""], None, ["df", "", ""]],
    ),
    ("startswith-scalar", lambda x: x.startswith("b"), [True, None, False]),
    ("endswith-scalar", lambda x: x.endswith("f"), [False, None, True]),
    ("replace-scalar", lambda x: x.replace("c", "q"), ["bq", None, "df"]),
    ("nest-list", lambda x: list_.make_list(a=x), [["bc"], [None], ["df"]]),
    ("nest-dict", lambda x: dict_(a=x), [{"a": "bc"}, {"a": None}, {"a": "df"}]),
]


@pytest.mark.parametrize(
    "name,weave_func,expected_output",
    string_ops_nullable_test_cases,
)
def test_arrow_vectorizer_string_nullable_scalar_ops_tagged(
    name, weave_func, expected_output
):
    expected_value_type = weave.type_of(expected_output[0])

    list = ["bc", None, "df"]
    for i, elem in enumerate(list):
        taggable = box.box(elem)
        list[i] = tag_store.add_tags(taggable, {"mytag": f"test{i + 1}"})

    tag_getter_op = make_tag_getter_op.make_tag_getter_op("mytag", types.String())

    awl = arrow.to_arrow(list)
    l = weave.save(awl)
    fn = weave_internal.define_fn({"x": awl.object_type}, weave_func).val
    vec_fn = arrow.vectorize(fn)

    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist_notags() == expected_output

    item_node = arrow.ArrowWeaveList.__getitem__(called, 0)

    def make_exp_tag(t: types.Type):
        return tagged_value_type.TaggedValueType(
            types.TypedDict({"mytag": types.String()}),
            t,
        )

    expected_type_obj_type = make_exp_tag(expected_value_type)
    # The general test here is not general enough to check these properly.
    # Specifcially, the general test assumes the vecotrize lambdas contians all
    # tag flow ops. However, list and dict constructors are explicitly (and
    # correctly) not tag flow ops and therefore the tags are only present on the
    # elements of the list and dict.
    if name == "nest-dict":
        item_node = item_node["a"]
        expected_type_obj_type = types.TypedDict(
            {
                **expected_value_type.property_types,
                "a": make_exp_tag(
                    types.optional(expected_value_type.property_types["a"])
                ),
            }
        )
    elif name == "nest-list":
        item_node = item_node[0]
        expected_type_obj_type = types.List(
            make_exp_tag(types.optional(expected_value_type.object_type))
        )

    # check that tags are propagated
    assert weave.use(tag_getter_op(item_node)) == "test1"

    # NOTE: This optionality is needed because some arrow ops eagerly declare
    # optional returns. See number.py and string.py for commentary on the subject.
    assert arrow.ArrowWeaveListType(types.optional(expected_type_obj_type)).assign_type(
        called.type
    )


@pytest.mark.parametrize(
    "name,input_datal,input_datar,weave_func,expected_output",
    [
        (
            "merge",
            [{"b": "c"}, None, {"b": "q"}],
            [{"c": 4}, {"c": 5}, {"c": 6}],
            lambda x, y: x.merge(y),
            [{"b": "c", "c": 4}, None, {"b": "q", "c": 6}],
        ),
        (
            "merge-overwrite",
            [{"b": "c"}, None, {"b": "q"}],
            [{"b": "g"}, {"b": "q"}, {"b": "a"}],
            lambda x, y: x.merge(y),
            [{"b": "g"}, None, {"b": "a"}],
        ),
        (
            "merge-dicts",
            [{"b": "c"}, None, {"b": "q"}],
            [{"c": {"a": 2}}, {"c": {"a": 3}}, {"c": {"a": 4}}],
            lambda x, y: x.merge(y),
            [
                {"b": "c", "c": {"a": 2}},
                None,
                {"b": "q", "c": {"a": 4}},
            ],
        ),
    ],
)
def test_arrow_typeddict_nullable_merge(
    input_datal, input_datar, name, weave_func, expected_output
):
    l = weave.save(arrow.to_arrow(input_datal))
    r = weave.save(arrow.to_arrow(input_datar))

    fn = weave_internal.define_fn(
        {
            "x": weave.type_of(input_datal).object_type,
            "y": weave.type_of(input_datar).object_type,
        },
        weave_func,
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l, "y": r})
    awl = weave.use(called)
    assert awl.to_pylist() == expected_output
    assert called.type == arrow.ArrowWeaveListType(
        weave.type_of(expected_output).object_type
    )
    assert awl.object_type == weave.type_of(expected_output).object_type


nullable_pick_cases = [
    (
        "pick",
        [None, {"a": 2.0, "b": "G"}, {"a": 3.0, "b": "q"}],
        lambda x: x.pick("a"),
        [None, 2.0, 3.0],
    ),
    (
        "pick-nested",
        [
            {"a": None, "c": "d"},
            {"a": {"b": 2.0}, "c": "G"},
            {"a": {"b": 3.0}, "c": "q"},
        ],
        lambda x: x.pick("a").pick("b"),
        [None, 2.0, 3.0],
    ),
]


@pytest.mark.parametrize(
    "name,input_data,weave_func,expected_output", nullable_pick_cases
)
def test_arrow_typeddict_pick_nullable(input_data, name, weave_func, expected_output):
    l = weave.save(arrow.to_arrow(input_data))
    fn = weave_internal.define_fn(
        {"x": weave.type_of(input_data).object_type}, weave_func
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"x": l})
    assert weave.use(called).to_pylist() == expected_output
    assert called.type == arrow.ArrowWeaveListType(
        weave.type_of(expected_output).object_type
    )


def test_object_types_nullable():
    data_node = arrow.to_arrow(
        [
            {"a": 5, "point": Point2(256, 256)},
            {"a": 6, "point": None},
        ]
    )
    assert weave.use(data_node[0]["point"].get_x()) == 256

    assert weave.use(data_node.map(lambda row: row["point"].get_x())).to_pylist() == [
        256,
        None,
    ]


def test_unflatten_structs_in_flattened_table():
    flattened_table = pa.table(
        {
            "a➡️b➡️c": [1, 2, 3],
            "a➡️b➡️d": [4, 5, 6],
            "a➡️e": [7, 8, 9],
            "g": ["a", "b", "c"],
        }
    )
    result = arrow._unflatten_structs_in_flattened_table(flattened_table)
    struct_result = pa.array(
        [
            {"a": {"b": {"c": 1, "d": 4}, "e": 7}, "g": "a"},
            {"a": {"b": {"c": 2, "d": 5}, "e": 8}, "g": "b"},
            {"a": {"b": {"c": 3, "d": 6}, "e": 9}, "g": "c"},
        ]
    )
    assert result == pa.table(
        {"a": struct_result.field("a"), "g": struct_result.field("g")}
    )


def test_map_with_index():
    ref = create_arrow_data(100)

    node = weave.get(ref).map(lambda row, index: index)
    assert weave.use(node).to_pylist() == list(range(100))


def verify_pyarrow_array_type_is_valid_for_tag_array(pa_type: pa.DataType):
    if pa.types.is_string(pa_type):
        raise errors.WeaveInternalError(
            "Encountered invalid tag array, expected a DictionaryArray, got a StringArray"
        )
    elif pa.types.is_struct(pa_type):
        for field in pa_type:
            verify_pyarrow_array_type_is_valid_for_tag_array(field.type)
    elif pa.types.is_list(pa_type):
        verify_pyarrow_array_type_is_valid_for_tag_array(pa_type.value_type)


def test_verify_dictionary_encoding_of_strings():
    data = pa.array(["1", "2", "3"])

    # raises
    with pytest.raises(errors.WeaveInternalError):
        verify_pyarrow_array_type_is_valid_for_tag_array(data.type)

    data = pa.array([{"a": "1"}, {"a": "2"}, {"a": "3"}])

    # raises
    with pytest.raises(errors.WeaveInternalError):
        verify_pyarrow_array_type_is_valid_for_tag_array(data.type)

    converted = arrow.recursively_encode_pyarrow_strings_as_dictionaries(data)

    # does not raise
    verify_pyarrow_array_type_is_valid_for_tag_array(converted.type)

    data = pa.array([["1"], ["2"], ["3"]])
    # raises
    with pytest.raises(errors.WeaveInternalError):
        verify_pyarrow_array_type_is_valid_for_tag_array(data.type)

    converted = arrow.recursively_encode_pyarrow_strings_as_dictionaries(data)

    # does not raise
    verify_pyarrow_array_type_is_valid_for_tag_array(converted.type)


@pytest.mark.parametrize(
    "list_of_data, exp_res",
    [
        # Empty Case
        ([[]], []),
        # Base Case
        (
            [
                [{"a": 1, "b": 2}, {"a": 2, "b": 3}],
                [{"a": 4, "b": 5}, {"a": 6, "b": 7}],
            ],
            [{"a": 1, "b": 2}, {"a": 2, "b": 3}, {"a": 4, "b": 5}, {"a": 6, "b": 7}],
        ),
        # Deeply Mixed Case
        (
            [
                [{"a": {"c": 1, "d": 2}, "b": {"d": 3, "c": 4}}],
                [{"b": {"d": 5, "c": 6}, "a": {"c": 7, "d": 8}}],
            ],
            [
                {"a": {"c": 1, "d": 2}, "b": {"d": 3, "c": 4}},
                {"a": {"c": 7, "d": 8}, "b": {"c": 6, "d": 5}},
            ],
        ),
        # Mix of lists and dicts
        (
            [
                [{"a": [{"c": 1, "d": 2}, {"d": 3, "c": 4}]}],
                [{"a": [{"d": 5, "c": 6}, {"c": 7, "d": 8}]}],
            ],
            [
                {"a": [{"c": 1, "d": 2}, {"d": 3, "c": 4}]},
                {"a": [{"d": 5, "c": 6}, {"c": 7, "d": 8}]},
            ],
        ),
        # Nested Mixed Types
        (
            [
                [{"a": 1, "b": 2, "c": 4}, {"a": "a", "b": 3, "c": 5}],
                [{"a": 4, "b": 5, "c": "c"}, {"a": 6, "b": 7}],
            ],
            [
                {"a": 1, "b": 2, "c": 4},
                {"a": "a", "b": 3, "c": 5},
                {"a": 4, "b": 5, "c": "c"},
                {"a": 6, "b": 7, "c": None},
            ],
        ),
        # Nested Mixed Types (flat w/ varying depth)
        (
            [
                [{"a": 1}],
                [{"a": [1]}],
                [{"a": "a"}],
                [{"a": ["a"]}],
                [{"a": {"b": 1}}],
                [{"a": [{"b": 1}]}],
            ],
            [
                {"a": 1},
                {"a": [1]},
                {"a": "a"},
                {"a": ["a"]},
                {"a": {"b": 1}},
                {"a": [{"b": 1}]},
            ],
        ),
    ],
)
def test_arrow_concat_mixed(list_of_data, exp_res):
    assert (
        weave.use(
            ops.make_list(
                **{
                    f"{ndx}": weave.save(arrow.to_arrow(data))
                    for ndx, data in enumerate(list_of_data)
                }
            ).concat()
        ).to_pylist()
        == exp_res
    )


def test_abs():
    data = [-10, -2.2, 5, None, 3.3]
    arrow_node = weave.save(arrow.to_arrow(data))
    assert weave.use(arrow_node.abs()).to_pylist() == [10, 2.2, 5, None, 3.3]


def test_argmax():
    data = [10, 20, None, 30, 40, None, 30, 20, None, 10]
    arrow_node = weave.save(arrow.to_arrow(data))
    assert weave.use(arrow_node.argmax()) == 4


def test_argmin():
    data = [10, 20, None, 30, 40, None, 0, 20, None, 10]
    arrow_node = weave.save(arrow.to_arrow(data))
    assert weave.use(arrow_node.argmin()) == 6


def test_stddev():
    data = [10, 20, None, 30, 40, None, 0, 20, None, 10]
    arrow_node = weave.save(arrow.to_arrow(data))
    res = round(weave.use(arrow_node.stddev()), 3)
    assert res == 12.454


def test_join_all_struct_val():
    t1 = arrow.to_arrow([{"a": 5, "b": {"c": 6}}])
    t2 = arrow.to_arrow([{"a": 9, "b": {"c": 10}}, {"a": 5, "b": {"c": 11}}])

    tables = weave.save([t1, t2])
    joined = tables.joinAll(lambda row: row["a"], True)
    res = weave.use(joined).to_pylist()
    # TODO: not correct, not because of join, because artifact saving is broken.
    assert res == [
        {"_tag": {"joinObj": 5}, "_value": {"a": [5, 5], "b": [{"c": 6}, {"c": 11}]}},
        {"_tag": {"joinObj": 9}, "_value": {"a": [None, 9], "b": [None, {"c": 10}]}},
    ]


def test_dense_sparse_conversion():
    xs = pa.array([None, 6, 7])
    ys = pa.array([False, True])
    types = pa.array([0, 1, 1, 0, 0], type=pa.int8())
    offsets = pa.array([0, 0, 1, 1, 2], type=pa.int32())
    union_arr = pa.UnionArray.from_dense(types, offsets, [xs, ys])

    sparse = arrow_type.dense_union_to_sparse_union(union_arr)
    assert sparse.type.mode == "sparse"
    assert sparse.to_pylist() == union_arr.to_pylist()

    dense = arrow_type.sparse_union_to_dense_union(sparse)
    assert dense.type.mode == "dense"
    assert dense.to_pylist() == sparse.to_pylist()


def test_to_arrow_union_list():
    val = [{"a": 5.0}, {"a": [1.0]}]
    arrow_val = arrow.to_arrow([{"a": 5.0}, {"a": [1.0]}])
    assert arrow_val.to_pylist() == val


def test_concat_empty_arrays():
    val = arrow.to_arrow([])
    val2 = arrow.to_arrow([{"a": 5}])
    assert val.concatenate(val).to_pylist() == []
    assert val.concatenate(val2).to_pylist() == val2.to_pylist()
    assert val2.concatenate(val).to_pylist() == val2.to_pylist()
    assert val2.concatenate(val2).to_pylist() == [{"a": 5}, {"a": 5}]


_loading_builtins_token = context_state.set_loading_built_ins()


def _test_arrow_do_body(a: int, b: int, c: list[int]) -> int:
    return a * b + a ** c[0]


@weave.op()
def _test_arrow_do_op(a: int, b: int, c: list[int]) -> int:
    if isinstance(a, graph.Node):
        raise errors.WeavifyError("weavifying")
    return _test_arrow_do_body(a, b, c)


context_state.clear_loading_built_ins(_loading_builtins_token)


def test_automap_more_than_one():
    data = [1, 2, -5, -100]
    arrow_data = weave.save(arrow.to_arrow(data))

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(x, x, [4]))
    ).to_pylist() == [_test_arrow_do_body(x, x, [4]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(x + 1, x, [4]))
    ).to_pylist() == [_test_arrow_do_body(x + 1, x, [4]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(x + 1, x, ops.make_list(a=x * 2)))
    ).to_pylist() == [_test_arrow_do_body(x + 1, x, [x * 2]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(-1, x, ops.make_list(a=x * 2)))
    ).to_pylist() == [_test_arrow_do_body(-1, x, [x * 2]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(-1, -9, ops.make_list(a=x * 2)))
    ).to_pylist() == [_test_arrow_do_body(-1, -9, [x * 2]) for x in data]


def test_vectorize_inner_lambdas():
    l = weave.save(arrow.to_arrow([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))
    inner_fn = weave_internal.define_fn(
        {"row": l.type.object_type.object_type}, lambda row: row + 1
    )
    fn = weave_internal.define_fn(
        {"row": l.type.object_type}, lambda row: row.map(inner_fn)
    ).val
    vec_fn = arrow.vectorize(fn)
    called = weave_internal.call_fn(vec_fn, {"row": l})
    assert list(weave.use(called)) == [[2, 3, 4], [5, 6, 7], [8, 9, 10]]
