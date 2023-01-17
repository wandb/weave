import typing

from . import artifact_base
from . import weave_types as types
from . import errors


class MemArtifact(artifact_base.Artifact):
    _refs: typing.Dict[str, typing.Any]

    def __init__(self) -> None:
        self._refs = {}

    def set(self, key: str, type_: types.Type, obj: typing.Any) -> "MemArtifactRef":
        self._refs[key] = obj
        return MemArtifactRef(self, key, type_, obj)

    def get(self, key: str, type_: types.Type) -> typing.Any:
        return self._refs[key]


class MemArtifactRef(artifact_base.ArtifactRef):
    @property
    def is_saved(self) -> bool:
        return False

    def local_ref_str(self) -> str:
        if self.path is None:
            raise errors.WeaveInternalError("MemArtifact without path!")
        return self.path

    @property
    def uri(self) -> str:
        raise errors.WeaveInternalError("Cannot get URI for in-memory artifact")
