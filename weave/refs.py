import typing
import os
import json

from . import artifacts_local
from . import weave_types as types
from . import errors
from . import box
from . import uris

if typing.TYPE_CHECKING:
    from .ops_domain.file_wbartifact import ArtifactVersionFile


class Ref:
    artifact: artifacts_local.Artifact
    extra: typing.Optional[list[str]]
    _type: typing.Optional[types.Type]

    @property
    def is_saved(self) -> bool:
        return self.artifact.is_saved

    @property
    def type(self) -> typing.Optional[types.Type]:
        return self._type

    # TODO: This local ref stuff should be split out to separate class.
    # Its a hack.
    @classmethod
    def from_local_ref(
        cls, artifact: artifacts_local.Artifact, s: str, type: types.Type
    ) -> "Ref":
        path, extra = cls.parse_local_ref_str(s)
        if isinstance(artifact, artifacts_local.LocalArtifact):
            return LocalArtifactRef(artifact, path=path, extra=extra, type=type)
        elif isinstance(artifact, artifacts_local.WandbArtifact):
            return WandbArtifactRef(artifact, path=path, extra=extra, type=type)
        else:
            raise ValueError(f"Unknown artifact type {artifact}")

    @classmethod
    def from_str(cls, s: str) -> "Ref":
        uri = uris.WeaveURI.parse(s)
        if isinstance(uri, uris.WeaveRuntimeURI):
            return MemRef.from_uri(uri)
        elif isinstance(uri, uris.WeaveLocalArtifactURI):
            return LocalArtifactRef.from_uri(uri)
        elif isinstance(uri, uris.WeaveWBArtifactURI):
            return WandbArtifactRef.from_uri(uri)
        else:
            raise errors.WeaveInvalidURIError("invalid uri: %s" % s)

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "Ref":
        raise NotImplementedError

    @classmethod
    def parse_local_ref_str(
        cls, s: str
    ) -> typing.Tuple[str, typing.Optional[list[str]]]:
        if "#" not in s:
            return s, None
        path, extra = s.split("#", 1)
        return path, extra.split("/")

    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def uri(self) -> str:
        raise NotImplementedError()

    def get(self) -> typing.Any:
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.uri


MEM_OBJS: typing.Dict[str, typing.Any] = {}


class MemRef(Ref):
    _name: str

    def __init__(self, name: str):
        self._name = name

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "MemRef":
        if not isinstance(uri, uris.WeaveRuntimeURI):
            raise errors.WeaveInternalError(
                f"Invalid URI class passed to MemRef.from_uri: {type(uri)}"
            )
        return cls(uri.full_name)

    @property
    def name(self) -> str:
        return self._name

    def get(self) -> typing.Any:
        if self._name not in MEM_OBJS:
            name = self._name  # pick name off of self for sentry logging
            raise errors.WeaveStorageError(f"Object {name} not found")
        return MEM_OBJS[self.name]

    def __str__(self) -> str:
        return self.name


def save_mem(obj: typing.Any, name: str) -> MemRef:
    MEM_OBJS[name] = obj
    return MemRef(name)


# We store REFS here if we can't attach them directly to the object
REFS: dict[int, Ref] = {}


def get_ref(obj: typing.Any) -> typing.Optional[Ref]:
    if isinstance(obj, Ref):
        return obj
    if hasattr(obj, "_ref"):
        return obj._ref
    try:
        if id(obj) in REFS:
            return REFS[id(obj)]
    except TypeError:
        pass
    return None


def put_ref(obj: typing.Any, ref: Ref) -> None:
    try:
        obj._ref = ref
    except AttributeError:
        if isinstance(obj, (int, float, str, list, dict, set)):
            return
        REFS[id(obj)] = ref


def clear_ref(obj: typing.Any) -> None:
    try:
        delattr(obj, "_ref")
    except AttributeError:
        pass
    if id(obj) in REFS:
        REFS.pop(id(obj))


