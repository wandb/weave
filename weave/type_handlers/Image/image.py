"""Defines the custom Image weave type."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from weave.trace.serialization import serializer
from weave.trace.serialization.base_serializer import WeaveSerializer
from weave.utils.invertable_dict import InvertableDict
from weave.utils.iterators import first

if TYPE_CHECKING:
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact

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
        "WEBP": "webp",
    }
)
ext_to_pil_format = pil_format_to_ext.inv


class ImageSerializer(WeaveSerializer):
    """Serializer for PIL Image objects.

    Stores images as files in their native format (PNG, JPEG, WEBP, etc.).
    This demonstrates the files-only pattern (no metadata).
    """

    @staticmethod
    def save(
        obj: "Image.Image", artifact: "MemTraceFilesArtifact", name: str
    ) -> Any | None:
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

        return None  # Files-only, no metadata

    @staticmethod
    def load(
        artifact: "MemTraceFilesArtifact", name: str, metadata: Any
    ) -> "Image.Image":
        """Load a PIL Image from artifact.

        Args:
            artifact: The artifact containing the image file
            name: Name hint (unused)
            metadata: Metadata (unused for images)

        Returns:
            PIL Image object
        """
        # Today, we assume there can only be 1 image in the artifact.
        filename = first(artifact.path_contents)
        if not filename.startswith("image."):
            raise ValueError(
                f"Expected filename to start with 'image.', got {filename}"
            )

        path = artifact.path(filename)
        return Image.open(path)


def register() -> None:
    if dependencies_met:
        serializer.register_serializer(Image.Image, ImageSerializer())
