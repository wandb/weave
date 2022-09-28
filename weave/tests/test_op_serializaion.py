import pytest
import weave
from .. import op_args
from .. import types

ops = weave.registry_mem.memory_registry.list_ops()


@pytest.mark.parametrize("op_name, op", [(op.name, op) for op in ops])
def test_explicit_experiment_construction(op_name, op):
    # Just make sure that this is successful
    assert op.to_dict() is not None