def deref(ref: Ref) -> typing.Any:
    if isinstance(ref, Ref):
        return ref.get()
    return ref


# This should not be declared here, but WandbArtifactRef.type needs to
# be able to create it right now, because of a series of hacks.
# Instead, We probably need a WandbArtifactFileRef.
# TODO: fix
class ArtifactVersionFileType(types.Type):
    name = "ArtifactVersionFile"

    def save_instance(
        self,
        obj: "ArtifactVersionFile",
        artifact: artifacts_local.LocalArtifact,
        name: str,
    ) -> "WandbArtifactRef":
        return WandbArtifactRef(obj.artifact, obj.path)

    # load_instance is injected by file_wbartifact.py in ops_domain.
    # Bad bad bad!
    # TODO: fix


class WandbArtifactRef(Ref):
    artifact: "artifacts_local.WandbArtifact"
    path: typing.Optional[str]
    _type: typing.Optional[types.Type]
    obj: typing.Optional[typing.Any]
    extra: typing.Optional[list[str]]

    def __init__(
        self,
        artifact: artifacts_local.WandbArtifact,
        path: typing.Optional[str],
        type: typing.Optional[types.Type] = None,
        obj: typing.Optional[typing.Any] = None,
        extra: typing.Optional[list[str]] = None,
    ):
        self.artifact = artifact
        self.path = path
        self._type = type
        self.obj = obj
        self.extra = extra

    @property
    def version(self) -> str:
        return self.artifact.version

    @property
    def type(self) -> types.Type:
        if self._type is not None:
            return self._type
        # if self.path is None:
        #     # If there's no path, this is a Ref directly to an ArtifactVersion
        #     # TODO: refactor
        #     return wbartifact.ArtifactVersionType()

        try:
            with self.artifact.open(f"{self.path}.type.json") as f:
                type_json = json.load(f)
        except (FileNotFoundError, KeyError):
            # If there's no type file, this is a Ref to the file itself
            # TODO: refactor
            return ArtifactVersionFileType()
        self._type = types.TypeRegistry.type_from_dict(type_json)
        return self._type

    @property
    def name(self) -> str:
        return self.artifact.location.full_name

    @property
    def uri(self) -> str:
        # TODO: should artifacts themselves be "extras" aware??
        # this is really clunky but we cannot use artifact URI since we need
        # to handle extras here which is not present in the artifact
        uri = uris.WeaveURI.parse(self.artifact.uri())
        uri.extra = self.extra
        uri.file = self.path
        return uri.uri

    def versions(self) -> list[str]:
        # TODO: implement versions on wandb artifact
        return [self.artifact.version]

    def get(self) -> typing.Any:
        if self.obj is not None:
            return self.obj
        if self.path is None:
            return self.artifact
        obj = self.type.load_instance(self.artifact, self.path, extra=None)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "WandbArtifactRef":
        if not isinstance(uri, uris.WeaveWBArtifactURI):
            raise errors.WeaveInternalError(
                f"Invalid URI class passed to WandbArtifactRef.from_uri: {type(uri)}"
            )
        # TODO: potentially need to pass full entity/project/name instead
        return cls(
            artifacts_local.WandbArtifact(uri.full_name, uri=uri),
            path=uri.file,
        )


types.WandbArtifactRefType.instance_class = WandbArtifactRef
types.WandbArtifactRefType.instance_classes = WandbArtifactRef


