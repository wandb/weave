import numpy as np
from . import weave_types as types
from . import errors


# TODO: this doesn't match how extra works for list types...
class NumpyArrayType(types.Type):
    instance_classes = np.ndarray
    name = "WeaveNDArray"

    def __init__(self, dtype="x", shape=(0,)):
        self.dtype = dtype
        self.shape = shape

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.dtype, obj.shape)

    def _to_dict(self):
        return {"dtype": str(self.dtype), "shape": self.shape}

    @classmethod
    def from_dict(cls, d):
        return cls(np.dtype(d.get("dtype", "object")), d["shape"])

    def _assign_type_inner(self, next_type):
        if not isinstance(next_type, NumpyArrayType):
            return False
        if (
            self.dtype != next_type.dtype
            and next_type.dtype != np.dtype("object")  # object is like "any"
        ) or tuple(self.shape) != tuple(next_type.shape):
            return False
        return True

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.npz", binary=True) as f:
            np.savez_compressed(f, arr=obj)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.npz", binary=True) as f:
            return np.load(f)["arr"]

    def __str__(self):
        return "<NumpyArrayType %s %s>" % (self.dtype, self.shape)
