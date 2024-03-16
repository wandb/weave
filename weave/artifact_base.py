# Object hierarchy:
# Artifact (set, get methods)
#   MemArtifact
#   FilesystemArtifact (adds open_file, new_file, etc method)
#     LocalArtifact
#     WandbArtifact

import typing

from . import weave_types as types
from . import ref_base


class Artifact:
    def set(self, key: str, type_: types.Type, obj: typing.Any) -> "ArtifactRef":
        raise NotImplementedError

    def get(self, key: str, type_: types.Type) -> typing.Any:
        raise NotImplementedError


class ArtifactRef(ref_base.Ref):
    def __init__(
        self,
        artifact: Artifact,
        path: typing.Optional[str],
        type: typing.Optional[types.Type] = None,
        obj: typing.Optional[typing.Any] = None,
        extra: typing.Optional[list[str]] = None,
        # Denotes that the ref should be saved as a path ref (just the path and extra)
        # without the full uri, because its a reference within an artifact
        serialize_as_path_ref: bool = False,
    ):
        self.artifact = artifact
        self.path = path
        self.serialize_as_path_ref = serialize_as_path_ref
        super().__init__(obj=obj, type=type, extra=extra)

    def without_extra(self, new_type: typing.Optional[types.Type]) -> "ArtifactRef":
        return self.__class__(
            artifact=self.artifact, path=self.path, type=new_type, obj=None, extra=None
        )

    def with_extra(
        self, new_type: typing.Optional[types.Type], obj: typing.Any, extra: list[str]
    ) -> "ArtifactRef":
        new_extra = self.extra
        if self.extra is None:
            new_extra = []
        else:
            new_extra = self.extra.copy()
        new_extra += extra
        return self.__class__(
            artifact=self.artifact,
            path=self.path,
            type=new_type,
            obj=obj,
            extra=new_extra,
        )

    def local_ref_str(self) -> str:
        raise NotImplementedError
