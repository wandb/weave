import typing

from . import artifact_base
from . import weave_types as types
from . import errors
from . import ref_base


class MemArtifact(artifact_base.Artifact):
    _refs: typing.Dict[str, "MemArtifactRef"]

    def __init__(self) -> None:
        self._refs = {}

    def ref_count(self) -> int:
        return len(self._refs)

    def refs(self) -> typing.Iterable[artifact_base.ArtifactRef]:
        return self._refs.values()

    def set(
        self, key: str, type_: types.Type, obj: typing.Any
    ) -> artifact_base.ArtifactRef:
        existing_ref = ref_base.get_ref(obj)
        if isinstance(existing_ref, artifact_base.ArtifactRef):
            return existing_ref
        ref = MemArtifactRef(self, key, type_, obj)
        self._refs[key] = ref
        return ref

    def get(self, key: str, type_: types.Type) -> typing.Any:
        return self._refs[key]._obj


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
