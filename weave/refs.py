import os
import json
from urllib.parse import urlparse

from . import artifacts_local
from . import weave_types as types
from . import box


class LocalArtifactUri:
    def __init__(self, artifact, path=None):
        self.artifact = artifact
        self.path = path
        if self.path is None:
            self.path = "_obj"

    def get(self):
        with self.artifact.open("_obj.type.json") as f:
            type_json = json.load(f)
        wb_type = types.TypeRegistry.type_from_dict(type_json)
        ref = LocalArtifactRef(wb_type, self)
        obj = ref.get()
        return obj

    @property
    def type(self):
        with self.artifact.open(f"{self.path}.type.json") as f:
            type_json = json.load(f)
        return types.TypeRegistry.type_from_dict(type_json)

    @classmethod
    def from_str(cls, s):
        # Commented out the more complicated full URI so that
        # the demo looks nicer
        # TODO: fix.
        # url = urlparse(s)
        # if url.scheme != "local-artifact":
        #     raise Exception("invalid")
        # artifact_root, path = split_path_dotfile(url.path, ".wandb-artifact")
        if "/" not in s:
            return cls(artifacts_local.LocalArtifact(s), "_obj")
        parts = s.split("/", 2)
        if len(parts) == 2:
            return cls(
                artifacts_local.LocalArtifact(parts[0], version=parts[1]), "_obj"
            )
        return cls(artifacts_local.LocalArtifact(parts[0], version=parts[1]), parts[2])

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
    uri: LocalArtifactUri

    def __init__(self, type, uri, obj=None):
        self.type = type
        self.uri = uri
        self.obj = obj

    def to_json(self):
        return {"type": self.type.to_dict(), "uri": str(self.uri)}

    @classmethod
    def from_json(cls, val):
        if isinstance(val, dict) and "type" in val and "uri" in val:
            return cls(
                types.TypeRegistry.type_from_dict(val["type"]),
                LocalArtifactUri.from_str(val["uri"]),
            )
        else:
            return None

    def get(self):
        obj = self.type.load_instance(self.uri.artifact, self.uri.path)
        obj = box.box(obj)
        put_ref(obj, self)
        return obj

    def versions(self):
        artifact_path = os.path.join("local-artifacts", self.uri.artifact._name)
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
                obj = self.uri.artifact.get_other_version_ref(version_name)
                ref = get_ref(obj)
                versions.append(ref)
        return versions

    def __str__(self):
        return str(self.uri)


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef
