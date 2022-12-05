import os

from .. import api as weave
from .. import weave_types as types
from ..ops_primitives import file_local
from ..ops_primitives import file as weave_file
from .. import artifacts_local
from .. import refs


def load_instance(self, artifact, name, extra=None):
    return ArtifactVersionFile(artifact, name)


# Inject onto the type, which lives in refs right now :(
# TODO: fix
refs.ArtifactVersionFileType.load_instance = load_instance  # type: ignore


@weave.weave_class(weave_type=refs.ArtifactVersionFileType)
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


refs.ArtifactVersionFileType.instance_class = ArtifactVersionFile
refs.ArtifactVersionFileType.instance_classes = ArtifactVersionFile


class ArtifactVersionDirType(types.ObjectType):
    name = "artifactversion_dir"

    def __init__(self):
        pass

    def property_types(self):
        return {
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(
                types.String(), types.SubDirType(refs.ArtifactVersionFileType())
            ),
            "files": types.Dict(types.String(), refs.ArtifactVersionFileType()),
        }


@weave.weave_class(weave_type=ArtifactVersionDirType)
class ArtifactVersionDir(weave_file.Dir):
    def _path_return_type(self, path):
        return file_local.path_type(os.path.join(self.fullPath, path))

    def _path(self, path):
        return file_local.open_(os.path.join(self.fullPath, path))


ArtifactVersionDirType.instance_classes = ArtifactVersionDir
ArtifactVersionDirType.instance_class = ArtifactVersionDir
