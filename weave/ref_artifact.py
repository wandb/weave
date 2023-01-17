import typing
import json

from . import weave_types as types
from . import ref_base
from . import artifact_base
from . import uris
from . import errors


class ArtifactRef(ref_base.Ref):
    FileType: typing.ClassVar[typing.Type[types.Type]]

    artifact: artifact_base.Artifact
    path: typing.Optional[str]

    def __init__(
        self,
        artifact: artifact_base.Artifact,
        path: typing.Optional[str],
        type: typing.Optional[types.Type] = None,
        obj: typing.Optional[typing.Any] = None,
        extra: typing.Optional[list[str]] = None,
    ):
        super().__init__(obj=obj, type=type, extra=extra)
        self.artifact = artifact
        self.path = path

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "ArtifactRef":
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__}({id(self)}) artifact={self.artifact} path={self.path} type={self.type} obj={self.obj is not None} extra={self.extra}"

    @property
    def is_saved(self) -> bool:
        return self.artifact.is_saved

    @property
    def created_at(self) -> str:
        return self.artifact.created_at

    @property
    def version(self) -> str:
        return self.artifact.version

    @property
    def name(self) -> str:
        return self.artifact.location.full_name

    @property
    def type(self) -> types.Type:
        if self._type is not None:
            return self._type
        try:
            with self.artifact.open(f"{self.path}.type.json") as f:
                type_json = json.load(f)
        except (FileNotFoundError, KeyError):
            # If there's no type file, this is a Ref to the file itself
            # TODO: refactor
            return self.FileType()
        self._type = types.TypeRegistry.type_from_dict(type_json)
        return self._type

    @property
    def uri(self) -> str:
        # TODO: should artifacts themselves be "extras" aware??
        # this is really clunky but we cannot use artifact URI since we need
        # to handle extras here which is not present in the artifact
        uri = self.artifact.location
        uri.extra = self.extra
        uri.file = self.path
        return uri.uri

    def versions(self) -> list["ArtifactRef"]:
        raise NotImplementedError

    def _get(self) -> typing.Any:
        if self.path is None:
            return self.artifact
        return self.type.load_instance(self.artifact, self.path, extra=self.extra)

    def local_ref_str(self) -> str:
        if self.path is None:
            raise errors.WeaveInternalError("Cannot get local ref str for artifact")
        s = self.path
        if self.extra is not None:
            s += "#%s" % "/".join(self.extra)
        return s
