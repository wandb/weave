from collections.abc import Iterable
import typing
import os
import json
from urllib.parse import urlparse
import wandb

from . import artifacts_local
from . import weave_types as types
from . import errors
from . import box


class Ref:
    pass

    def _ipython_display_(self):
        from . import show

        return show(self)


def get_ref(obj):
    if hasattr(obj, "_ref"):
        return obj._ref
    return None


def put_ref(obj, ref):
    obj._ref = ref


class WandbArtifactRef(Ref):
    def __init__(self, artifact, path, type=None, obj=None):
        self.artifact = artifact
        self.path = path
        self._type = type
        self.obj = obj
        put_ref(obj, self)

    @property
    def version(self):
        return self.artifact.version

    @property
    def type(self):
        if self._type is not None:
            return self._type
        with open(self.artifact.open(f"{self.path}.type.json", "r")) as f:
            type_json = json.load(f)
        self._type = types.TypeRegistry.type_from_dict(type_json)
        return self._type

    def uri(self):
        pass

    def get(self):
        if self.obj:
            return self.obj
        obj = self.type.load_instance(self.artifact, self.path, extra=self.extra)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj
        
    @classmethod
    def from_str(cls, s):
        pass

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
        put_ref(obj, self)
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

    def get(self) -> typing.Any:
        if self.obj:
            return self.obj
        obj = self.type.load_instance(self.artifact, self.path, extra=self.extra)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj

    def versions(self):
        artifact_path = os.path.join("local-artifacts", self.artifact._name)
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
        # Commented out the more complicated full URI so that
        # the demo looks nicer
        # TODO: fix.
        # url = urlparse(s)
        # if url.scheme != "local-artifact":
        #     raise Exception("invalid")
        # artifact_root, path = split_path_dotfile(url.path, ".wandb-artifact")

        if "/" not in s:
            return cls(artifacts_local.LocalArtifact(s), path="_obj", type=type)

        parts = s.split("/", 2)
        if len(parts) == 3:
            path_extra_part = parts[2]
        else:
            path_extra_part = "_obj"
        path, extra = cls.parse_local_ref_str(path_extra_part)
        return cls(
            artifacts_local.LocalArtifact(parts[0], version=parts[1]),
            path=path,
            type=type,
            extra=extra,
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
        elif len(parts) == 2:
            extra = parts[1]
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

    def __str__(self):
        # TODO: this is no good! We always refer to "latest"
        #    but we should actually refer to specific versions.
        # But then when we're mutating, we need to know which branch to
        #    mutate...
        # TODO: Use full URI
        components = [self.artifact._name, self.artifact.version]
        path = self.local_ref_str()
        if path:
            components.append(path)
        return "/".join(components)


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef
