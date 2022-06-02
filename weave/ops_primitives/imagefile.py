import dataclasses
import typing
from .. import types


class ArtifactFileType(types.Type):
    def save_instance(self, obj, artifact, name):
        pass

    def load_instance(self, artifact, name, extra=None):
        return ArtifactFile(artifact, name)


@dataclasses.dataclass
class ArtifactFile:
    artifact: typing.Any
    path: str


class ImageFileType(types.ObjectType):
    name = "image-file"

    def property_types(self):
        return {
            "path": ArtifactFileType(),
            "format": types.String(),
            "height": types.Int(),
            "width": types.Int(),
            "sha256": types.String(),
        }


@dataclasses.dataclass
class ImageFile:
    path: ArtifactFile
    format: str
    height: int
    width: int
    sha256: str
    artifact: typing.Any


ImageFileType.instance_class = ImageFile
ImageFileType.instance_classes = ImageFile