class LocalArtifactRef(Ref):
    artifact: artifacts_local.LocalArtifact
    path: str
    _type: typing.Optional[types.Type]
    obj: typing.Optional[typing.Any]
    extra: typing.Optional[list[str]]

    def __init__(
        self,
        artifact: artifacts_local.LocalArtifact,
        path: typing.Optional[str],
        type: typing.Optional[types.Type] = None,
        obj: typing.Optional[typing.Any] = None,
        extra: typing.Optional[list[str]] = None,
    ):
        self.artifact = artifact
        if path is None:
            raise errors.WeaveInternalError("path must not be None")
        if "/" in path:
            raise errors.WeaveInternalError('"/" in path not yet supported: %s' % path)
        self.path = path
        self._type = type
        self.obj = obj
        self.extra = extra
        if obj is not None:
            obj = box.box(obj)
            put_ref(obj, self)

    def __repr__(self) -> str:
        return f"<LocalArtifactRef({id(self)}) artifact={self.artifact} path={self.path} type={self.type} obj={self.obj is not None} extra={self.extra}"

    @property
    def created_at(self) -> str:
        return self.artifact.created_at

    @property
    def uri(self) -> str:
        # TODO: should artifacts themselves be "extras" aware??
        # this is really clunky but we cannot use artifact URI since we need
        # to handle extras here which is not present in the artifact
        uri = uris.WeaveURI.parse(self.artifact.uri())
        uri.extra = self.extra
        uri.file = self.path
        return uri.uri

    @property
    def version(self) -> typing.Optional[str]:
        return self.artifact.version

    @property
    def type(self) -> types.Type:
        if self._type is not None:
            return self._type
        # if self.path != "_obj":
        #     raise errors.WeaveInternalError(
        #         "Trying to load type from a non-root object. Ref should be instantiated with a type for this object: %s %s"
        #         % (self.artifact, self.path)
        #     )
        with self.artifact.open(f"{self.path}.type.json") as f:
            type_json = json.load(f)
        self._type = types.TypeRegistry.type_from_dict(type_json)
        return self._type

    @property
    def name(self) -> str:
        return self.artifact.location.full_name

    def get(self) -> typing.Any:
        # Can't do this, when you save a list, you get a different
        # representation back which test_decorators.py depend on right now
        if self.obj is not None:
            return self.obj
        obj = self.type.load_instance(self.artifact, self.path, extra=self.extra)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj

    def versions(self) -> list["LocalArtifactRef"]:
        artifact_path = os.path.join(
            artifacts_local.local_artifact_dir(), self.artifact.name
        )
        versions = []
        for version_name in os.listdir(artifact_path):
            if (
                not os.path.islink(os.path.join(artifact_path, version_name))
                and not version_name.startswith("working")
                and not version_name.startswith(".")
            ):
                # This is ass-backward, have to get the full object to just
                # get the ref.
                # TODO
                art = self.artifact.get_other_version(version_name)
                if art is None:
                    raise errors.WeaveInternalError(
                        "Could not get other version: %s %s"
                        % (self.artifact, version_name)
                    )
                ref = LocalArtifactRef(art, path="_obj")
                # obj = uri.get()
                # ref = get_ref(obj)
                versions.append(ref)
        return sorted(versions, key=lambda v: v.artifact.created_at)

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "LocalArtifactRef":
        if not isinstance(uri, uris.WeaveLocalArtifactURI):
            raise errors.WeaveInternalError(
                f"Invalid URI class passed to WandbLocalArtifactRef.from_uri: {type(uri)}"
            )
        return cls(
            artifacts_local.LocalArtifact(uri.full_name, uri.version),
            path=uri.file,
            obj=None,
            extra=uri.extra,
        )

    def local_ref_str(self) -> str:
        s = self.path
        if self.extra is not None:
            s += "#%s" % "/".join(self.extra)
        return s


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef


def get_local_version_ref(name: str, version: str) -> typing.Optional[LocalArtifactRef]:
    # TODO: Watch out, this is a major race!
    #   - We need to eliminate this race or allow duplicate objectcs in parallel
    #     and then resolve later.
    #   - This is especially a problem for creating Runs and async Runs. We may
    #     accidentally launch parallel runs with the same run ID!
    if not artifacts_local.local_artifact_exists(name, version):
        return None
    art = artifacts_local.LocalArtifact(name, version)
    return LocalArtifactRef(art, path="_obj")


# Should probably be "get_version_object()"
def get_local_version(name: str, version: str) -> typing.Any:
    ref = get_local_version_ref(name, version)
    if ref is None:
        return None
    return ref.get()
