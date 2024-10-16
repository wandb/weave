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
    # Note: I am purposely ignoring the `name` here and hard-coding the filename to "image.png".
    # There is an extensive internal discussion here:
    # https://weightsandbiases.slack.com/archives/C03BSTEBD7F/p1723670081582949
    #
    # In summary, there is an outstanding design decision to be made about how to handle the
    # `name` parameter. One school of thought is that using the `name` parameter allows multiple
    # object to use the same artifact more cleanly. However, another school of thought is that
    # the payload should not be dependent on an external name - resulting in different payloads
    # for the same logical object.
    #
    # Using `image.png` is fine for now since we don't have any cases of multiple objects
    # using the same artifact. Moreover, since we package the deserialization logic with the
    # object payload, we can always change the serialization logic later without breaking
    # existing payloads.
    with artifact.new_file("image.png", binary=True) as f:
        obj.save(f, format="png")  # type: ignore


def load(artifact: MemTraceFilesArtifact, name: str) -> "Image.Image":
    # Note: I am purposely ignoring the `name` here and hard-coding the filename. See comment
    # on save.
    path = artifact.path("image.png")
    return Image.open(path)


def register() -> None:
    if dependencies_met:
        serializer.register_serializer(Image.Image, save, load)
