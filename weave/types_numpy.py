import numpy as np
from . import weave_types as types
from . import errors


class NumpyArraySaver:
    def __init__(self, artifact, name):
        self._artifact = artifact
        self._name = name
        self._arrays = []

    def add(self, arr):
        self._arrays.append(arr)
        return len(self._arrays) - 1

    def close(self):
        arr = np.array(self._arrays)
        with self._artifact.new_file(f"{self._name}.npz", binary=True) as f:
            np.savez_compressed(f, arr=arr)


class NumpyArrayLoader:
    def __init__(self, artifact, name):
        self._artifact = artifact
        self._name = name
        with artifact.open(f"{name}.npz", binary=True) as f:
            self._arr = np.load(f)["arr"]

    def get(self, index):
        return self._arr[index]


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
        handler = artifact.get_path_handler(name, handler_constructor=NumpyArraySaver)
        index = handler.add(obj)
        return [str(index)]

    @classmethod
    def load_instance(cls, artifact, name, extra=None):
        if extra is None or not isinstance(extra, list):
            raise errors.WeaveInternalError(
                f"Received unexpect 'extra' param - {extra}. Expected a singleton list of integer."
            )
        extra = extra[0]
        index = int(extra)
        handler = artifact.get_path_handler(name, handler_constructor=NumpyArrayLoader)
        return handler.get(index)

    def __str__(self):
        return "<NumpyArrayType %s %s>" % (self.dtype, self.shape)
