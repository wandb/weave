from collections.abc import Iterable
import typing
import os
import json

from . import artifacts_local
from . import weave_types as types
from . import errors
from . import box
from . import artifacts_local
from . import uris


class Ref:
    pass

    def _ipython_display_(self):
        from . import show

        return show(self)

    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def uri(self) -> str:
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.uri


# We store REFS here if we can't attach them directly to the object
REFS: dict[str, typing.Any] = {}


def get_ref(obj):
    if hasattr(obj, "_ref"):
        return obj._ref
    try:
        if id(obj) in REFS:
            return REFS[id(obj)]
    except TypeError:
        pass
    return None


def put_ref(obj, ref):
    try:
        obj._ref = ref
    except AttributeError:
        if isinstance(obj, (int, float, str, list, dict, set)):
            return
        REFS[id(obj)] = ref


def clear_ref(obj):
    try:
        delattr(obj, "_ref")
    except AttributeError:
        pass
    if id(obj) in REFS:
        REFS.pop(id(obj))


class WandbArtifactRef(Ref):
    artifact: "artifacts_local.WandbArtifact"

    def __init__(self, artifact, path, type=None, obj=None, extra=None):
        self.artifact = artifact
        self.path = path
        self._type = type
        self.obj = obj
        self.extra = extra

    @property
    def version(self):
        return self.artifact.version

    @property
    def type(self):
        if self._type is not None:
            return self._type
        with self.artifact.open(f"{self.path}.type.json") as f:
            type_json = json.load(f)
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

    def versions(self):
        # TODO: implement versions on wandb artifact
        return [self.artifact.version]

    def get(self):
        if self.obj is not None:
            return self.obj
        obj = self.type.load_instance(self.artifact, self.path, extra=None)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj

    @classmethod
    def from_str(cls, s):
        uri = uris.WeaveWBArtifactURI(s)
        # TODO: potentially need to pass full entity/project/name instead
        return cls(
            artifacts_local.WandbArtifact(uri.full_name, uri=uri),
            path=uri.file,
        )


types.WandbArtifactRefType.instance_class = WandbArtifactRef
types.WandbArtifactRefType.instance_classes = WandbArtifactRef


class LocalArtifactRef(Ref):
    artifact: "artifacts_local.LocalArtifact"

    def __init__(self, artifact, path, type=None, obj=None, extra=None):
        self.artifact = artifact
        self.path = path
        if "/" in self.path:
            raise errors.WeaveInternalError('"/" in path not yet supported')
        if self.path is None:
            raise errors.WeaveInternalError("path must not be None")
        self._type = type
        self.obj = obj
        self.extra = extra
        if obj is not None:
            obj = box.box(obj)
            put_ref(obj, self)

    @property
    def is_saved(self):
        return self.artifact.is_saved

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
    def version(self):
        return self.artifact.version

    @property
    def type(self):
        if self._type is not None:
            return self._type
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
        # if self.obj is not None:
        #     return self.obj
        obj = self.type.load_instance(self.artifact, self.path, extra=self.extra)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj

    def versions(self):
        artifact_path = os.path.join(
            artifacts_local.LOCAL_ARTIFACT_DIR, self.artifact._name
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
                ref = LocalArtifactRef(art, path="_obj")
                # obj = uri.get()
                # ref = get_ref(obj)
                versions.append(ref)
        return sorted(versions, key=lambda v: v.artifact.created_at)

    @classmethod
    def from_str(cls, s, type=None):
        loc = uris.WeaveLocalArtifactURI(s)
        return cls(
            artifacts_local.LocalArtifact(loc.full_name, loc.version),
            path=loc.file,
            type=type,
            obj=None,
            extra=loc.extra,
        )

    @classmethod
    def from_local_ref(cls, artifact, s, type):
        path, extra = cls.parse_local_ref_str(s)
        return cls(artifact, path=path, extra=extra, type=type)

    @classmethod
    def parse_local_ref_str(cls, s):
        parts = s.split("/")
        path = parts[0]
        if len(parts) == 1:
            extra = None
        else:
            extra = parts[1:]
        return path, extra

    def local_ref_str(self):
        parts = []
        if self.path != "_obj" or self.extra is not None:
            parts.append(self.path)
        if self.extra is not None:
            if isinstance(self.extra, Iterable):
                for comp in self.extra:
                    parts.append(str(comp))
            else:
                parts.append(str(self.extra))
        return "/".join(parts)


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef
