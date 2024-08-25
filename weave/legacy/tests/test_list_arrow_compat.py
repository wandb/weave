import itertools

import numpy as np
import pytest

from weave.legacy.weave import api as weave
from weave.legacy.weave import box, ops, weave_internal
from weave.legacy.weave import ops_arrow as arrow
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.language_features.tagging import (
    make_tag_getter_op,
    tag_store,
    tagged_value_type,
)
from weave.legacy.weave.ops_primitives import dict_, list_

from weave.legacy.tests.util import tag_test_util as ttu
from weave.legacy.tests.util import list_arrow_test_helpers as lath


def filter_fn(row) -> bool:
    return row < 3


def inv_filter_fn(row) -> bool:
    return row < -3


# TODO: Test Tag managmenet
@pytest.mark.parametrize(
    "data, fn_name, fn_def, res, extra_args",
    [
        ([1, 2, 3, 4], "map", lambda row: row + 1, [2, 3, 4, 5], []),
        (
            [1, 2, 3, 4],
            "map",
            lambda row: list_.make_list(a=row + 1, b=row * -1),
            [[2, -1], [3, -2], [4, -3], [5, -4]],
            [],
        ),
        (
            [1, 2, 3, 4],
            "map",
            lambda row: dict_(a=row + 1, b=row * -1),
            [
                {"a": 2, "b": -1},
                {"a": 3, "b": -2},
                {"a": 4, "b": -3},
                {"a": 5, "b": -4},
            ],
            [],
        ),
        ([1, 2, 3, 4], "filter", filter_fn, [1, 2], []),
        ([1, None, 2, None, 3, None, 4], "filter", filter_fn, [1, 2], []),
        ([1, 2, 3, 4], "filter", inv_filter_fn, [], []),
        (
            [1, 2, 3, 4],
            "sort",
            lambda row: list_.make_list(a=row * -1),
            [4, 3, 2, 1],
            [["asc"]],
        ),
        (
            [1, 2, 3, 4],
            "sort",
            lambda row: list_.make_list(a=row * -1),
            [1, 2, 3, 4],
            [["desc"]],
        ),
        (
            [1, 2, 3, 4],
            "sort",
            lambda row: list_.make_list(a=row * 0, b=row * -2),
            [4, 3, 2, 1],
            [["asc", "asc"]],
        ),
        (
            [1, 2, 3, 4],
            "sort",
            lambda row: list_.make_list(a=row * 0, b=row * -2),
            [1, 2, 3, 4],
            [["asc", "desc"]],
        ),
        # ([1,2,3,4], "map", lambda row: row + 1, [2,3,4,5]),
        (
            [1, 2, 3, 4, None],
            "sort",
            lambda row: list_.make_list(
                a=row * 0 if row is not None else None,
                b=row * -2 if row is not None else None,
            ),
            [None, 1, 2, 3, 4],
            [["asc", "desc"]],
        ),
        (
            [1, 2, 3, 4, None],
            "sort",
            lambda row: list_.make_list(
                a=row * 0 if row is not None else None,
                b=row * -2 if row is not None else None,
            ),
            [None, 4, 3, 2, 1],
            [["asc", "asc"]],
        ),
        (
            [1, 2, 3, 4, None],
            "sort",
            lambda row: list_.make_list(
                a=row * 0 if row is not None else None,
                b=row * -2 if row is not None else None,
            ),
            [4, 3, 2, 1, None],
            [["desc", "asc"]],
        ),
        (
            [1, 2, 3, 4, None],
            "sort",
            lambda row: list_.make_list(a="a", b=row),
            [None, 1, 2, 3, 4],
            [["asc", "asc"]],
        ),
        (
            [[None, 1], [None, 2], [None, 3]],
            "sort",
            lambda row: list_.make_list(a=row[0], b=row[1]),
            [[None, 1], [None, 2], [None, 3]],
            [["asc", "asc"]],
        ),
        (
            [1, "a", None, 2.0, {"a": 1}],
            "sort",
            lambda row: list_.make_list(a=row),
            [None, 1, 2.0, "a", {"a": 1}],
            [["asc"]],
        ),
        (
            [{"a": 1}, {"a": 2}, {"a": 3}, {"a": None}],
            "sort",
            lambda row: list_.make_list(a=row["a"]),
            list(
                reversed(
                    [
                        {"a": None},
                        {"a": 1},
                        {"a": 2},
                        {"a": 3},
                    ]
                )
            ),
            [["desc"]],
        ),
    ],
)
def test_list_arrow_compatibility(data, fn_name, fn_def, res, extra_args):
    test_list_arrow_fn_results_maybe_incompatible(
        data, fn_name, fn_def, res, res, extra_args
    )


