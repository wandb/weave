from . import derive_op
from . import api as weave


def test_mapped_add():
    mapped_add = derive_op.make_mapped_op("number-add")
    assert weave.use(mapped_add([3, 4, 5], 9)) == [12, 13, 14]
