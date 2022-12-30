from .. import api as weave
from .. import box
from . import any

import pytest
import typing


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
