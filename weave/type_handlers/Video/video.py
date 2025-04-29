"""Defines the custom Video weave type."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING, Any

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

try:
    from moviepy.editor import (
        VideoClip,
        VideoFileClip,
    )
except ImportError:
    dependencies_met = False
else:
    dependencies_met = True

if TYPE_CHECKING:
    from moviepy.editor import (
        VideoClip,
        VideoFileClip,
    )

SUPPORTED_FORMATS = ["gif", "mp4", "webm"]
DEFAULT_VIDEO_FORMAT = "gif"


def get_format_from_filename(filename: str) -> str | None:
    """Get the file format from a filename.

    Args:
        filename: The filename to extract the format from

    Returns:
        The format string or None if no extension is found
    """
    # Handle special case for just a file extension (like ".mp4")
    if filename.startswith(".") and len(filename) > 1:
        return filename[1:]

    # Use splitext which handles correctly the last extension
    _, ext = os.path.splitext(filename)
    if ext and len(ext) > 1:
        return ext[1:]  # Get the extension without the dot
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
        video_format = getattr(obj, "format", DEFAULT_VIDEO_FORMAT)

    video_format = video_format.lower()
    if video_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported video format: {video_format} - Only gif, mp4, and webm are supported"
        )

    # Save the video file
    with artifact.writeable_file_path(f"video.{video_format}") as fp:
        if is_video_file:
            # If it's already a VideoFileClip just copy it
            shutil.copy(obj.filename, fp)
        else:
            # If it's not a VideoFileClip we need to encode and write the file
            fps = obj.fps or None
            try:
                # Use appropriate writing method based on format
                if video_format == "webm" or video_format == "mp4":
                    # Add codec and verbose=False to ensure consistent behavior
                    codec = "libvpx" if video_format == "webm" else "libx264"
                    obj.write_videofile(
                        fp,
                        fps=fps,
                        codec=codec,
                        audio=False,
                        verbose=False,
                        logger=None,
                    )
                else:
                    # Gif is the default
                    obj.write_gif(fp, fps=fps)
            except Exception as e:
                raise ValueError(
                    f"Failed to write video file with format {video_format} with error: {e}"
                )

    return


def load(artifact: MemTraceFilesArtifact, name: str) -> VideoClip:
    """Load a VideoClip from the artifact.

    Args:
        artifact: The artifact to load from
        name: Ignored, consistent with save method

    Returns:
        The loaded VideoClip
    """
    # Assume there can only be 1 video in the artifact
    for filename in artifact.path_contents:
        path = artifact.path(filename)
        if filename.startswith("video."):
            return VideoFileClip(path)

    raise ValueError("No video or found for artifact")


def is_instance(obj: Any) -> bool:
    """Check if the object is any subclass of VideoClip."""
    return isinstance(obj, VideoClip)


def register() -> None:
    """Register the video type handler with the serializer."""
    if dependencies_met:
        serializer.register_serializer(VideoClip, save, load, is_instance)
