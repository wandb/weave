from ... import api as weave
from ... import registry_mem


def test_mapped_add():
    mapped_add = registry_mem.memory_registry.get_op("mapped_number-add")
    assert weave.use(mapped_add([3, 4, 5], 9)) == [12, 13, 14]
