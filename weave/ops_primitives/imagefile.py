import dataclasses
import typing
from .. import types
from .. import api as weave

# Artifact entries implement a File interface.


# A file versioned by an artifact, either inside or a bucket Ref
class ArtifactEntryType(types.Type):
    def load_instance(self, artifact, name, extra=None):
        return ArtifactEntry(artifact, name)


@dataclasses.dataclass
class ArtifactEntry:
    artifact: typing.Any  # Artifact
    path: str


ArtifactEntryType.instance_classes = ArtifactEntry
ArtifactEntryType.instance_class = ArtifactEntry


@weave.type(__override_name="image-file")  # type: ignore
class ImageArtifactEntry:
    # TODO: just File? No, because the frontend is going to call .artifactVersion()
    #     on us. So we need to be ImageArtifactEntry
    path: ArtifactEntry  # This should be a Ref<File<ImageExtensions>>
    format: str
    height: int
    width: int
    sha256: str

    @property
    def artifact(self):
        return self.path.artifact
