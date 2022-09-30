from .. import derive_op
from .. import api as weave
from .. import registry_mem
from .. import derive_op


def test_mapped_add():
    op = registry_mem.memory_registry.get_op("number-add")
    mapped_add = derive_op.MappedDeriveOpHandler.make_derived_op(op)
    assert weave.use(mapped_add([3, 4, 5], 9)) == [12, 13, 14]
