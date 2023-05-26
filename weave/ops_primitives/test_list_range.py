import pytest
import weave


def test_range():
    assert weave.use(weave.ops.range(0, 3, 1)) == [0, 1, 2]
