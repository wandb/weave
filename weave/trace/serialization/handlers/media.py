"""Serialization handlers for media and other special types."""

from __future__ import annotations

import datetime
import shutil
from typing import Any, TypedDict

from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.registry import SerializationContext, register

# Try to import optional dependencies
try:
    from rich.markdown import Markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    Markdown = None

try:
    from moviepy.editor import VideoClip, VideoFileClip
    from weave.type_handlers.Video.video import (
        VideoFormat,
        DEFAULT_VIDEO_FORMAT,
        get_format_from_filename,
        write_video,
    )
    VIDEO_AVAILABLE = True
except ImportError:
    VIDEO_AVAILABLE = False
    VideoClip = None

try:
    from weave.type_handlers.Content.content import Content
    CONTENT_AVAILABLE = True
except ImportError:
    CONTENT_AVAILABLE = False
    Content = None

try:
    from weave.type_handlers.File.file import File
    FILE_AVAILABLE = True
except ImportError:
    FILE_AVAILABLE = False
    File = None


# DateTime handlers
def serialize_datetime(obj: datetime.datetime, context: SerializationContext) -> dict[str, Any]:
    """Serialize a datetime object to ISO format with timezone information."""
    # If the datetime object is naive (has no timezone), assume UTC
    if obj.tzinfo is None:
        obj = obj.replace(tzinfo=datetime.timezone.utc)
    
    return {
        "_type": "datetime",
        "value": obj.isoformat()
    }


def deserialize_datetime(data: dict[str, Any], context: SerializationContext) -> datetime.datetime:
    """Deserialize an ISO format string back to a datetime object with timezone."""
    if data.get("_type") != "datetime":
        raise ValueError(f"Expected datetime type, got {data.get('_type')}")
    
    return datetime.datetime.fromisoformat(data["value"])


# Markdown handlers
class SerializedMarkdown(TypedDict):
    markup: str
    code_theme: str | None