@pytest.mark.parametrize(
    "data, fn_name, fn_def, list_res, arrow_res, extra_args",
    [
        (
            [{"a": 1}, {"a": 2}, {"a": 3}, {"a": None}],
            "sort",
            lambda row: list_.make_list(a=row),
            [{"a": 1}, {"a": 2}, {"a": 3}, {"a": None}],
            [
                {"a": None},
                {"a": 1},
                {"a": 2},
                {"a": 3},
            ],
            [["asc"]],
        )
    ],
)
def test_list_arrow_fn_results_maybe_incompatible(
    data, fn_name, fn_def, list_res, arrow_res, extra_args
):
    list_node = list_.make_list(**{f"{i}": v for i, v in enumerate(data)})
    arrow_node = weave.save(arrow.to_arrow(data))

    list_node_mapped = list_node.__getattr__(fn_name)(fn_def, *extra_args)
    arrow_node_mapped = arrow_node.__getattr__(fn_name)(fn_def, *extra_args)

    assert weave.use(list_node_mapped) == list_res
    assert weave.use(arrow_node_mapped).to_pylist_raw() == arrow_res


# TODO: In Weave0, we also have a `join2` op. This will be done in a followup
# PR.
def compare_join_results(results, exp_results):
    # Currently list join and arrow join return slightly different result
    # orderings. PyArrow's join pushes all outer join results without a match to
    # the end of the list, while list join returns the order found. For purposes
    # of Weave1 development, we will ignore this difference. It would be
    # unnecessarily costly to resort the results of either join to match the
    # other.
    error_msg = f"Expected {exp_results}, got {results}"
    assert len(results) == len(exp_results), f"Result length is wrong; {error_msg}"
    for exp_result in exp_results:
        assert (
            exp_result in results
        ), f"Expected result {exp_result} not found; {error_msg}"
    for result in results:
        assert (
            result in exp_results
        ), f"unexpected result {exp_result} found; {error_msg}"


@pytest.mark.parametrize("li", lath.ListInterfaces)
def test_join_all(li):
    # This test tests joining a nullable list of lists, with duplicate keys that are partially overlapping and not all entries have the key! (our join logic is quite nuanced.)
    list_node_1 = li.make_node(
        [
            {
                "id": "1.0",
            },
            {
                "id": "1.a",
                "val": 1,
            },
            {
                "id": "1.b",
                "val": 1,
            },
            {
                "id": "1.c",
                "val": 2,
            },
            {
                "id": "1.d",
                "val": 2,
            },
            {
                "id": "1.e",
                "val": 3,
            },
        ]
    )
    list_node_2 = li.make_node(
        [
            {
                "id": "2.0",
            },
            {
                "id": "2.f",
                "val": 1,
            },
            {
                "id": "2.g",
                "val": 1,
            },
            {
                "id": "2.h",
                "val": 3,
            },
            {
                "id": "2.i",
                "val": 3,
            },
            {
                "id": "2.j",
                "val": 5,
            },
        ]
    )
    join_list = list_.make_list(a=list_node_1, c=None, b=list_node_2)
    join_fn = weave_internal.define_fn(
        {"row": list_node_1.type.object_type},
        lambda row: row["val"],
    )

    joined_inner_node = join_list.joinAll(join_fn, False)
    joined_outer_node = join_list.joinAll(join_fn, True)

    # TODO: Arrow and List have different permutation ordering here - probably fix list implementation to match arrow
    exp_results = [
        {
            "val": [1, 1],
            "id": ["1.a", "2.f"],
        },
        {
            "val": [1, 1],
            "id": ["1.a", "2.g"],
        },
        {
            "val": [1, 1],
            "id": ["1.b", "2.f"],
        },
        {
            "val": [1, 1],
            "id": ["1.b", "2.g"],
        },
        {
            "val": [3, 3],
            "id": ["1.e", "2.i"],
        },
        {
            "val": [3, 3],
            "id": ["1.e", "2.h"],
        },
    ]
    compare_join_results(li.use_node(joined_inner_node), exp_results)

    exp_results = [
        {
            "val": [1, 1],
            "id": ["1.a", "2.f"],
        },
        {
            "val": [1, 1],
            "id": ["1.b", "2.f"],
        },
        {
            "val": [1, 1],
            "id": ["1.a", "2.g"],
        },
        {
            "val": [1, 1],
            "id": ["1.b", "2.g"],
        },
        {
            "val": [2, None],
            "id": ["1.c", None],
        },
        {
            "val": [2, None],
            "id": ["1.d", None],
        },
        {
            "val": [3, 3],
            "id": ["1.e", "2.h"],
        },
        {
            "val": [3, 3],
            "id": ["1.e", "2.i"],
        },
        {
            "val": [None, 5],
            "id": [None, "2.j"],
        },
    ]

    compare_join_results(li.use_node(joined_outer_node), exp_results)
    # Currently list join and arrow join return slightly different result
    # orderings. DuckDB's join order is not obvious, while
    # list join returns the order found. For purposes
    # of Weave1 development, we will ignore this difference. It would be
    # unnecessarily costly to resort the results of either join to match the
    # other.
    if li == lath.ListNode:
        tag_order = [1, 1, 1, 1, 2, 2, 3, 3, 5]
    elif li == lath.ArrowNode:
        tag_order = [1, 1, 1, 1, 3, 3, 2, 2, 5]
    assert li.use_node(joined_outer_node.joinObj()) == tag_order


