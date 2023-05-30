import contextlib
import dataclasses
import typing
import json
import datetime
import os

from . import artifact_base
from . import ref_base
from . import ref_util
from . import weave_types as types
from . import uris
from . import errors
from . import file_base
from . import object_context

from .language_features.tagging import tag_store


class FilesystemArtifactType(types.Type):
    def save_instance(
        self, obj: "FilesystemArtifact", artifact: "FilesystemArtifact", name: str
    ) -> "FilesystemArtifactRef":
        return FilesystemArtifactRef(obj, None)


class BranchPointType(typing.TypedDict):
    commit: str
    n_commits: int
    original_uri: str


@dataclasses.dataclass
class ArtifactMetadata:
    """
    Simple class to represent metadata for an artifact. Since
    Artifacts can be any where between non-saved, saved, and mutated,
    their metadata itself is split into two parts: mutable and readonly.

    Mutable metadata is metadata takes precedence over readonly metadata.
    """

    _mutable_metadata: typing.Dict[str, typing.Any]
    _readonly_metadata: typing.Dict[str, typing.Any]

    def __getitem__(self, key: str) -> typing.Any:
        return self._mutable_metadata.get(key, self._readonly_metadata.get(key))

    def __setitem__(self, key: str, value: typing.Any) -> None:
        self._mutable_metadata[key] = value

    def __delitem__(self, key: str) -> None:
        del self._mutable_metadata[key]

    def __contains__(self, key: str) -> bool:
        return key in self._mutable_metadata or key in self._readonly_metadata

    def as_dict(self) -> typing.Dict[str, typing.Any]:
        return {**self._readonly_metadata, **self._mutable_metadata}

    def update(self, other: typing.Dict[str, typing.Any]) -> None:
        self._mutable_metadata.update(other)


class FilesystemArtifact(artifact_base.Artifact):
    RefClass: typing.ClassVar[typing.Type["FilesystemArtifactRef"]]
    name: str

    def set(
        self, key: str, type_: types.Type, obj: typing.Any
    ) -> artifact_base.ArtifactRef:
        # We should do this, but it doesn't work yet!
        # existing_ref = ref_base.get_ref(obj)
        # if isinstance(existing_ref, artifact_base.ArtifactRef):
        #     return existing_ref
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
    def branch(self) -> typing.Optional[str]:
        raise NotImplementedError

    @property
    def branch_point(self) -> typing.Optional[BranchPointType]:
        raise NotImplementedError

    @property
    def initial_uri_obj(self) -> uris.WeaveURI:
        # uri_obj must be a stable identifier (no aliases) for this artifact.
        # initial_uri_obj is the uri used to construct the artifact, which may include
        # aliases. artifact_wandb is the only case where we need to override this
        # to provide different behaviors for each, because it does not resolve aliases
        # upon construction. storage.to_weavejs is the only place that makes use
        # of initial_uri_obj. It doesn't want to incur the cost of resolving potentially
        # many uris (as in a run summary object), and the calling code doesn't care.
        return self.uri_obj

    @property
    def uri_obj(self) -> uris.WeaveURI:
        raise NotImplementedError

    @property
    def uri(self) -> str:
        return str(self.uri_obj)

    @property
    def metadata(self) -> ArtifactMetadata:
        raise NotImplementedError

    def delete(self) -> None:
        raise NotImplementedError

    def rename(self, new_name: str) -> None:
        raise NotImplementedError

    def direct_url(self, path: str) -> typing.Optional[str]:
        raise NotImplementedError

    def path(self, path: str) -> str:
        raise NotImplementedError

    def size(self, path: str) -> int:
        return os.path.getsize(self.path(path))

    def path_info(
        self, path: str
    ) -> typing.Optional[
        typing.Union["FilesystemArtifactFile", "FilesystemArtifactDir"]
    ]:
        res = self._path_info(path)
        if isinstance(res, FilesystemArtifactRef):
            if res.path is None:
                raise errors.WeaveInternalError(f"Cannot get path info for {path}")
            return res.artifact.path_info(res.path)
        return res

    def _path_info(
        self, path: str
    ) -> typing.Optional[
        typing.Union[
            "FilesystemArtifactFile", "FilesystemArtifactDir", "FilesystemArtifactRef"
        ]
    ]:
        raise NotImplementedError

    def previous_uri(self) -> typing.Optional[str]:
        raise NotImplementedError

    def undo(self) -> typing.Optional["FilesystemArtifact"]:
        raise NotImplementedError


