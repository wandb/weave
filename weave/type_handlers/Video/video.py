"""Defines the custom Video weave type."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

if TYPE_CHECKING:
    from moviepy.editor import (
        VideoClip,
        VideoFileClip,
    )
    from PIL import Image
try:
    from moviepy.editor import (
        VideoClip,
        VideoFileClip,
    )
    from PIL import Image

except ImportError:
    dependencies_met = False
else:
    dependencies_met = True

SUPPORTED_FORMATS = ["gif", "mp4", "webm"]
DEFAULT_VIDEO_FORMAT = "gif"


class VideoWithPreview(BaseModel):
    """TypedDict for video with preview.
    This is used to store the video and its preview image.
    """

    model_config = {"arbitrary_types_allowed": True}
    video: VideoClip
    preview: Image.Image | None
    video_format: str
    preview_format: str = "png"

    @property
    def video_fname(self) -> str:
        """Get the filename for the video."""
        return f"video.{self.video_format}"

    @property
    def preview_fname(self) -> str:
        """Get the filename for the preview."""
        return f"image.{self.preview_format}"


def get_preview_image(clip: VideoClip) -> Image.Image | None:
    """
    Get a preview image from a VideoClip:
    We get the middle frame since even slightly edited videos will have different mid frames
    but often the same first frame. If we return none, the clip is empty or invalid
    """
    # elif isinstance(clip, mp.
    duration = clip.duration
    # fps = clip.fps
    # n_frames = int(duration * fps)
    # mid_frame = n_frames // 2

    preview_arr = clip.get_frame(duration // 2)
    preview = Image.fromarray(preview_arr) if preview_arr is not None else None
    return preview


def get_format_from_filename(filename: str) -> str | None:
    split = os.path.splitext(filename)
    if len(split) > 1 and len(split[1]) > 1:
        return split[1][1:]  # Get the extension without the dot
    return None


def save(
    obj: VideoClip,
    artifact: MemTraceFilesArtifact,
    name: str,
) -> None:
    """Save a VideoClip to the artifact.
    Args:
        obj: The VideoClip or VideoWithPreview to save
        artifact: The artifact to save to
        name: Ignored, see comment below
    """
    is_video_file = isinstance(obj, VideoFileClip)
    if is_video_file:
        video_format = get_format_from_filename(obj.filename) or DEFAULT_VIDEO_FORMAT
    else:
        video_format = getattr(obj, "format") or DEFAULT_VIDEO_FORMAT
    video_format = video_format.lower()
    if video_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported video format: {video_format} - Only gif, mp4, and webm are supported"
        )

    preview = get_preview_image(obj)

    if preview is None:
        raise ValueError(
            "Failed to read frames from video. Please ensure the video is not corrupted."
        )

    # Save the video file
    with artifact.writeable_file_path(f"video.{video_format}") as fp:
        # If it's already a VideoFileClip just copy it
        if is_video_file:
            shutil.copy(obj.filename, fp)
        else:
            fps = obj.fps or None
            try:
                # Use appropriate writing method based on format
                if video_format == "webm" or video_format == "mp4":
                    obj.write_videofile(fp, fps=fps)
                else:
                    # Gif is the default
                    obj.write_gif(fp, fps=fps)
            except Exception as e:
                raise ValueError(f"Failed to write video file with error: {e}")

    with artifact.writeable_file_path("image.png") as fp:
        preview.save(fp)

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
    video, preview, video_ext, preview_ext = None, None, None, None
    for filename in artifact.path_contents:
        path = artifact.path(filename)
        ext = os.path.splitext(filename)[1][1:]  # Get the extension without the dot
        if filename.startswith("video."):
            if ext in SUPPORTED_FORMATS:
                video = VideoFileClip(path)
                video_ext = ext
            else:
                raise ValueError(f"Unsupported video format: {ext}")
        if filename.startswith("image."):
            if ext in ["png", "jpg", "jpeg"]:
                preview = Image.open(path)
                preview_ext = ext
            else:
                raise ValueError(f"Unsupported image format: {ext}")
    if video and video_ext and preview_ext:
        return VideoWithPreview(
            video=video,
            preview=preview,
            video_format=video_ext,
            preview_format=preview_ext,
        )
    raise ValueError("No video or preview extension found for artifact")


def is_instance(obj: Any) -> bool:
    """Check if the object is any subclass of VideoClip."""
    return isinstance(obj, VideoClip)


def register() -> None:
    """Register the video type handler with the serializer."""
    if dependencies_met:
        serializer.register_serializer(VideoClip, save, load, is_instance)
