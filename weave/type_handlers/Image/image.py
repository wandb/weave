"""Defines the custom Image weave type."""

from __future__ import annotations

import logging
from typing import Any

from weave.trace import object_preparers, serializer
from weave.trace.custom_objs import MemTraceFilesArtifact
from weave.utils.invertable_dict import InvertableDict

try:
    from PIL import Image
except ImportError:
    dependencies_met = False
else:
    dependencies_met = True

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = "PNG"

pil_format_to_ext = InvertableDict[str, str](
    {
        "JPEG": "jpg",
        "PNG": "png",
    }
)
ext_to_pil_format = pil_format_to_ext.inv


class PILImagePreparer:
    def should_prepare(self, obj: Any) -> bool:
        return isinstance(obj, Image.Image)

    def prepare(self, obj: Image.Image) -> None:
        try:
            # This load is necessary to ensure that the image is fully loaded into memory.
            # If we don't do this, it's possible that only part of the data is loaded
            # before the object is returned.  This can happen when trying to run an evaluation
            # on a ref-get'd dataset with image columns.
            obj.load()
        except Exception as e:
            logger.exception(f"Failed to load PIL Image: {e}")
            raise


def save(obj: Image.Image, artifact: MemTraceFilesArtifact, name: str) -> None:
    fmt = getattr(obj, "format", DEFAULT_FORMAT)
    ext = pil_format_to_ext.get(fmt)
    if ext is None:
        logger.debug(f"Unknown image format {fmt}, defaulting to {DEFAULT_FORMAT}")
        ext = pil_format_to_ext[DEFAULT_FORMAT]

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
    fname = f"image.{ext}"
    with artifact.new_file(fname, binary=True) as f:
        obj.save(f, format=ext_to_pil_format[ext])  # type: ignore


def load(artifact: MemTraceFilesArtifact, name: str) -> Image.Image:
    # Today, we assume there can only be 1 image in the artifact.
    filename = next(iter(artifact.path_contents))
    if not filename.startswith("image."):
        raise ValueError(f"Expected filename to start with 'image.', got {filename}")

    path = artifact.path(filename)
    return Image.open(path)


def register() -> None:
    if dependencies_met:
        serializer.register_serializer(Image.Image, save, load)
        object_preparers.register(PILImagePreparer())
