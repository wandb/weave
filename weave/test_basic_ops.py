from . import api as weave
from . import ops

from .weave_internal import make_const_node


def test_number_ops():
    nine = make_const_node(weave.types.Number(), 9)
    assert weave.use(nine + 3) == 12
    assert weave.use(nine - 3) == 6
    assert weave.use(nine * 3) == 27
    assert weave.use(nine / 2) == 4.5
    assert weave.use(nine == 8) == False
    assert weave.use(nine == 9) == True
    assert weave.use(nine != 8) == True
    assert weave.use(nine != 9) == False
    assert weave.use(nine > 8) == True
    assert weave.use(nine > 9) == False
    assert weave.use(nine < 10) == True
    assert weave.use(nine < 9) == False
    assert weave.use(nine >= 8) == True
    assert weave.use(nine >= 9) == True
    assert weave.use(nine <= 10) == True
    assert weave.use(nine <= 9) == True
