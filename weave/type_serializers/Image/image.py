"""Defines the custom Image weave type."""

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact

dependencies_met = False

try:
    from PIL import Image

    dependencies_met = True
except ImportError:
    pass


def save(obj: "Image", artifact: MemTraceFilesArtifact, name: str) -> None:
    pass


def load(artifact: MemTraceFilesArtifact, name: str) -> "Image":
    pass


if dependencies_met:
    serializer.register_serializer(Image, save, load)
