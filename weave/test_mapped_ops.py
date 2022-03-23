from . import api as weave
from . import ops
from . import weave_internal


def test_mapped_add():
    mapped_add = weave_internal.make_mapped_op("number-add")
    assert weave.use(mapped_add([3, 4, 5], 9)) == [12, 13, 14]
