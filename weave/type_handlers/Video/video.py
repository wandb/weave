"""Defines the custom Video weave type."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Optional, TypedDict, Union
from pydantic import BaseModel

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from weave.utils.invertable_dict import InvertableDict
from PIL import Image

try:
    import moviepy.editor as mp
except ImportError:
    dependencies_met = False
else:
    dependencies_met = True

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = "gif"

format_to_ext = InvertableDict[str, str](
    {
        "gif": "gif",
        "mp4": "mp4",
        "webm": "webm",
    }
)
ext_to_format = format_to_ext.inv

class VideoWithPreview(BaseModel):
    """TypedDict for video with preview.
    This is used to store the video and its preview image.
    """
    model_config = { "arbitrary_types_allowed": True }
    video: mp.VideoClip
    preview: Optional[Image.Image]
    video_format: str = DEFAULT_FORMAT
    preview_format: str = "png"

    @property
    def video_fname(self) -> str:
        """Get the filename for the video."""
        return f"video.{self.video_format}"

    @property
    def preview_fname(self) -> str:
        """Get the filename for the preview."""
        return f"image.{self.preview_format}"

def get_preview_image_video_file(clip: mp.VideoFileClip) -> Union[Image.Image, None]:
    duration = clip.duration
    preview_arr = clip.get_frame(duration//2)
    preview = Image.fromarray(preview_arr) if preview_arr is not None else None
    return preview

def get_preview_image(clip: mp.VideoClip) -> Union[Image.Image, None]:
    if isinstance(clip, mp.VideoFileClip):
        return get_preview_image_video_file(clip)
    # elif isinstance(clip, mp.
    duration = clip.duration
    fps = clip.fps
    n_frames = int(duration * fps)
    mid_frame = n_frames//2
    preview_arr = clip.get_frame(mid_frame / fps)
    preview = Image.fromarray(preview_arr) if preview_arr is not None else None
    return preview

def to_video_with_preview(obj: mp.VideoClip) -> Union[VideoWithPreview, None]:
    """Convert a VideoClip to a VideoWithPreview TypedDict.
    This is used to store the video and its preview image.
    """
    fmt = getattr(obj, "format", DEFAULT_FORMAT)
    # Check if the object is a VideoFileClip, which has a filename attribute
    is_file_clip = hasattr(obj, "filename") and isinstance(obj, mp.VideoClip)

    # For VideoFileClip objects, use the original format when it's webm
    if is_file_clip and obj.filename:
        preview = get_preview_image(obj)

        if preview:
            preview.save('./test.png', format='png')
        else:
            logger.error("Failed to extract preview frame from video.")

        original_ext = os.path.splitext(obj.filename)[1].lower().lstrip('.')
        if original_ext not in format_to_ext:
            raise ValueError(f"Unsupported video format: {fmt} - Only gif, mp4, and webm are supported")
        return VideoWithPreview(video=obj, preview=preview, video_format=original_ext, preview_format="png")
    else:
        return None

def save(obj: Union[VideoWithPreview, mp.VideoClip], artifact: MemTraceFilesArtifact, name: str) -> None:
    """Save a VideoClip to the artifact.
    Args:
        obj: The VideoClip or VideoWithPreview to save
        artifact: The artifact to save to
        name: Ignored, see comment below
    """
    if isinstance(obj, mp.VideoClip):
        obj = to_video_with_preview(obj)

    with artifact.writeable_file_path(obj.video_fname) as fp:
        shutil.copy(obj.video.filename, fp)

    if obj.preview:
        with artifact.writeable_file_path(obj.preview_fname) as fp:
            obj.preview.save(fp)

    return



def load(artifact: MemTraceFilesArtifact, name: str) -> VideoWithPreview:
    """Load a VideoClip from the artifact.

    Args:
        artifact: The artifact to load from
        name: Ignored, consistent with save method

    Returns:
        The loaded VideoClip
    """
    # Assume there can only be 1 video in the artifact
    video, preview, video_ext, preview_ext = None, None, "gif", "png"
    for filename in artifact.path_contents:
        path = artifact.path(filename)
        ext = os.path.splitext(filename)[1][1:]  # Get the extension without the dot
        if filename.startswith("video."):
            if ext in ["gif", "mp4", "webm"]:
                video = mp.VideoFileClip(path)
                video_ext = ext
            else:
                raise ValueError(f"Unsupported video format: {ext}")
        if filename.startswith("image."):
            if ext in ["png", "jpg", "jpeg"]:
                preview = Image.open(path)
                preview_ext = ext
            else:
                raise ValueError(f"Unsupported image format: {ext}")
    return VideoWithPreview(video=video, preview=preview, video_format=video_ext, preview_format=preview_ext)

def register() -> None:
    """Register the video type handler with the serializer."""
    if dependencies_met:
        serializer.register_serializer(mp.VideoClip, save, load)
        serializer.register_serializer(VideoWithPreview, save, load)
