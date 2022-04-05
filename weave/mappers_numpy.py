import numpy as np
from . import mappers

from . import weave_types as types
from . import types_numpy


class NumpyArraySaver(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        self.type = type_
        self._arrays = []
        self._artifact = artifact
        self._path = path

    def result_type(self):
        return types_numpy.NumpyArrayRefType(
            types.Const(types.String(), "-".join(self._path))
        )
        # return NumpyArrayRefType(self.type, self._path)

    def close(self):
        name = "-".join(self._path)
        with self._artifact.new_file(f"{name}.npz", binary=True) as f:
            np.savez_compressed(f, arr=np.array(self._arrays))

    def apply(self, arr):
        self._arrays.append(arr)
        # return offset into array
        return types_numpy.NumpyArrayRef("-".join(self._path), len(self._arrays) - 1)


class NumpyArrayLoader:
    def __init__(self, type_, mapper, artifact, path):
        self._artifact = artifact
        self.type = type_
        self._arrays = []
        self._loaded = None

    def result_type(self):
        # TODO: we need to store target type on ref so we can get the
        #     right type back here
        return types_numpy.NumpyArrayType(types.Any(), types.Any())
        # return NumpyArrayRefType(self.type, self._path)

    def apply(self, ref):
        if self._loaded is None:
            # TODO: assumes all refs have the same path (ie assumes
            #     a ConstString Type for path)
            path = ref.path
            with self._artifact.open(f"{path}.npz", binary=True) as f:
                self._loaded = np.load(f)["arr"]
        return self._loaded[ref.index]
