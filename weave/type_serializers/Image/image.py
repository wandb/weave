"""Defines the custom Image weave type."""

import base64
import logging
import re
from io import BytesIO
from pathlib import Path
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

# match local image file paths
IMAGE_SUFFIX = r".*\.(png|jpg|jpeg|gif|tiff)"
LOCAL_IMAGE_PATTERN = re.compile(rf"^{IMAGE_SUFFIX}$", re.IGNORECASE)
REMOTE_IMAGE_PATTERN = re.compile(rf"https://.*\.{IMAGE_SUFFIX}", re.IGNORECASE)
# match base64 encoded images
BASE64_IMAGE_PATTERN = re.compile(r"^data:image/.*;base64,", re.IGNORECASE)


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


def is_local_image(path: str) -> bool:
    return LOCAL_IMAGE_PATTERN.match(path) is not None


def is_remote_image(path: str) -> bool:
    return REMOTE_IMAGE_PATTERN.match(path) is not None


def is_base64_image(path: str) -> bool:
    return BASE64_IMAGE_PATTERN.match(path) is not None


class PathImage(BaseModel):
    # allow PIL.Image.Image in the pydantic model
    model_config = {"arbitrary_types_allowed": True}

    path: Optional[str | Path]
    img: Optional[Image.Image]

    @staticmethod
    def from_path(path: str | Path) -> Optional["PathImage"]:
        if isinstance(path, str):
            assert is_local_image(path), "Path is not a local image"
        try:
            img = Image.open(path)
            return PathImage(img=img, path=path)
        except Exception as e:
            logger.warning(f"Failed to open local image file: {path}. {e}")
            return None

    @staticmethod
    def from_url(url: str) -> Optional["PathImage"]:
        assert is_remote_image(url), "URL is not a remote image"
        try:
            import requests

            img_stream = requests.get(url, stream=True).raw
            img = Image.open(img_stream)
            return PathImage(img=img, path=url)
        except Exception as e:
            logger.warning(f"Failed to load remote image file: {url}. {e}")
            return None


class EncodedImage(BaseModel):
    # allow PIL.Image.Image in the pydantic model
    model_config = {"arbitrary_types_allowed": True}

    raw_data: str
    img: Image.Image

    @staticmethod
    def from_data(data: str) -> Optional["EncodedImage"]:
        assert is_base64_image(data), "Data is not a base64 encoded image"
        try:
            image_data = re.sub("^data:image/.+;base64,", "", data)
            img = Image.open(BytesIO(base64.b64decode(image_data)))
            return EncodedImage(raw_data=data, img=img)
        except Exception as e:
            logger.warning(f"Failed to decode base64 image data: {e}")
            return None
