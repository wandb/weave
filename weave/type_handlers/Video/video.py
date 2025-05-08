"""Defines the custom Video weave type."""

from __future__ import annotations

import shutil
from enum import Enum
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


class VideoFormat(str, Enum):
    """
    These are NOT the list of formats we accept from the user
    Rather, these are the list of formats we can save to weave servers
    If we detect that the file is in these formats, we copy it over directly
    Otherwise, we encode it to one of these formats using ffmpeg (mp4 by default)
    """

    GIF = "gif"
    MP4 = "mp4"
    WEBM = "webm"
    UNSUPPORTED = "unsupported"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: Any) -> VideoFormat:
        return cls.UNSUPPORTED


DEFAULT_VIDEO_FORMAT = VideoFormat.MP4


def get_format_from_filename(filename: str) -> VideoFormat:
    """Get the file format from a filename.

    Args:
        filename: The filename to extract the format from

    Returns:
        The format string or None if no extension is found
    """
    # Get last dot position
    last_dot = filename.rfind(".")

    # If there's no dot or it's the last character, return None
    if last_dot == -1 or last_dot == len(filename) - 1:
        return VideoFormat.UNSUPPORTED

    # Get the extension without the dot
    return VideoFormat(filename[last_dot + 1 :])


def write_video(fp: str, clip: VideoClip) -> None:
    """
    Takes a filepath and a VideoClip and writes the video to the file.
    errors if the file does not end in a supported video extension.
    """
    fps = clip.fps or None
    audio = clip.audio
    fmt_str = get_format_from_filename(fp)
    fmt = VideoFormat(fmt_str)

    if fmt == VideoFormat.UNSUPPORTED:
        raise ValueError(f"Unsupported video format: {fmt_str}")

    if fmt == VideoFormat.GIF:
        clip.write_gif(fp, fps=fps)
        return
    if fmt == VideoFormat.WEBM:
        codec = "libvpx"
    else:
        codec = "libx264"

    clip.write_videofile(
        fp,
        fps=fps,
        codec=codec,
        audio=audio,
        verbose=False,
        logger=None,
    )


def save_video_file_clip(
    obj: VideoFileClip,
    artifact: MemTraceFilesArtifact,
    _: str,
) -> None:
    """Save a VideoFileClip to the artifact.
    Args:
        obj: The VideoFileClip
        artifact: The artifact to save to
        name: Ignored, see comment below
    """
    video_format = get_format_from_filename(obj.filename)

    # Check if the format is known/supported. If not, set to unsupported
    fmt = VideoFormat(video_format)
    ext = fmt.value

    if fmt == VideoFormat.UNSUPPORTED:
        ext = DEFAULT_VIDEO_FORMAT.value

    with artifact.writeable_file_path(f"video.{ext}") as fp:
        if fmt == VideoFormat.UNSUPPORTED:
            # If the format is unsupported, we need to convert it
            write_video(fp, obj)
        else:
            # Copy the file directly if it's a supported format
            shutil.copy(obj.filename, fp)


def save_non_file_clip(
    obj: VideoClip,
    artifact: MemTraceFilesArtifact,
    _: str,
) -> None:
    ext = DEFAULT_VIDEO_FORMAT.value
    with artifact.writeable_file_path(f"video.{ext}") as fp:
        # If the format is unsupported, we need to convert it
        write_video(fp, obj)


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

    try:
        if is_video_file:
            save_video_file_clip(obj, artifact, name)
        else:
            save_non_file_clip(obj, artifact, name)
    except Exception as e:
        raise ValueError(f"Failed to write video file with error: {e}")


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


def is_video_clip_instance(obj: Any) -> bool:
    """Check if the object is any subclass of VideoClip."""
    return isinstance(obj, VideoClip)


def register() -> None:
    """Register the video type handler with the serializer."""
    if dependencies_met:
        serializer.register_serializer(VideoClip, save, load, is_video_clip_instance)
