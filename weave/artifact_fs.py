import contextlib
import typing
import json
import datetime

from . import artifact_base
from . import ref_base
from . import ref_util
from . import weave_types as types
from . import uris
from . import errors


class FilesystemArtifact(artifact_base.Artifact):
    RefClass: typing.ClassVar[typing.Type["FilesystemArtifactRef"]]
    name: str

    def set(
        self, key: str, type_: types.Type, obj: typing.Any
    ) -> artifact_base.ArtifactRef:
        ref_extra = type_.save_instance(obj, self, key)
        # If save_instance returned a Ref, return that directly.
        # TODO: refactor
        if isinstance(ref_extra, ref_base.Ref):
            return ref_extra
        with self.new_file(f"{key}.type.json") as f:
            json.dump(type_.to_dict(), f)
        return self.RefClass(self, path=key, type=type_, obj=obj, extra=ref_extra)

    def get(self, key: str, type_: types.Type) -> typing.Any:
        return self.ref_from_local_str(key, type_).get()

    @property
    def is_saved(self) -> bool:
        raise NotImplementedError

    @contextlib.contextmanager
    def open(
        self, path: str, binary: bool = False
    ) -> typing.Generator[typing.IO, None, None]:
        raise NotImplementedError

    @contextlib.contextmanager
    def new_file(
        self, path: str, binary: bool = False
    ) -> typing.Generator[typing.IO, None, None]:
        raise NotImplementedError

    def ref_from_local_str(self, s: str, type: "types.Type") -> "FilesystemArtifactRef":
        path, extra = ref_util.parse_local_ref_str(s)
        return self.RefClass(self, path=path, extra=extra, type=type)

    @property
    def created_at(self) -> datetime.datetime:
        raise NotImplementedError

    @property
    def version(self) -> str:
        raise NotImplementedError

    @property
    def location(self) -> uris.WeaveURI:
        raise NotImplementedError


class FilesystemArtifactRef(artifact_base.ArtifactRef):
    FileType: typing.ClassVar[typing.Type[types.Type]]

    artifact: FilesystemArtifact
    path: typing.Optional[str]

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "FilesystemArtifactRef":
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__}({id(self)}) artifact={self.artifact} path={self.path} type={self.type} obj={self.obj is not None} extra={self.extra}"

    @property
    def is_saved(self) -> bool:
        return self.artifact.is_saved

    @property
    def created_at(self) -> datetime.datetime:
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

    def versions(self) -> list["FilesystemArtifactRef"]:
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
