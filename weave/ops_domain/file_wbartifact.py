import os
from .. import api as weave
from .. import weave_types as types
from ..ops_primitives import file as weave_file
from .. import artifacts_local
from .. import refs


class ArtifactVersionFileType(types.Type):
    name = "ArtifactVersionFile"

    def save_instance(self, obj, artifact, name):
        return refs.WandbArtifactRef(obj.artifact, obj.path)

    def load_instance(self, artifact, name, extra=None):
        return ArtifactVersionFile(artifact, name)


@weave.weave_class(weave_type=ArtifactVersionFileType)
class ArtifactVersionFile(weave_file.File):
    artifact: artifacts_local.WandbArtifact
    path: str

    def __init__(self, artifact, path):
        self.artifact = artifact
        self.path = path

    def get_local_path(self):
        return self.artifact.path(self.path)

    def _contents(self):
        return open(self.get_local_path(), encoding="ISO-8859-1").read()


ArtifactVersionFileType.instance_class = ArtifactVersionFile
ArtifactVersionFileType.instance_classes = ArtifactVersionFile


class ArtifactVersionDirType(types.ObjectType):
    name = "artifactversion-dir"

    def __init__(self):
        pass

    def property_types(self):
        return {
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(
                types.String(), types.SubDirType(ArtifactVersionFileType())
            ),
            "files": types.Dict(types.String(), ArtifactVersionFileType()),
        }


@weave.weave_class(weave_type=ArtifactVersionDirType)
class ArtifactVersionDir(weave_file.Dir):
    def _path_return_type(self, path):
        return path_type(os.path.join(self.fullPath, path))

    def _path(self, path):
        return open_(os.path.join(self.fullPath, path))


ArtifactVersionDirType.instance_classes = ArtifactVersionDir
ArtifactVersionDirType.instance_class = ArtifactVersionDir
