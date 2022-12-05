import numpy as np
from .. import types_numpy as numpy_types
from .. import weave_types as types


def test_construct_numpy_type():
    target_type = {
        "type": "ndarray",
        "serializationPath": {
            "key": "some_key",
            "path": "a/b/c.npz",
        },
        "shape": [],
    }
    # should not raise
    t = numpy_types.NumpyArrayType.from_dict(target_type)

    # the following array should be assignable to t
    arr = np.array(1)
    t_inferred = types.TypeRegistry.type_of(arr)
    assert t_inferred.assign_type(t)
