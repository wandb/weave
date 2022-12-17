import typing
import pytest
from .. import api as weave
from ..ops_arrow import list_ as arrow
from ..ops_primitives import list_, dict_


def filter_fn(row) -> bool:
    return row < 3


def optional_filter_fn(row) -> bool:
    return row < 3


def inv_filter_fn(row) -> bool:
    return row < -3


# TODO: Test Tag management
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
        # Filter on Nones
        ([1, None, 2, None, 3, None, 4], "filter", optional_filter_fn, [1, 2], []),
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
