import pytest

import weave_query as weave
import weave_query


def test_number_bin_vector():
    awl = weave_query.ops.to_weave_arrow([1, 2, 3, 4, 5])
    mapped = awl.map(lambda x: x.bin(weave_query.ops.number_bins_fixed(2)))
    res = weave.use(mapped).to_pylist_tagged()
    assert res == [
        {"start": 0.0, "stop": 2.0},
        {"start": 2.0, "stop": 4.0},
        {"start": 2.0, "stop": 4.0},
        {"start": 4.0, "stop": 6.0},
        {"start": 4.0, "stop": 6.0},
    ]