def serialize_markdown(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a Rich Markdown object."""
    if not MARKDOWN_AVAILABLE:
        return {"_type": "FallbackString", "_value": str(obj)}
    
    result = {
        "_type": "Markdown",
        "markup": obj.markup,
    }
    
    if hasattr(obj, "code_theme") and obj.code_theme:
        result["code_theme"] = obj.code_theme
    
    return result


def deserialize_markdown(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize a Rich Markdown object."""
    if not MARKDOWN_AVAILABLE:
        return None
    
    if data.get("_type") != "Markdown":
        return None
    
    kwargs = {"markup": data.get("markup", "")}
    if "code_theme" in data:
        kwargs["code_theme"] = data["code_theme"]
    
    return Markdown(**kwargs)


def is_markdown(obj: Any) -> bool:
    """Check if object is a Rich Markdown."""
    if not MARKDOWN_AVAILABLE:
        return False
    return isinstance(obj, Markdown)


# Video handlers
def serialize_video(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a MoviePy VideoClip."""
    if not VIDEO_AVAILABLE:
        return {"_type": "FallbackString", "_value": str(obj)}
    
    # Create artifact for file storage
    artifact = MemTraceFilesArtifact()
    
    # Determine format
    if isinstance(obj, VideoFileClip) and hasattr(obj, "filename"):
        fmt = get_format_from_filename(obj.filename)
        if fmt == VideoFormat.UNSUPPORTED:
            fmt = DEFAULT_VIDEO_FORMAT
    else:
        fmt = DEFAULT_VIDEO_FORMAT
    
    # Save video to artifact
    fname = f"video.{fmt}"
    with artifact.writeable_file_path(fname) as fp:
        if isinstance(obj, VideoFileClip) and hasattr(obj, "filename"):
            src_fmt = get_format_from_filename(obj.filename)
            if src_fmt == fmt:
                # Same format, just copy the file
                shutil.copy(obj.filename, fp)
            else:
                # Need to convert format
                write_video(fp, obj)
        else:
            # General VideoClip, write it
            write_video(fp, obj)
    
    # Get encoded files
    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)
        for k, v in artifact.path_contents.items()
    }
    
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "moviepy.video.VideoClip.VideoClip"},
        "files": encoded_path_contents,
    }
    
    return result


def deserialize_video(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize a MoviePy VideoClip."""
    if not VIDEO_AVAILABLE:
        return None
    
    if data.get("_type") != "CustomWeaveType":
        return None
    
    if data.get("weave_type", {}).get("type") != "moviepy.video.VideoClip.VideoClip":
        return None
    
    # Reconstruct artifact from files
    files = data.get("files", {})
    artifact = MemTraceFilesArtifact(files, metadata={})
    
    # Find video file
    video_files = [f for f in artifact.path_contents if f.startswith("video.")]
    if not video_files:
        raise ValueError("No video file found in artifact")
    
    path = artifact.path(video_files[0])
    return VideoFileClip(path)


def is_video_clip(obj: Any) -> bool:
    """Check if object is a MoviePy VideoClip."""
    if not VIDEO_AVAILABLE:
        return False
    return isinstance(obj, VideoClip)


# Content handlers
def serialize_content(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a Content object."""
    if not CONTENT_AVAILABLE:
        return {"_type": "FallbackString", "_value": str(obj)}
    
    # Create artifact for file storage
    artifact = MemTraceFilesArtifact()
    
    # Save content using its save method
    from weave.type_handlers.Content.content import save as content_save
    content_save(obj, artifact, "content")
    
    # Get encoded files
    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)
        for k, v in artifact.path_contents.items()
    }
    
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
        "files": encoded_path_contents,
    }
    
    return result


def deserialize_content(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize a Content object."""
    if not CONTENT_AVAILABLE:
        return None
    
    if data.get("_type") != "CustomWeaveType":
        return None
    
    if data.get("weave_type", {}).get("type") != "weave.type_wrappers.Content.content.Content":
        return None
    
    # Reconstruct artifact from files
    files = data.get("files", {})
    artifact = MemTraceFilesArtifact(files, metadata={})
    
    # Load content using its load method
    from weave.type_handlers.Content.content import load as content_load
    return content_load(artifact, "content")


def is_content(obj: Any) -> bool:
    """Check if object is a Content object."""
    if not CONTENT_AVAILABLE:
        return False
    return isinstance(obj, Content)


# File handlers
def serialize_file(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize a File object."""
    if not FILE_AVAILABLE:
        return {"_type": "FallbackString", "_value": str(obj)}
    
    # Create artifact for file storage
    artifact = MemTraceFilesArtifact()
    
    # Save file using its save method
    from weave.type_handlers.File.file import save as file_save
    file_save(obj, artifact, "file")
    
    # Get encoded files
    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)
        for k, v in artifact.path_contents.items()
    }
    
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "weave.type_handlers.File.file.File"},
        "files": encoded_path_contents,
    }
    
    return result


def deserialize_file(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize a File object."""
    if not FILE_AVAILABLE:
        return None
    
    if data.get("_type") != "CustomWeaveType":
        return None
    
    if data.get("weave_type", {}).get("type") != "weave.type_handlers.File.file.File":
        return None
    
    # Reconstruct artifact from files
    files = data.get("files", {})
    artifact = MemTraceFilesArtifact(files, metadata={})
    
    # Load file using its load method
    from weave.type_handlers.File.file import load as file_load
    return file_load(artifact, "file")


def is_file(obj: Any) -> bool:
    """Check if object is a File object."""
    if not FILE_AVAILABLE:
        return False
    return isinstance(obj, File)


def register_media_handlers():
    """Register all media and special type handlers."""
    # DateTime (high priority as it's a common type)
    register(
        datetime.datetime,
        serialize_datetime,
        deserialize_datetime,
        priority=80
    )
    
    # Markdown
    if MARKDOWN_AVAILABLE:
        register(
            Markdown,
            serialize_markdown,
            deserialize_markdown,
            priority=70,
            check_func=is_markdown
        )
    
    # Video
    if VIDEO_AVAILABLE:
        register(
            VideoClip,
            serialize_video,
            deserialize_video,
            priority=70,
            check_func=is_video_clip
        )
    
    # Content
    if CONTENT_AVAILABLE:
        register(
            Content,
            serialize_content,
            deserialize_content,
            priority=70,
            check_func=is_content
        )
    
    # File
    if FILE_AVAILABLE:
        register(
            File,
            serialize_file,
            deserialize_file,
            priority=70,
            check_func=is_file
        )