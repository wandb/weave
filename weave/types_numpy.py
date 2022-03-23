import numpy as np
from . import weave_types as types


class NumpyArrayRef:
    def __init__(self, path, index):
        self.path = path
        self.index = index


class NumpyArrayRefType(types.ObjectType):
    name = "numpyarrayref"
    instance_classes = NumpyArrayRef
    instance_class = NumpyArrayRef

    type_vars = {
        # This is not NumpyArrayType!
        #   its Type<NumpyArrayType> Or something like that
        # Have recursion here with result_type, need to fix
        # 'result_type': Type(),
        "path": types.String(),
    }

    def __init__(self, path):
        # self.result_type = result_type
        self.path = path

    def property_types(self):
        return {
            # 'result_type': self.result_type,
            "path": self.path,
            "index": types.Number(),
        }


class NumpyArrayType(types.Type):
    instance_classes = np.ndarray
    name = "ndarray"

    def __init__(self, dtype, shape):
        self.dtype = dtype
        self.shape = shape

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.dtype, obj.shape)

    def _to_dict(self):
        return {"dtype": str(self.dtype), "shape": self.shape}

    @classmethod
    def from_dict(cls, d):
        return cls(np.dtype(d["dtype"]), d["shape"])

    def assign_type(self, next_type):
        if not isinstance(next_type, NumpyArrayType):
            return types.InvalidType()
        if self.dtype != next_type.dtype or self.shape != next_type.shape:
            return types.InvalidType()
        return self

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.npz", binary=True) as f:
            np.savez_compressed(f, arr=obj)

        return self

    @classmethod
    def load_instance(cls, artifact, name):
        with artifact.open(f"{name}.npz", binary=True) as f:
            return np.load(f)["arr"]

    def __str__(self):
        return "<NumpyArrayType %s %s>" % (self.dtype, self.shape)
