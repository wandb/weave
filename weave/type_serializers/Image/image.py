"""Defines the custom Image weave type."""

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact

dependencies_met = False

try:
    from PIL import Image

    dependencies_met = True
except ImportError:
    pass


def save(obj: "Image.Image", artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("image.png") as f:
        obj.save(f)  # type: ignore


def load(artifact: MemTraceFilesArtifact, name: str) -> "Image.Image":
    path = artifact.path("image.png")
    return Image.open(path)


if dependencies_met:
    serializer.register_serializer(Image.Image, save, load)