FilesystemArtifactType.instance_classes = FilesystemArtifact


class FilesystemArtifactRef(artifact_base.ArtifactRef):
    FileType: typing.ClassVar[typing.Type[types.Type]]

    artifact: FilesystemArtifact
    path: typing.Optional[str]

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "FilesystemArtifactRef":
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__}({id(self)}) artifact={self.artifact} path={self.path} type={self.type} extra={self.extra}"

    @property
    def _outer_type(self) -> types.Type:
        if self.path is None:
            return types.TypeRegistry.type_of(self.artifact)

        # This block is required to fix some W&B tests that mock artifacts and don't
        # provide a .type.json file. They rely on the ref being constructed with a
        # type. When _get is called, it calls _outer_type to try to read the artifact,
        # which needs to early return here to avoid the type.json read.
        if self.extra is None and self._type is not None:
            return self._type

        try:
            with self.artifact.open(f"{self.path}.type.json") as f:
                type_json = json.load(f)
        except FileNotFoundError:
            return types.TypeRegistry.type_of(self.artifact.path_info(self.path))
        return types.TypeRegistry.type_from_dict(type_json)

    @property
    def type(self) -> types.Type:
        obj_ctx = object_context.get_object_context()
        if obj_ctx:
            t = obj_ctx.lookup_ref_type(str(self))
            if not isinstance(t, object_context.NoResult):
                return t

        if self._type is not None:
            return self._type

        if not self.is_saved:
            return types.NoneType()

        ot = self._outer_type
        if self.extra is not None:
            # This is some hacking to make extra refs work (a ref that's a pointer to
            # an item in a list)...
            # Not a general solution!
            # TODO: fix
            from . import types_numpy

            if isinstance(ot, types.List):
                self._type = ot.object_type
            elif isinstance(ot, types_numpy.NumpyArrayType):
                # The Numpy type implementation is not consistent with how list extra refs
                # work!
                # TODO: fix
                self._type = ot
            else:
                print(
                    "SELF TYPE",
                )
                raise errors.WeaveInternalError(
                    f"Cannot get type of {self} with extra {self.extra}"
                )
        else:
            self._type = ot
        return self._type

    # Artifact Name (unique per project, unique per local-artifact user namespace)
    @property
    def name(self) -> str:
        return self.artifact.name

    # The identifier for the artifact (typically the commit_hash, but can be branch)
    @property
    def version(self) -> str:
        return self.artifact.version

    # An optional branchname by which this artifact is identified.
    @property
    def branch(self) -> typing.Optional[str]:
        return self.artifact.branch

    @property
    def branch_point(self) -> typing.Optional[BranchPointType]:
        return self.artifact.branch_point

    @property
    def is_saved(self) -> bool:
        return self.artifact.is_saved

    # The original URI used to construct the artifact
    @property
    def initial_uri(self) -> str:
        uri = typing.cast("FilesystemArtifactURI", self.artifact.initial_uri_obj)
        uri = typing.cast("FilesystemArtifactURI", uri.parse(str(uri)))
        uri.path = self.path
        uri.extra = self.extra
        return str(uri)

    # A stable, fully qualified URI for this artifact (always uses commit_hash for version)
    @property
    def uri(self) -> str:
        uri = typing.cast("FilesystemArtifactURI", self.artifact.uri_obj)
        uri = typing.cast("FilesystemArtifactURI", uri.parse(str(uri)))
        uri.path = self.path
        uri.extra = self.extra
        return str(uri)

    # A URI suitable to branch from (will include branchname if appropriate)
    @property
    def branch_uri(self) -> str:
        uri = typing.cast("FilesystemArtifactURI", self.artifact.uri_obj)
        uri = typing.cast("FilesystemArtifactURI", uri.parse(str(uri)))
        uri.path = self.path
        uri.extra = self.extra
        if self.branch is not None:
            uri.version = self.branch
        return str(uri)

    def versions(self) -> list["FilesystemArtifactRef"]:
        raise NotImplementedError

    def _get(self) -> typing.Any:
        if self.path is None:
            return self.artifact
        # If we not in the execution path, we don't have a tagging context.
        # But we need a tagging context to load objects that were tagged.
        # This call will only create one if we don't already have one.
        # TODO: caching tagged values is already problematic in other ways
        # since they break idempotency. When we figure that out, we may
        # be able to remove this.
        with tag_store.isolated_tagging_context():
            return self._outer_type.load_instance(
                self.artifact, self.path, extra=self.extra
            )

    def local_ref_str(self) -> str:
        if self.path is None:
            raise errors.WeaveInternalError("Cannot get local ref str for artifact")
        s = self.path
        if self.extra is not None:
            s += "#%s" % "/".join(self.extra)
        return s


