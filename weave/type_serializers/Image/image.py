"""Defines the custom Image weave type."""

import base64
import logging
import re
from functools import cached_property
from io import BytesIO
from typing import Optional

from pydantic import BaseModel

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact

dependencies_met = False

try:
    from PIL import Image

    dependencies_met = True
except ImportError:
    pass


logger = logging.getLogger(__name__)


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


# match local image file paths
image_suffix = r".*\.(png|jpg|jpeg|gif|tiff)"
local_image_pattern = re.compile(rf"^{image_suffix}$", re.IGNORECASE)
remote_image_pattern = re.compile(rf"https://.*\.{image_suffix}", re.IGNORECASE)
# match base64 encoded images
base64_image_pattern = re.compile(r"^data:image/.*;base64,", re.IGNORECASE)


def is_local_image(path: str) -> bool:
    return local_image_pattern.match(path) is not None


def is_remote_image(path: str) -> bool:
    return remote_image_pattern.match(path) is not None


def is_base64_image(path: str) -> bool:
    return base64_image_pattern.match(path) is not None


class PathImage(BaseModel):
    data: Optional[str]
    path: Optional[str]

    @cached_property
    def img(self) -> Optional[Image.Image]:
        if not dependencies_met:
            logger.error("Failed to load image: PIL is not installed")
            return None

        # If we have the raw bytes, use that
        if self.data:
            # strip headers, then decode
            try:
                image_data = re.sub("^data:image/.+;base64,", "", self.data)
                return Image.open(BytesIO(base64.b64decode(image_data)))
            except Exception as e:
                logger.error(f"Failed to decode base64 image data: {e}")
                return None

        if not self.path:
            return None

        if is_local_image(self.path):
            try:
                return Image.open(self.path)
            except Exception as e:
                logger.error(f"Failed to open local image file: {self.path}. {e}")
                return None

        if is_remote_image(self.path):
            try:
                import requests

                return Image.open(requests.get(self.path).raw)
            except Exception as e:
                logger.error(f"Failed to load remote image file: {self.path}. {e}")
                return None
        return None
