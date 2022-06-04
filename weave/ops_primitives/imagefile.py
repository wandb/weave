import dataclasses
import typing
from .. import types
from .. import api as weave


class ArtifactFileType(types.Type):
    def load_instance(self, artifact, name, extra=None):
        return ArtifactFile(artifact, name)


@dataclasses.dataclass
class ArtifactFile:
    artifact: typing.Any  # Artifact
    path: str


ArtifactFileType.instance_classes = ArtifactFile
ArtifactFileType.instance_class = ArtifactFile


@weave.type(__override_name="image-file")  # type: ignore
class ImageFile:
    path: ArtifactFile  # TODO: just file
    format: str
    height: int
    width: int
    sha256: str

    @property
    def artifact(self):
        return self.path.artifact
