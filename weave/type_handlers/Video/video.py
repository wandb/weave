"""Defines the custom Video weave type."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Optional

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from weave.utils.invertable_dict import InvertableDict

try:
    import moviepy.editor as mp
except ImportError:
    dependencies_met = False
else:
    dependencies_met = True

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = "gif"

# Video format to file extension mapping
format_to_ext = InvertableDict[str, str](
    {
        "gif": "gif",
        "mp4": "mp4",
        "webm": "webm",
    }
)
ext_to_format = format_to_ext.inv


def save(obj: mp.VideoClip, artifact: MemTraceFilesArtifact, name: str) -> None:
    """Save a VideoClip to the artifact.
    
    Args:
        obj: The VideoClip to save
        artifact: The artifact to save to
        name: Ignored, see comment below
    """
    # Get the format of the video, default to GIF if unknown
    fmt = getattr(obj, "format", DEFAULT_FORMAT)
    
    # Check if the object is a VideoFileClip, which has a filename attribute
    is_file_clip = hasattr(obj, "filename") and isinstance(obj, mp.VideoFileClip)
    
    # For VideoFileClip objects, use the original format when it's webm
    if is_file_clip and obj.filename:
        original_ext = os.path.splitext(obj.filename)[1].lower().lstrip('.')
        if original_ext == "webm":
            # Use webm directly for webm files
            fname = "video.webm"
            with artifact.writeable_file_path(fname) as fp:
                # Use shutil.copy instead of reencoding to preserve quality and improve performance
                shutil.copy(obj.filename, fp)
            return
        elif original_ext == "mp4":
            # Convert mp4 to webm
            fname = "video.webm"
            with artifact.writeable_file_path(fname) as fp:
                logger.debug("Converting MP4 to WebM for browser compatibility")
                obj.write_videofile(fp, codec="libvpx", audio_codec="libvorbis", 
                                  fps=obj.fps, preset="fast", ffmpeg_params=["-crf", "20"])
            return
    
    # Handle other cases as before
    ext = format_to_ext.get(fmt, DEFAULT_FORMAT)
    
    # Similar to image.py, we're using a standard filename for consistency
    # See the extensive comment in the image.py file for rationale
    fname = f"video.{ext}"
    
    with artifact.writeable_file_path(fname) as fp:
        # If the video is MP4 format, convert to webm for web compatibility
        if ext == "mp4":
            logger.debug("Converting MP4 to WebM for browser compatibility")
            obj.write_videofile(fp, codec="libvpx", audio_codec="libvorbis", 
                               fps=obj.fps, preset="fast", ffmpeg_params=["-crf", "20"])
            # Update the filename to reflect the new format
            os.rename(fp, fp.replace(".mp4", ".webm"))
            fname = "video.webm"
        elif ext == "gif":
            obj.write_gif(fp, fps=obj.fps)
        elif ext == "webm":
            obj.write_videofile(fp, codec="libvpx", audio_codec="libvorbis", 
                               fps=obj.fps, preset="fast", ffmpeg_params=["-crf", "20"])
        else:
            # Fallback to GIF if format is unknown
            logger.debug(f"Unknown video format {fmt}, defaulting to {DEFAULT_FORMAT}")
            obj.write_gif(fp, fps=obj.fps)


def load(artifact: MemTraceFilesArtifact, name: str) -> mp.VideoClip:
    """Load a VideoClip from the artifact.

    Args:
        artifact: The artifact to load from
        name: Ignored, consistent with save method
        
    Returns:
        The loaded VideoClip
    """
    # Assume there can only be 1 video in the artifact
    filename = next(iter(artifact.path_contents))
    if not filename.startswith("video."):
        raise ValueError(f"Expected filename to start with 'video.', got {filename}")
    
    path = artifact.path(filename)
    ext = os.path.splitext(filename)[1][1:]  # Get the extension without the dot
    
    if ext in ["gif", "mp4", "webm"]:
        return mp.VideoFileClip(path)
    else:
        raise ValueError(f"Unsupported video format: {ext}")


def register() -> None:
    """Register the video type handler with the serializer."""
    if dependencies_met:
        serializer.register_serializer(mp.VideoClip, save, load)
