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
    ):
        self.artifact = artifact
        self.path = path
        super().__init__(obj=obj, type=type, extra=extra)

    def with_extra(
        self, new_type: types.Type, obj: typing.Any, extra: list[str]
    ) -> "ArtifactRef":
        return self.__class__(
            artifact=self.artifact,
            path=self.path,
            type=new_type,
            obj=obj,
            extra=extra,
        )

    def local_ref_str(self) -> str:
        raise NotImplementedError