@pytest.mark.parametrize("li", lath.ListInterfaces)
def test_join_2(li):
    # This test tests joining a nullable list of lists, with duplicate keys that are partially overlapping and not all entries have the key! (our join logic is quite nuanced.)
    list_node_1 = li.make_node(
        [
            {
                "id": "1.0",
            },
            {
                "id": "1.a",
                "val": 1,
            },
            {
                "id": "1.b",
                "val": 1,
            },
            {
                "id": "1.c",
                "val": 2,
            },
            {
                "id": "1.d",
                "val": 2,
            },
            {
                "id": "1.e",
                "val": 3,
            },
        ]
    )
    list_node_2 = li.make_node(
        [
            {
                "id": "2.0",
            },
            {
                "id": "2.f",
                "val": 1,
            },
            {
                "id": "2.g",
                "val": 1,
            },
            {
                "id": "2.h",
                "val": 3,
            },
            {
                "id": "2.i",
                "val": 3,
            },
            {
                "id": "2.j",
                "val": 5,
            },
        ]
    )
    # join_list = list_.make_list(a=list_node_1, c=None, b=list_node_2)
    join_fn = weave_internal.define_fn(
        {"row": list_node_1.type.object_type},
        lambda row: row["val"],
    )

    joined_inner_node = list_node_1.join(
        list_node_2, join_fn, join_fn, "a0", "a1", False, False
    )
    joined_left_outer_node = list_node_1.join(
        list_node_2, join_fn, join_fn, "a0", "a1", True, False
    )
    joined_right_outer_node = list_node_1.join(
        list_node_2, join_fn, join_fn, "a0", "a1", False, True
    )
    joined_full_outer_node = list_node_1.join(
        list_node_2, join_fn, join_fn, "a0", "a1", True, True
    )

    # TODO: Arrow and List have different permutation ordering here - probably fix list implementation to match arrow
    exp_results = [
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.i", "val": 3}},
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.h", "val": 3}},
    ]
    compare_join_results(li.use_node(joined_inner_node), exp_results)

    exp_results = [
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.i", "val": 3}},
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.h", "val": 3}},
        {"a0": {"id": "1.c", "val": 2}, "a1": None},
        {"a0": {"id": "1.d", "val": 2}, "a1": None},
    ]
    compare_join_results(li.use_node(joined_left_outer_node), exp_results)

    exp_results = [
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.h", "val": 3}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.i", "val": 3}},
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": None, "a1": {"id": "2.j", "val": 5}},
    ]
    compare_join_results(li.use_node(joined_right_outer_node), exp_results)

    exp_results = [
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.g", "val": 1}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.i", "val": 3}},
        {"a0": {"id": "1.a", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.b", "val": 1}, "a1": {"id": "2.f", "val": 1}},
        {"a0": {"id": "1.e", "val": 3}, "a1": {"id": "2.h", "val": 3}},
        {"a0": {"id": "1.c", "val": 2}, "a1": None},
        {"a0": {"id": "1.d", "val": 2}, "a1": None},
        {"a0": None, "a1": {"id": "2.j", "val": 5}},
    ]
    compare_join_results(li.use_node(joined_full_outer_node), exp_results)

    # Currently list join and arrow join return slightly different result
    # orderings. DuckDB's join order is not obvious, while
    # list join returns the order found. For purposes
    # of Weave1 development, we will ignore this difference. It would be
    # unnecessarily costly to resort the results of either join to match the
    # other.
    if li == lath.ListNode:
        tag_order = [1, 1, 1, 1, 2, 2, 3, 3, 5]
    elif li == lath.ArrowNode:
        tag_order = [1, 1, 1, 1, 3, 3, 2, 2, 5]
    assert li.use_node(joined_full_outer_node.joinObj()) == tag_order


algos = [
    ("pca", {}),
    ("tsne", {"perplexity": 2, "learning_rate": 10, "iterations": 3}),
    ("umap", {"neighbors": 2, "min_dist": 0.1, "spread": 1.0}),
]


@pytest.mark.timeout(60)
@pytest.mark.parametrize(
    "li, algo, options",
    [
        (li, algo_options[0], algo_options[1])
        for li in lath.ListInterfaces
        for algo_options in algos
    ],
)
def test_2d_projection(li, algo, options):
    n_rows = 15
    n_cols = 6
    data = np.random.rand(n_rows, n_cols)
    data_as_dicts = [
        {f"col_{item_ndx}": item for item_ndx, item in enumerate(row)} for row in data
    ]
    col_names = [f"col_{item_ndx}" for item_ndx in range(n_cols)]
    node = li.make_node(data_as_dicts)
    projection = node._get_op("2DProjection")(algo, "many", col_names, options)
    res = li.use_node(projection)
    assert len(res) == n_rows
    assert res[0].get("projection").get("x") is not None
    assert res[0].get("projection").get("y") is not None
    assert res[0].get("source") == data_as_dicts[0]


def test_join_to_str():
    data = ["1", None, "2", None, "3"]
    res = "1,,2,,3"  # note, Weave0 uses "" for Nones - we may consider changing this in the future
    list_node = lath.ListNode.make_node(data)
    arrow_node = lath.ArrowNode.make_node([data, data])

    list_joined = list_node.joinToStr(",")
    arrow_joined = arrow_node.joinToStr(",")

    assert lath.ListNode.use_node(list_joined) == res
    assert lath.ArrowNode.use_node(arrow_joined) == [res, res]


@pytest.mark.parametrize(
    "use_arrow",
    [True, False],
)
def test_flatten_and_tags(use_arrow):
    # tagged<list<tagged<awl<tagged<dict<id: tagged<number>, col: tagged<string>>>>>>>
    cst = weave_internal.const
    tag = ttu.op_add_tag
    item_tag_getter = ttu.make_get_tag("item_tag")
    list_tag_getter = ttu.make_get_tag("list_tag")

    def cst_list(data):
        return ops.make_list(**{str(i): l for i, l in enumerate(data)})

    def cst_arrow(data):
        return arrow.ops.list_to_arrow(cst_list(data))

    if use_arrow:
        inner_list_fn = cst_arrow
    else:
        inner_list_fn = cst_list

    list_of_lists = cst_list(
        [
            tag(
                inner_list_fn(
                    [
                        tag(cst("item_1_1"), {"item_tag": "1_1"}),
                        tag(cst("item_1_2"), {"item_tag": "1_2"}),
                        tag(cst("item_1_3"), {"item_tag": "1_3"}),
                    ]
                ),
                {"list_tag": "1"},
            ),
            tag(
                inner_list_fn(
                    [
                        tag(cst("item_2_1"), {"item_tag": "2_1"}),
                        tag(cst("item_2_2"), {"item_tag": "2_2"}),
                        tag(cst("item_2_3"), {"item_tag": "2_3"}),
                    ]
                ),
                {"list_tag": "2"},
            ),
            tag(
                inner_list_fn(
                    [
                        tag(cst("item_3_1"), {"item_tag": "3_1"}),
                        tag(cst("item_3_2"), {"item_tag": "3_2"}),
                        tag(cst("item_3_3"), {"item_tag": "3_3"}),
                    ]
                ),
                {"list_tag": "3"},
            ),
        ]
    )

    flattened = list_of_lists.flatten()

    data_res = weave.use(flattened)
    item_tag_res = weave.use(item_tag_getter(flattened[0]))
    list_tag_res = weave.use(list_tag_getter(flattened[0]))

    if use_arrow:
        data_res = data_res.to_pylist_notags()

    assert data_res == [
        "item_1_1",
        "item_1_2",
        "item_1_3",
        "item_2_1",
        "item_2_2",
        "item_2_3",
        "item_3_1",
        "item_3_2",
        "item_3_3",
    ]
    assert item_tag_res == "1_1"
    assert list_tag_res == "1"


@pytest.mark.parametrize(
    "use_arrow",
    [True, False],
)
def test_tag_pushdown_on_list_of_lists(use_arrow):
    data = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    for i, row in enumerate(data):
        for j, item in enumerate(row):
            data[i][j] = tag_store.add_tags(box.box(item), {"row": i, "col": j})
        data[i] = tag_store.add_tags(box.box(data[i]), {"list_tag": i})
    data = tag_store.add_tags(box.box(data), {"top_tag": 2})
    list_node = weave.save(data)

    if use_arrow:
        list_node = arrow.ops.list_to_arrow(list_node)

    from weave.legacy.weave import context_state

    _loading_builtins_token = context_state.set_loading_built_ins()

    row_tag_getter = make_tag_getter_op.make_tag_getter_op("row", types.Int())
    col_tag_getter = make_tag_getter_op.make_tag_getter_op("col", types.Int())
    list_tag_getter = make_tag_getter_op.make_tag_getter_op("list_tag", types.Int())
    top_tag_getter = make_tag_getter_op.make_tag_getter_op("top_tag", types.Int())

    context_state.clear_loading_built_ins(_loading_builtins_token)

    inner_func = (
        lambda n: n
        + row_tag_getter(n)
        + col_tag_getter(n)
        + list_tag_getter(n)
        - top_tag_getter(n)
        + 3
    )

    outer_func = lambda row: row.map(inner_func)
    mapped = list_node.map(outer_func)

    assert mapped.type == tagged_value_type.TaggedValueType(
        types.TypedDict({"top_tag": types.Int()}),
        (types.List if not use_arrow else arrow.ArrowWeaveListType)(
            tagged_value_type.TaggedValueType(
                types.TypedDict({"list_tag": types.Int(), "top_tag": types.Int()}),
                types.List(
                    tagged_value_type.TaggedValueType(
                        types.TypedDict(
                            {
                                "row": types.Int(),
                                "col": types.Int(),
                                "top_tag": types.Int(),
                                "list_tag": types.Int(),
                            }
                        ),
                        types.Number(),
                    )
                ),
            )
        ),
    )

    output = weave.use(mapped)

    if use_arrow:
        output = output.to_pylist_tagged()

    assert output == [
        [data[i][j] + 3 + i + j - 2 + i for j in range(3)] for i in range(3)
    ]


@pytest.mark.parametrize(
    "use_arrow",
    [True, False],
)
def test_sample(use_arrow):
    input_array = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    if use_arrow:
        input_array_node = weave.save(arrow.to_arrow(input_array))
        sample_node = input_array_node.randomlyDownsample(5)
    else:
        sample_node = list_.sample(input_array, 5)
    result = weave.use(sample_node)

    if use_arrow:
        result = result.to_pylist_tagged()

    assert len(result) == 5
    assert len(set(result)) == 5
    assert set(result).issubset(set(input_array))
    assert sorted(result) == result


@pytest.mark.parametrize(
    "use_arrow",
    [True, False],
)
def test_sample_10(use_arrow):
    input_array = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    if use_arrow:
        input_array_node = weave.save(arrow.to_arrow(input_array))
        sample_node_10 = input_array_node.randomlyDownsample(10)
    else:
        sample_node_10 = list_.sample(input_array, 10)
    result_10 = weave.use(sample_node_10)

    if use_arrow:
        result_10 = result_10.to_pylist_tagged()

    assert result_10 == input_array


@pytest.mark.parametrize(
    "use_arrow",
    [True, False],
)
def test_sample_bad(use_arrow):
    input_array = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    if use_arrow:
        input_array_node = weave.save(arrow.to_arrow(input_array))
        bad_node = input_array_node.randomlyDownsample(-1)
    else:
        bad_node = list_.sample(input_array, -1)

    with pytest.raises(ValueError):
        weave.use(bad_node)


@pytest.mark.parametrize(
    "use_arrow, input_array",
    list(itertools.product([True, False], [[], list(range(10))])),
)
def test_sample_length_zero_list(use_arrow, input_array):
    input_array = []
    if use_arrow:
        input_array_node = weave.save(arrow.to_arrow(input_array))
        bad_node = input_array_node.randomlyDownsample(0)
    else:
        bad_node = list_.sample(input_array, 0)

    result = weave.use(bad_node)

    if use_arrow:
        result = result.to_pylist_tagged()

    assert result == []
