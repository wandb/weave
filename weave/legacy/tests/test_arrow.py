import datetime
import hashlib
import itertools
import string

import pyarrow as pa
import pytest
from PIL import Image

from weave.legacy.weave import api as weave
from weave.legacy.weave import (
    box,
    context_state,
    errors,
    graph,
    mappers_arrow,
    ops,
    storage,
    weave_internal,
)

# If you're thinking of import vectorize here, don't! Put your
# tests in test_arrow_vectorizer.py instead
from weave.legacy.weave import ops_arrow as arrow
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.arrow import constructors
from weave.legacy.weave.arrow.arrow_tags import (
    recursively_encode_pyarrow_strings_as_dictionaries,
)
from weave.legacy.weave.language_features.tagging import (
    make_tag_getter_op,
    tag_store,
    tagged_value_type,
)
from weave.legacy.weave.op_def import map_type
from weave.legacy.weave.ops_domain import project_ops
from weave.legacy.weave.ops_primitives import list_, make_list
from .util import list_arrow_test_helpers as lath

from weave.legacy.tests.util import tag_test_util as ttu
from weave.legacy.tests.util import weavejs_ops
from . import test_wb

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
        weave_internal.define_fn(
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
        weave_internal.define_fn(
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
    data_node = arrow.to_weave_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    assert weave.use(data_node[0]["im"].width_()) == 256

    assert weave.use(data_node.map(lambda row: row["im"].width_())).to_pylist_raw() == [
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
    assert weave.use(mapped_width_node).to_pylist_raw() == [
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
    assert weave.use(weave_internal.const(data2)[0]["im"].width_()) == 256


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
    assert weave.use(weave_internal.const(data2)[0]["im"].width_()) == [256]


def test_custom_tagged_groupby1():
    im1 = tag_store.add_tags(Image.linear_gradient("L").rotate(0), {"a": 1})
    im2 = tag_store.add_tags(Image.linear_gradient("L").rotate(4), {"a": 2})
    raw_data = box.box([{"a": 5, "im": im1}, {"a": 6, "im": im2}])
    data_node = weave.save(arrow.to_arrow(raw_data))
    grouped_node = data_node.groupby(lambda row: ops.dict_(a=row["a"]))
    group1_node = grouped_node[0]

    assert grouped_node.type == arrow.ops.awl_group_by_result_type(
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

    assert group1_node.type == arrow.ops.awl_group_by_result_object_type(
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
        arrow.ops.awl_group_by_result_type(
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
    data = arrow.to_weave_arrow(
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
    data = arrow.to_weave_arrow(
        [
            {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
            {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
        ]
    )
    node = data.groupby(lambda row: ops.dict_(a=row["a"]))[0]
    saved_node = weave.save(node, "test_custom_groupby_intermediate_save:latest")
    weave.use(saved_node)
    loaded_node = ops.get(
        "local-artifact:///test_custom_groupby_intermediate_save:latest/obj"
    )
    assert weave.use(loaded_node.pick("im").offset(0)[0].width_()) == 256


def test_map_array():
    data = arrow.to_weave_arrow([1, 2, 3])
    assert weave.use(data.map(lambda i: i + 1)).to_pylist_raw() == [2, 3, 4]


def test_map_typeddict():
    data = arrow.to_weave_arrow([{"a": 1, "b": 2}, {"a": 3, "b": 5}])
    assert weave.use(data.map(lambda row: row["a"])).to_pylist_raw() == [1, 3]


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
    assert weave.use(weave.save(arrow.to_weave_arrow(data))[0]) == data[0]


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
    col_node = arrow.ops.pick(weave_internal.const(data_node), "outer")
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
    data = arrow.to_weave_arrow([Point2(1, 2), Point2(5, 6)])
    assert weave.use(data.map(lambda row: row.get_x())).to_pylist_raw() == [1, 5]


@pytest.mark.skip("not working yet")
def test_map_typeddict_object():
    data = arrow.to_weave_arrow(
        [{"a": 0, "p": Point2(1, 2)}, {"a": 3, "p": Point2(9, 12)}]
    )
    assert weave.use(data.map(lambda row: row["p"])).to_pylist_raw() == []


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

    awl = arrow.to_weave_arrow(list)
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

    list_nodes = make_list(l1=awls[0], l2=awls[1])
    concatenated = arrow.ops.concat(list_nodes)

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
    unnest_node = weave_internal.const(data).unnest()
    assert unnest_node.type == arrow.ArrowWeaveListType(
        types.TypedDict({"a": types.Int(), "b": types.String()})
    )
    assert weave.use(weave_internal.const(data).unnest()).to_pylist_raw() == [
        {"a": 1, "b": "c"},
        {"a": 2, "b": "c"},
        {"a": 3, "b": "c"},
        {"a": 4, "b": "d"},
        {"a": 5, "b": "d"},
        {"a": 6, "b": "d"},
    ]


def test_arrow_unnest_two_list_cols():
    data = arrow.to_arrow(
        [
            {"a": [1, 2, 3], "b": "c", "c": ["a", "b", "c"]},
            {"a": [4, 5, 6], "b": "d", "c": ["d", "e", "f"]},
        ]
    )
    assert weave.type_of(data) == arrow.ArrowWeaveListType(
        types.TypedDict(
            {
                "a": types.List(types.Int()),
                "b": types.String(),
                "c": types.List(types.String()),
            }
        )
    )
    unnest_node = weave_internal.const(data).unnest()
    assert unnest_node.type == arrow.ArrowWeaveListType(
        types.TypedDict({"a": types.Int(), "b": types.String(), "c": types.String()})
    )
    assert weave.use(weave_internal.const(data).unnest()).to_pylist_raw() == [
        {"a": 1, "b": "c", "c": "a"},
        {"a": 2, "b": "c", "c": "b"},
        {"a": 3, "b": "c", "c": "c"},
        {"a": 4, "b": "d", "c": "d"},
        {"a": 5, "b": "d", "c": "e"},
        {"a": 6, "b": "d", "c": "f"},
    ]


def test_arrow_nullable_concat():
    ca1 = pa.chunked_array([[1, 2], [3, 4]])
    ca2 = pa.compute.add(ca1, 1)
    awl1 = arrow.ArrowWeaveList(ca1)
    awl2 = arrow.ArrowWeaveList(ca2)
    list_of_awl = make_list(A=awl1, B=awl2, C=weave.save(None))
    result = list_of_awl.concat()
    assert weave.use(result).to_pylist_raw() == [1, 2, 3, 4, 2, 3, 4, 5]

    # Second pass - forcing none type to be first in member list
    list_of_awl.type = types.List(
        types.union(types.NoneType(), arrow.ArrowWeaveListType(types.Int()))
    )
    result = list_of_awl.concat()
    assert weave.use(result).to_pylist_raw() == [1, 2, 3, 4, 2, 3, 4, 5]


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
    grouped = weave_internal.const(awl).groupby(group_func)
    assert weave.use(grouped[0]).to_pylist_raw() == [{"d": {"a": 1, "b": 2}, "c": 1}]


def test_arrow_weave_list_groupby_struct_chunked_array_type():
    ref = create_arrow_data(1000)

    # chunkedarray is used when there are two levels of nesting
    node = (
        weave.get(ref)
        .groupby(lambda row: ops.dict_(rotate=row["rotate"], shear=row["shear"]))
        .map(lambda row: row.groupby(lambda row: row["y"]))
        .dropna()[0][0]
    )

    assert (
        weave.use(node).to_pylist_raw()
        == [{"rotate": 0, "shear": 0, "x": "a", "y": 5}] * 5
    )


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
    awl = weave.save(arrow.to_weave_arrow([-1, 0, 1, None]))
    weave_func = lambda row: row < 1
    fn = weave_internal.define_fn(
        {"row": awl.type.object_type},
        weave_func,
    )

    called = awl.filter(fn)
    awl = weave.use(called)
    assert awl.to_pylist_notags() == [-1, 0]


def test_grouped_typed_dict_assign():
    assert types.List(types.TypedDict(property_types={})).assign_type(
        arrow.ops.awl_group_by_result_object_type(
            object_type=types.TypedDict(
                property_types={"a": types.Int(), "im": types.Int()}
            ),
            _key=types.TypedDict(property_types={"a": types.String()}),
        )
    )


def test_arrow_index_var():
    data = arrow.to_weave_arrow([1, 2, 3])
    result = data.map(lambda row, index: row + index)
    assert weave.use(result).to_pylist_raw() == [1, 3, 5]


def test_concat_multiple_table_types():
    datal = weave.save(
        arrow.to_weave_arrow([{"prompt": "a"}, {"prompt": None}, {"prompt": "b"}])
    )
    datar = weave.save(
        arrow.to_weave_arrow(
            [
                {"prompt": None, "generation_prompt": "a"},
                {"prompt": "d", "generation_prompt": None},
                {"prompt": "e", "generation_prompt": "f"},
            ]
        )
    )

    to_concat = ops.make_list(l=datal, r=datar)
    result = arrow.ops.concat(to_concat)

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
    result = arrow.ops.concat(to_concat)

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

    assert weave.use(result).to_pylist_raw() == data


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
    result = arrow.ops.concat(to_concat)

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
    result = arrow.ops.concat(to_concat)

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
    result = arrow.ops.concat(to_concat)

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
    result = arrow.ops.concat(to_concat)

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
        # Ensure these two are actually different date times! The timezone is utc in
        # our ci environment, so serializing these results in the same thing if the
        # timestamps match. We use the serialized representation for graph deduplication,
        # meaning we end up with the same node for both of these, which breaks the test
        # (but not the actual behavior of the code).
        datetime.datetime(2020, 1, 2, 3, 4, 6),
        datetime.datetime(2020, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
    ]
    utc_dates = [d.astimezone(datetime.timezone.utc) for d in dates]
    timestamps = [d.timestamp() * 1000 for d in utc_dates]

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

    result = arrow.ops.map_each(node, lambda row: row + 1)
    assert arrow.ArrowWeaveListType(types.List(types.Number())).assign_type(result.type)
    assert weave.use(result).to_pylist_notags() == [[3, 4, 5]] * 3

    # I believe there is a dispatch bug here. If we a regular list instead of awl
    # for node in this test, we'd get the single "top" tag here. The first dispatch
    # rule is "Prefer non-mapped". I think our intention is to return no list ops
    # there, but we don't exclude arrowweavelist ops. So we end up picking
    # the arrowweavelist ops, in the case where we have an arrow weave list input.
    # TODO fix
    assert weave.use(tag_getter_op(result)).to_pylist_notags() == [
        "row0",
        "row1",
        "row2",
    ]
    assert weave.use(tag_getter_op(result[0])) == "row0"
    assert weave.use(tag_getter_op(result[0][0])) == "row0_col0"


def test_unflatten_structs_in_flattened_table():
    flattened_table = pa.table(
        {
            "a➡️b➡️c": [1, 2, 3],
            "a➡️b➡️d": [4, 5, 6],
            "a➡️e": [7, 8, 9],
            "g": ["a", "b", "c"],
        }
    )
    result = arrow.ops.unflatten_structs_in_flattened_table(flattened_table)
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
    assert weave.use(node).to_pylist_raw() == list(range(100))


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

    converted = recursively_encode_pyarrow_strings_as_dictionaries(data)

    # does not raise
    verify_pyarrow_array_type_is_valid_for_tag_array(converted.type)

    data = pa.array([["1"], ["2"], ["3"]])
    # raises
    with pytest.raises(errors.WeaveInternalError):
        verify_pyarrow_array_type_is_valid_for_tag_array(data.type)

    converted = recursively_encode_pyarrow_strings_as_dictionaries(data)

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
        # Empty Lists
        (
            [[{"a": [1]}], [{"a": []}], [{"a": None}]],
            [{"a": [1]}, {"a": []}, {"a": None}],
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
        ).to_pylist_raw()
        == exp_res
    )


def test_complex_concat_union():
    l_0_0 = weave.save(arrow.to_arrow([{"a": [1]}]))
    l_0_1 = weave.save(arrow.to_arrow([{"a": []}]))
    l_0_2 = weave.save(arrow.to_arrow([{"a": None}]))
    l_0 = ops.make_list(a=l_0_0, b=l_0_1, c=l_0_2).concat()["a"]

    # This is intentionally empty!
    l_1_0 = weave.save(arrow.to_arrow([{"a": []}]))
    l_1_1 = weave.save(arrow.to_arrow([{"a": []}]))
    l_1_2 = weave.save(arrow.to_arrow([{"a": None}]))
    l_1 = ops.make_list(a=l_1_0, b=l_1_1, c=l_1_2).concat()["a"]

    l = ops.make_list(a=l_0, b=l_1).concat()

    assert weave.use(l).to_pylist_raw() == [[1], [], None, [], [], None]


def test_abs():
    data = [-10, -2.2, 5, None, 3.3]
    arrow_node = weave.save(arrow.to_arrow(data))
    assert weave.use(arrow_node.abs()).to_pylist_raw() == [10, 2.2, 5, None, 3.3]


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
    from weave.legacy.weave import ops_arrow

    t1 = arrow.to_arrow([{"a": 5, "b": {"c": 6}}])
    t2 = arrow.to_arrow([{"a": 9, "b": {"c": 10}}, {"a": 5, "b": {"c": 11}}])

    tables = weave.save([t1, t2])
    joined = tables.joinAll(lambda row: row["a"], True)

    res = weave.use(joined).to_pylist_raw()
    # TODO: not correct, not because of join, because artifact saving is broken.
    assert res == [
        {"_tag": {"joinObj": 5}, "_value": {"a": [5, 5], "b": [{"c": 6}, {"c": 11}]}},
        {"_tag": {"joinObj": 9}, "_value": {"a": [None, 9], "b": [None, {"c": 10}]}},
    ]


def test_join_all_on_list():
    t1 = arrow.to_arrow([{"a": [5], "b": {"c": 6}}])
    t2 = arrow.to_arrow([{"a": [9], "b": {"c": 10}}, {"a": [5], "b": {"c": 11}}])

    tables = weave.save([t1, t2])
    joined = tables.joinAll(lambda row: row["a"], True)
    res = weave.use(joined).to_pylist_raw()
    # TODO: not correct, not because of join, because artifact saving is broken.
    assert res == [
        {
            "_tag": {"joinObj": [5]},
            "_value": {"a": [[5], [5]], "b": [{"c": 6}, {"c": 11}]},
        },
        {
            "_tag": {"joinObj": [9]},
            "_value": {"a": [None, [9]], "b": [None, {"c": 10}]},
        },
    ]


def test_to_arrow_union_list():
    val = [{"a": 5.0}, {"a": [1.0]}]
    arrow_val = arrow.to_arrow([{"a": 5.0}, {"a": [1.0]}])
    assert arrow_val.to_pylist_raw() == val


def test_concat_empty_arrays():
    val = arrow.to_arrow([])
    val2 = arrow.to_arrow([{"a": 5}])
    assert val.concat(val).to_pylist_raw() == []
    assert val.concat(val2).to_pylist_raw() == val2.to_pylist_raw()
    assert val2.concat(val).to_pylist_raw() == val2.to_pylist_raw()
    assert val2.concat(val2).to_pylist_raw() == [{"a": 5}, {"a": 5}]


_loading_builtins_token = context_state.set_loading_built_ins()


def _test_arrow_do_body(a: int, b: int, c: list[int]) -> int:
    return a * b + a ** c[0]


@weave.op()
def _test_arrow_do_op(a: int, b: int, c: list[int]) -> int:
    if isinstance(a, graph.Node):
        raise errors.WeavifyError("weavifying")
    return _test_arrow_do_body(a, b, c)


context_state.clear_loading_built_ins(_loading_builtins_token)


def test_concat_nulls():
    datal = weave.save(
        arrow.to_arrow([{"prompt": None}, {"prompt": None}, {"prompt": None}])
    )
    datar = weave.save(
        arrow.to_arrow(
            [
                {"prompt": ["a"]},
                {"prompt": ["d"]},
                {"prompt": ["e"]},
            ]
        )
    )

    list_nodes = make_list(l1=datal, l2=datar)
    concatenated = arrow.ops.concat(list_nodes)

    assert weave.use(concatenated.to_py()) == [
        {"prompt": None},
        {"prompt": None},
        {"prompt": None},
        {"prompt": ["a"]},
        {"prompt": ["d"]},
        {"prompt": ["e"]},
    ]


def test_automap_more_than_one():
    data = [1, 2, -5, -100]
    arrow_data = weave.save(arrow.to_arrow(data))

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(x, x, [4]))
    ).to_pylist_raw() == [_test_arrow_do_body(x, x, [4]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(x + 1, x, [4]))
    ).to_pylist_raw() == [_test_arrow_do_body(x + 1, x, [4]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(x + 1, x, ops.make_list(a=x * 2)))
    ).to_pylist_raw() == [_test_arrow_do_body(x + 1, x, [x * 2]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(-1, x, ops.make_list(a=x * 2)))
    ).to_pylist_raw() == [_test_arrow_do_body(-1, x, [x * 2]) for x in data]

    assert weave.use(
        arrow_data.map(lambda x: _test_arrow_do_op(-1, -9, ops.make_list(a=x * 2)))
    ).to_pylist_raw() == [_test_arrow_do_body(-1, -9, [x * 2]) for x in data]


def test_serialization_of_boxed_nones():
    data = [{"a": 1, "b": box.box(None)}, {"a": 2, "b": box.box(None)}]
    arrow_data = weave.save(arrow.to_arrow(data))
    assert weave.use(arrow_data).to_pylist_raw() == data


def test_join_tag_support():
    # tagged<list<tagged<awl<tagged<dict<id: tagged<number>, col: tagged<string>>>>>>>
    cst = weave_internal.const
    tag = ttu.op_add_tag

    def cst_list(data):
        return ops.make_list(**{str(i): l for i, l in enumerate(data)})

    def cst_dict(data):
        return ops.dict_(**data)

    lists_rows = []
    for l_i in range(3):
        list_rows = []
        for r_i in range(4):
            row_key = f"{l_i}_{r_i}"
            # Purposely having id duplicated for purposes of joining
            list_rows.append(
                tag(
                    cst_dict(
                        {
                            "id": tag(
                                cst(f"id_val_{r_i}"), {"id_tag": f"id_{row_key}"}
                            ),
                            "col": tag(
                                cst(f"col_val_{row_key}"), {"col_tag": f"col_{row_key}"}
                            ),
                        }
                    ),
                    {"row_tag": f"row_{row_key}"},
                )
            )
        raw_list = cst_list(list_rows)
        raw_awl = arrow.ops.list_to_arrow(raw_list)
        tagged_awl = tag(raw_awl, {"awl_tag": f"awl_{l_i}"})
        lists_rows.append(tagged_awl)
    raw_lists = cst_list(lists_rows)

    get_id = ttu.make_get_tag("id_tag")
    get_col = ttu.make_get_tag("col_tag")
    get_row = ttu.make_get_tag("row_tag")
    get_awl = ttu.make_get_tag("awl_tag")

    second_list = weave.use(raw_lists[1])
    assert second_list.to_pylist_raw() == [
        {
            "_tag": {"_ct_row_tag": "row_1_0"},
            "_value": {
                "id": {"_tag": {"_ct_id_tag": "id_1_0"}, "_value": "id_val_0"},
                "col": {"_tag": {"_ct_col_tag": "col_1_0"}, "_value": "col_val_1_0"},
            },
        },
        {
            "_tag": {"_ct_row_tag": "row_1_1"},
            "_value": {
                "id": {"_tag": {"_ct_id_tag": "id_1_1"}, "_value": "id_val_1"},
                "col": {"_tag": {"_ct_col_tag": "col_1_1"}, "_value": "col_val_1_1"},
            },
        },
        {
            "_tag": {"_ct_row_tag": "row_1_2"},
            "_value": {
                "id": {"_tag": {"_ct_id_tag": "id_1_2"}, "_value": "id_val_2"},
                "col": {"_tag": {"_ct_col_tag": "col_1_2"}, "_value": "col_val_1_2"},
            },
        },
        {
            "_tag": {"_ct_row_tag": "row_1_3"},
            "_value": {
                "id": {"_tag": {"_ct_id_tag": "id_1_3"}, "_value": "id_val_3"},
                "col": {"_tag": {"_ct_col_tag": "col_1_3"}, "_value": "col_val_1_3"},
            },
        },
    ]

    joined = raw_lists.joinAll(lambda row: row["id"], True)
    joined_row = joined[1]

    assert weave.use(joined_row) == {
        "id": ["id_val_1", "id_val_1", "id_val_1"],
        "col": ["col_val_0_1", "col_val_1_1", "col_val_2_1"],
    }

    joined_row_item = joined_row["col"][1]

    assert (weave.use(joined_row_item)) == "col_val_1_1"
    assert (weave.use(get_col(joined_row_item))) == "col_1_1"
    assert (weave.use(get_row(joined_row_item))) == "row_1_1"
    assert (weave.use(get_awl(joined_row_item))) == "awl_1"

    joined_row_obj = joined_row_item.joinObj()

    assert (weave.use(joined_row_obj)) == "id_val_1"


def test_arrow_handling_of_empty_structs():
    data = [{"a": 5, "b": {}}, {"a": 6, "b": {}}, {"a": 7, "b": None}]
    arrow_data = weave.save(arrow.to_arrow(data))
    assert weave.use(arrow_data.map(lambda x: x["b"])).to_pylist_raw() == [{}, {}, None]
    assert weave.use(arrow_data.map(lambda x: x["a"])).to_pylist_raw() == [5, 6, 7]


def test_count_on_group():
    col = weave.save(arrow.to_arrow([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    col = col.groupby(lambda x: x % 2)
    col = col.map(lambda x: x.count())
    assert weave.use(col).to_pylist_raw() == [
        {"_tag": {"groupKey": 1}, "_value": 5},
        {"_tag": {"groupKey": 0}, "_value": 5},
    ]


def test_limit_on_group():
    col = weave.save(arrow.to_arrow([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    col = col.groupby(lambda x: x % 2)
    col = col.map(lambda x: x.limit(3))
    assert weave.use(col).to_pylist_raw() == [[1, 3, 5], [2, 4, 6]]


def test_offset_on_group():
    col = weave.save(arrow.to_arrow([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    col = col.groupby(lambda x: x % 2)
    col = col.map(lambda x: x.offset(2))
    assert weave.use(col).to_pylist_raw() == [[5, 7, 9], [6, 8, 10]]


def test_map_column():
    arr = arrow.to_arrow(
        [{"a": {"c": 6, "d": 7}, "b": 9}, {"a": {"c": 14, "d": 7}, "b": 5}]
    )

    def _map(awl, path):
        if isinstance(awl.object_type, types.TypedDict):
            # Keep the first element of the dict
            key0, type0 = next(iter(awl.object_type.property_types.items()))
            return arrow.ArrowWeaveList(
                awl._arrow_data.field(key0),
                type0,
                awl._artifact,
            )

    res = arr.map_column(_map)
    # Since this is post-order traversal of the type tree, we should
    # only see the innermost type
    assert res.object_type == types.Int()
    assert res.to_pylist_raw() == [6, 14]


def test_encode_decode_list_of_dictionary_encoded_strings():
    data = [["a", "b", "c"], ["b", "c"], ["a", "b", None], None, ["d"], []]
    awl = arrow.to_arrow(
        data,
        wb_type=types.List(
            types.UnionType(
                types.List(types.UnionType(types.String(), types.NoneType())),
                types.NoneType(),
            )
        ),
    )
    awl._arrow_data = recursively_encode_pyarrow_strings_as_dictionaries(
        awl._arrow_data
    )
    result = awl.to_pylist_raw()
    assert result == data


def test_pushdown_of_gql_tags_on_awls(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: test_wb.workspace_response())
    project_node = ops.project("stacey", "mendeleev")
    project = weave.use(project_node)
    data = box.box([1, 2, 3])
    tag_store.add_tags(data, {"project": project})
    awl = weave.save(arrow.to_arrow(data))

    list_node = arrow.ops.arrow_list_(**{"a": awl, "b": awl})
    concatted = arrow.ops.concat(list_node)

    for i in range(6):
        cell = arrow.ops.index(concatted, i)
        ptag = project_ops.get_project_tag(cell)
        assert weave.use(ptag) == project

    count = concatted.count()
    assert weave.use(count) == 6


def test_groupby_concat():
    # query at issue
    #   some-table().rows().concat()
    #   .groupby(some_function)
    #   .dropna().concat()'  <- note second concat here

    data = [{"time": 1, "model_type": "a"}, {"time": 2, "model_type": "b"}]
    awl_node = weave.save(arrow.to_arrow(data))

    # concat
    list_node = ops.make_list(**{str(i): awl_node for i in range(4)})
    concatted = arrow.ops.concat(list_node)

    # groupby
    grouped = concatted.groupby(lambda x: ops.dict_(**{"time": x["time"]}))

    # dropna
    dropped = grouped.dropna()

    # now concat all the groups together
    concatted_2 = arrow.ops.concat(dropped)
    selected = concatted_2.map(
        lambda row: ops.dict_(time=row.groupkey()["time"], model_type=row["model_type"])
    )

    result = weave.use(selected).to_pylist_notags()
    assert result == ([data[0]] * 4) + ([data[1]] * 4)


def test_conversion_of_domain_types_to_awl_values(fake_wandb):
    fake_wandb.fake_api.add_mock(lambda q, ndx: test_wb.workspace_response())
    project_node = ops.project("stacey", "mendeleev")
    project = weave.use(project_node)
    data = box.box([project] * 3)
    awl = weave.save(arrow.to_arrow(data))

    list_node = arrow.ops.arrow_list_(**{"a": awl, "b": awl})
    assert [[item for item in l] for l in weave.use(list_node)] == [[project] * 2] * 3


def test_non_zero_offset():
    non_zero_offset_array = pa.array([[0, 1], [2, 3], [4, 5]]).slice(1)
    awl = arrow.ArrowWeaveList(non_zero_offset_array)

    # First assertion validates that the test setup is correct:
    assert awl._arrow_data.offsets[0] != 0

    # We just want to validate that this function completes - no assertion
    # needed
    awl.map_column(lambda x, y: None)


def test_object_types_nullable():
    data_node = arrow.to_weave_arrow(
        [
            {"a": 5, "point": Point2(256, 256)},
            {"a": 6, "point": None},
        ]
    )
    assert weave.use(data_node[0]["point"].get_x()) == 256

    assert weave.use(
        data_node.map(lambda row: row["point"].get_x())
    ).to_pylist_raw() == [
        256,
        None,
    ]


def test_save_nested_custom_objs():
    t1 = arrow.to_arrow([{"a": 5}])
    t2 = arrow.to_arrow([{"a": 9}])

    tables = weave.save([t1, t2])
    assert weave.use(tables[0]).to_pylist_raw() == [{"a": 5}]
    assert weave.use(tables[1]).to_pylist_raw() == [{"a": 9}]


def test_to_compare_safe():
    l = [[], "a", 5]
    a = arrow.to_arrow(l)
    safe = arrow.to_compare_safe(a)
    assert safe.to_pylist_notags() == ["__t_13-__list_-", "__t_13-a", "__t_9-5"]


def test_empty_dict():
    data = [{}]
    awl = arrow.to_arrow(data)
    ref = storage.save(awl)
    awl2 = storage.get(str(ref))
    assert len(awl2) == 1
    assert awl._arrow_data == awl2._arrow_data


def test_arrow_op_decorator_handles_optional_tagged_type():
    obj = [None, 1, 2, None]
    obj[1] = box.box(obj[1])
    obj[2] = box.box(obj[2])
    tag_store.add_tags(obj[1], {"mytag": "a"})
    tag_store.add_tags(obj[2], {"mytag": "b"})
    awl = arrow.to_arrow(obj)
    assert awl.object_type == types.optional(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"mytag": types.String()}), types.Int()
        )
    )

    node = weave.save(awl)
    toTimestamp = node.toTimestamp()

    expected = [
        None,
        datetime.datetime(1970, 1, 1, 0, 0, 0, 1000, tzinfo=datetime.timezone.utc),
        datetime.datetime(1970, 1, 1, 0, 0, 0, 2000, tzinfo=datetime.timezone.utc),
        None,
    ]

    expected[1] = box.box(expected[1])
    expected[2] = box.box(expected[2])

    tag_store.add_tags(expected[1], {"mytag": "a"})
    tag_store.add_tags(expected[2], {"mytag": "b"})

    expected = arrow.to_arrow(expected)
    actual = weave.use(toTimestamp)

    assert actual.to_pylist_raw() == expected.to_pylist_raw()


def test_flatten_handles_tagged_lists():
    data = [[1], [2, 3], [4, 5, 6]]
    for i in range(len(data)):
        data[i] = box.box(data[i])
        tag_store.add_tags(data[i], {"outer": "outer"})
        for j in range(len(data[i])):
            data[i][j] = box.box(data[i][j])
            tag_store.add_tags(data[i][j], {"inner": "inner"})

    awl = arrow.to_arrow(data)
    node = weave.save(awl)
    flattened = node.flatten()

    assert flattened.type == arrow.ArrowWeaveListType(
        tagged_value_type.TaggedValueType(
            types.TypedDict({"outer": types.String(), "inner": types.String()}),
            types.Int(),
        )
    )

    expected = [1, 2, 3, 4, 5, 6]
    assert weave.use(flattened).to_pylist_notags() == expected
    assert weave.use(flattened).to_pylist_raw() == [
        {
            "_tag": {
                "outer": "outer",
                "inner": "inner",
            },
            "_value": i,
        }
        for i in expected
    ]


def test_keys_ops():
    awl = arrow.to_arrow([{"a": 1}, {"a": 1, "b": 2, "c": 2}, {"c": 3}])
    node = weave.save(awl)
    keys_node = node.keys()
    # Unfortunately, we lose specific info about key presence in AWL.
    assert weave.use(keys_node).to_pylist_raw() == [
        ["a", "b", "c"],
        ["a", "b", "c"],
        ["a", "b", "c"],
    ]

    all_keys_node = keys_node.flatten().unique()

    assert weave.use(all_keys_node).to_pylist_raw() == ["a", "b", "c"]


def test_repeat_0():
    data = {"a": 1}
    repeated = constructors.repeat(data, 0)
    assert len(repeated) == 0
    assert repeated.type == pa.struct({"a": pa.int64()})
