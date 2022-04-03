import typing
import os
import json
from urllib.parse import urlparse

from . import artifacts_local
from . import weave_types as types
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


class LocalArtifactRef(Ref):
    artifact: "artifacts_local.LocalArtifact"

    def __init__(self, artifact, path=None, type=None, obj=None):
        self.artifact = artifact
        self.path = path
        if self.path is None:
            self.path = "_obj"
        self._type = type
        self.obj = obj

    @property
    def type(self):
        if self._type is not None:
            return self._type
        with self.artifact.open(f"{self.path}.type.json") as f:
            type_json = json.load(f)
        self._type = types.TypeRegistry.type_from_dict(type_json)
        return self._type

    def get(self) -> typing.Any:
        obj = self.type.load_instance(self.artifact, self.path)
        obj = box.box(obj)
        put_ref(obj, self)
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
        return versions

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
        if len(parts) == 2:
            return cls(
                artifacts_local.LocalArtifact(parts[0], version=parts[1]),
                path="_obj",
                type=type,
            )
        return cls(
            artifacts_local.LocalArtifact(parts[0], version=parts[1]),
            path=parts[2],
            type=type,
        )

    def __str__(self):
        # TODO: this is no good! We always refer to "latest"
        #    but we should actually refer to specific versions.
        # But then when we're mutating, we need to know which branch to
        #    mutate...
        artifact_version = self.artifact._name + "/" + self.artifact.version
        if self.path == "_obj":
            return artifact_version
        return artifact_version + "/" + self.path
        # artifact_uri = f"local-artifact://{self.artifact.abs_root}"
        # if self.path is not None:
        #     return f"{artifact_uri}/{self.path}"
        # return artifact_uri


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef
