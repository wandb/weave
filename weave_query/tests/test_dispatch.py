import pytest

import weave_query as weave
import weave_query
from weave_query import ops_arrow


def test_dispatch_lambda():
    l = weave.save([1, 2, 3])
    filtered = l.filter(lambda x: x > 1)
    assert weave.use(filtered) == [2, 3]

    l = ops_arrow.to_weave_arrow([1, 2, 3])
    filtered = l.filter(lambda x: x > 1)
    assert weave.use(filtered).to_pylist_raw() == [2, 3]
