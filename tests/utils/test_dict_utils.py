import pytest

from weave.utils.dict_utils import sum_dict_leaves


@pytest.mark.parametrize(
    ("dicts", "expected"),
    [
        # Numbers summed, strings collected into a list.
        (
            [
                {"a": 1, "b": "hello", "c": 2},
                {"a": 3, "b": "world", "c": 4},
                {"a": 5, "b": "!", "c": 6},
            ],
            {"a": 9, "b": ["hello", "world", "!"], "c": 12},
        ),
        # Nested dicts summed leaf-wise.
        (
            [
                {"a": {"x": 1, "y": 2}, "b": 3},
                {"a": {"x": 4, "y": 5}, "b": 6},
                {"a": {"x": 7, "y": 8}, "b": 9},
            ],
            {"a": {"x": 12, "y": 15}, "b": 18},
        ),
        # Empty input and empty member dicts.
        ([], {}),
        ([{}], {}),
        # None values are dropped.
        (
            [
                {"a": 1, "b": None, "c": 2},
                {"a": 3, "b": None, "c": 4},
                {"a": 5, "b": None, "c": 6},
            ],
            {"a": 9, "c": 12},
        ),
        # Mixed types per key collected into a list.
        (
            [
                {"a": 1, "b": "hello", "c": 2},
                {"a": "world", "b": 3, "c": 4},
                {"a": 5, "b": "!", "c": "test"},
            ],
            {
                "a": [1, "world", 5],
                "b": ["hello", 3, "!"],
                "c": [2, 4, "test"],
            },
        ),
        # Nested dicts with mixed types.
        (
            [
                {"a": {"x": 1, "y": "hello"}, "b": 3},
                {"a": {"x": "world", "y": 2}, "b": "test"},
                {"a": {"x": 5, "y": 3}, "b": 6},
            ],
            {
                "a": {"x": [1, "world", 5], "y": ["hello", 2, 3]},
                "b": [3, "test", 6],
            },
        ),
        # Deeply nested (2 levels) with mixed types.
        (
            [
                {
                    "level1": {
                        "level2": {"a": 1, "b": "hello", "c": {"x": 2, "y": "world"}}
                    },
                    "top": 10,
                },
                {
                    "level1": {
                        "level2": {"a": "test", "b": 3, "c": {"x": "deep", "y": 4}}
                    },
                    "top": "mixed",
                },
                {
                    "level1": {
                        "level2": {"a": 5, "b": "!", "c": {"x": 6, "y": "nested"}}
                    },
                    "top": 20,
                },
            ],
            {
                "level1": {
                    "level2": {
                        "a": [1, "test", 5],
                        "b": ["hello", 3, "!"],
                        "c": {"x": [2, "deep", 6], "y": ["world", 4, "nested"]},
                    }
                },
                "top": [10, "mixed", 20],
            },
        ),
    ],
)
def test_sum_dict_leaves(dicts, expected):
    """sum_dict_leaves: sum numbers, collect strings/mixed into lists, drop None, recurse."""
    assert sum_dict_leaves(dicts) == expected
