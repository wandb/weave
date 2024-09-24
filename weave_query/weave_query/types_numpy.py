import numpy as np

from weave.legacy.weave import weave_types as types


# TODO: this doesn't match how extra works for list types...
class NumpyArrayType(types.Type):
    instance_classes = np.ndarray
    name = "WeaveNDArray"

    def __init__(self, dtype="x", shape=(0,)):  # type: ignore
        self.dtype = dtype
        self.shape = shape

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        return cls(obj.dtype, obj.shape)

    def _to_dict(self):  # type: ignore
        return {"dtype": str(self.dtype), "shape": self.shape}

    @classmethod
    def from_dict(cls, d):  # type: ignore
        return cls(np.dtype(d.get("dtype", "object")), d["shape"])

    def _assign_type_inner(self, next_type):  # type: ignore
        if not isinstance(next_type, NumpyArrayType):
            return False
        if (
            self.dtype != next_type.dtype
            and next_type.dtype != np.dtype("object")  # object is like "any"
        ) or tuple(self.shape) != tuple(next_type.shape):
            return False
        return True

    def save_instance(self, obj, artifact, name):  # type: ignore
        with artifact.new_file(f"{name}.npz", binary=True) as f:
            np.savez_compressed(f, arr=obj)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.npz", binary=True) as f:
            return np.load(f)["arr"]

    def __str__(self):  # type: ignore
        return "<NumpyArrayType %s %s>" % (self.dtype, self.shape)
