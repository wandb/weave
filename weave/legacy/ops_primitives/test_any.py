import typing

import pytest

from weave import api as weave
from weave.legacy import box
from weave.legacy.ops_primitives import any

cases: list[typing.Tuple[typing.Any, bool]] = [
    (1, False),
    (None, True),
    ([], False),
    (box.box(None), True),
    ([1, 2, 3], False),
]


@pytest.mark.parametrize(["input", "expected_output"], cases)
def test_isnone(input, expected_output):
    node = any.is_none(input)
    assert weave.use(node) == expected_output