@dataclasses.dataclass
class FilesystemArtifactURI(uris.WeaveURI):
    name: str
    version: str
    path: typing.Optional[str] = None
    extra: typing.Optional[list[str]] = None

    def __init__(*args: list[typing.Any], **kwargs: dict[str, typing.Any]) -> None:
        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class FilesystemArtifactFileType(file_base.FileBaseType):
    # Note the name! When Weave0 uses "file" it means FilesystemArtifactFile.
    name = "file"

    def save_instance(
        self,
        obj: "FilesystemArtifactFile",
        artifact: FilesystemArtifact,
        name: str,
    ) -> FilesystemArtifactRef:
        return FilesystemArtifactRef(obj.artifact, obj.path)

    def load_instance(
        self,
        artifact: FilesystemArtifact,
        name: str,
        extra: typing.Optional[list[str]] = None,
    ) -> "FilesystemArtifactFile":
        return FilesystemArtifactFile(artifact, name)


@dataclasses.dataclass
class FilesystemArtifactFile(file_base.File):
    artifact: "FilesystemArtifact"
    path: str

    # Providing a _ref property means that get_ref on this object will return the
    # ref.
    @property
    def _ref(self) -> FilesystemArtifactRef:
        return FilesystemArtifactRef(self.artifact, self.path, obj=self)

    @contextlib.contextmanager
    def open(self, mode: str = "r") -> typing.Generator[typing.IO, None, None]:
        if "r" in mode:
            binary = False
            if "b" in mode:
                binary = True
            with self.artifact.open(self.path, binary=binary) as f:
                yield f
        else:
            raise NotImplementedError

    def size(self) -> int:
        return self.artifact.size(self.path)

    def digest(self) -> typing.Optional[str]:
        from weave.artifact_wandb import WandbArtifact

        if isinstance(self.artifact, WandbArtifact):
            # we can get the digest from the manifest (much faster)
            return self.artifact.digest(self.path)
        else:
            # This matches how WandB calculates digests for files
            from wandb.sdk.lib import hashutil  # type: ignore[attr-defined]

            return hashutil.md5_file_b64(self.artifact.path(self.path))


FilesystemArtifactFileType.instance_classes = FilesystemArtifactFile


class FilesystemArtifactDirType(file_base.BaseDirType):
    name = "dir"
    artifact: "FilesystemArtifactType" = FilesystemArtifactType()

    def property_types(self) -> dict[str, types.Type]:
        return {
            "artifact": self.artifact,
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(
                types.String(),
                file_base.SubDirType(FilesystemArtifactFileType()),
            ),
            "files": types.Dict(types.String(), FilesystemArtifactFileType()),
        }


@dataclasses.dataclass
class FilesystemArtifactDir(file_base.Dir):
    artifact: "FilesystemArtifact"
    fullPath: str
    size: int
    # TODO: these should be mappings instead!
    dirs: dict[str, file_base.SubDir]
    files: dict[str, FilesystemArtifactFile]

    def path_info(
        self, path: str
    ) -> typing.Union[FilesystemArtifactFile, "FilesystemArtifactDir", None]:
        target_path = self.fullPath
        if target_path != "" and path != "":
            target_path += "/"
        target_path += path

        return self.artifact.path_info(target_path)


FilesystemArtifactDirType.instance_classes = FilesystemArtifactDir


def update_weave_meta(wb_type: types.Type, artifact: FilesystemArtifact) -> None:
    panel_type = types.type_name_to_type("Panel")
    artifact.metadata["_weave_meta"] = {
        "is_weave_obj": True,
        "type_name": wb_type.name,
        "is_panel": panel_type and panel_type().assign_type(wb_type),
    }
