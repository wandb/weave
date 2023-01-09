import pytest
from .. import api as weave
from ..ops_arrow import list_ as arrow
from ..ops_primitives import list_, dict_
from . import list_arrow_test_helpers as lath
import numpy as np
import pytest


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
    ],
)
def test_fn_equality(data, fn_name, fn_def, res, extra_args):
    list_node = list_.make_list(**{f"{i}": v for i, v in enumerate(data)})
    arrow_node = weave.save(arrow.to_arrow(data))

    list_node_mapped = list_node.__getattr__(fn_name)(fn_def, *extra_args)
    arrow_node_mapped = arrow_node.__getattr__(fn_name)(fn_def, *extra_args)

    assert weave.use(list_node_mapped) == res
    assert weave.use(arrow_node_mapped).to_pylist() == res


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
    join_fn = weave.define_fn(
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
    # orderings. PyArrow's join pushes all outer join results without a match to
    # the end of the list, while list join returns the order found. For purposes
    # of Weave1 development, we will ignore this difference. It would be
    # unnecessarily costly to resort the results of either join to match the
    # other.
    if li == lath.ListNode:
        tag_order = [1, 1, 1, 1, 2, 2, 3, 3, 5]
    elif li == lath.ArrowNode:
        tag_order = [1, 1, 1, 1, 3, 3, 2, 2, 5]
    assert li.use_node(joined_outer_node.joinObj()) == tag_order


algos = [
    ("pca", {}),
    ("tsne", {"perplexity": 20, "learning_rate": 100, "iterations": 10}),
    ("umap", {"neighbors": 10, "min_dist": 0.1, "spread": 1.0}),
]


@pytest.mark.parametrize(
    "li, algo, options",
    [
        (li, algo_options[0], algo_options[1])
        for li in lath.ListInterfaces
        for algo_options in algos
    ],
)
def test_2d_projection(li, algo, options):
    n_rows = 100
    n_cols = 100
    data = np.random.rand(n_rows, n_cols)
    data_as_dicts = [
        {f"col_{item_ndx}": item for item_ndx, item in enumerate(row)} for row in data
    ]
    col_names = [f"col_{item_ndx}" for item_ndx in range(n_cols)]
    node = li.make_node(data_as_dicts)
    projection = node._get_op("2DProjection")(algo, "many", col_names, options)
    res = weave.use(projection)
    assert len(res) == n_rows
    assert res[0].get("projection").get("x") is not None
    assert res[0].get("projection").get("y") is not None
    assert res[0].get("source") == data_as_dicts[0]
