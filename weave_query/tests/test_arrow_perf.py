# These are performance tests. If they start to flake we can come up
# with a better way to run them.
import time

import pytest

import weave
from weave.legacy.weave import ops_arrow, ops_primitives


@pytest.mark.skip(reason="Performance test")
def test_listmap():
    range_data = list(range(20000))
    pydata = [{"a": i, "b": i, "c": i} for i in range_data]
    data = ops_arrow.to_weave_arrow(pydata)
    node = ops_primitives.List._listmap(data, lambda x: x["a"] + 1)
    expected = [x + 1 for x in range_data]
    start_time = time.time()
    assert weave.use(node) == expected
    elapsed = time.time() - start_time
    # Runs in 0.9s on my m1 macbook pro
    assert elapsed < 2.5
