"""Serialization handlers for media and special types using the new registration system."""

from __future__ import annotations

import datetime
from typing import Any

from weave.trace.serialization.handlers.handler_registry import handler
from weave.trace.serialization.registry import SerializationContext


# DateTime handler
@handler(datetime.datetime, priority=80, name="DateTime")
class DateTimeHandler:
    @staticmethod
    def serialize(obj: datetime.datetime, context: SerializationContext) -> dict[str, Any]:
        """Serialize a datetime object to ISO format with timezone information."""
        # If the datetime object is naive (has no timezone), assume UTC
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=datetime.timezone.utc)
        
        return {
            "_type": "datetime",
            "value": obj.isoformat()
        }
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> datetime.datetime:
        """Deserialize an ISO format string back to a datetime object with timezone."""
        if data.get("_type") != "datetime":
            raise ValueError(f"Expected datetime type, got {data.get('_type')}")
        
        return datetime.datetime.fromisoformat(data["value"])


# Markdown handler (conditional)
try:
    from rich.markdown import Markdown
    
    @handler(Markdown, priority=70, name="RichMarkdown")
    class MarkdownHandler:
        @staticmethod
        def serialize(obj: Markdown, context: SerializationContext) -> dict[str, Any]:
            """Serialize a Rich Markdown object."""
            result = {
                "_type": "Markdown",
                "markup": obj.markup,
            }
            
            if hasattr(obj, "code_theme") and obj.code_theme:
                result["code_theme"] = obj.code_theme
            
            return result
        
        @staticmethod
        def deserialize(data: dict[str, Any], context: SerializationContext) -> Markdown:
            """Deserialize a Rich Markdown object."""
            if data.get("_type") != "Markdown":
                raise ValueError(f"Expected Markdown type, got {data.get('_type')}")
            
            kwargs = {"markup": data.get("markup", "")}
            if "code_theme" in data:
                kwargs["code_theme"] = data["code_theme"]
            
            return Markdown(**kwargs)

except ImportError:
    pass  # Rich not available


# Video handler (conditional)
try:
    from moviepy.editor import VideoClip, VideoFileClip
    from weave.type_handlers.Video.video import (
        VideoFormat,
        DEFAULT_VIDEO_FORMAT,
        get_format_from_filename,
        write_video,
    )
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
    import shutil
    
    def is_video_clip(obj: Any) -> bool:
        """Check if object is a MoviePy VideoClip."""
        return isinstance(obj, VideoClip)
    
    @handler(is_video_clip, priority=70, name="VideoClip")
    class VideoHandler:
        @staticmethod
        def serialize(obj: VideoClip, context: SerializationContext) -> dict[str, Any]:
            """Serialize a MoviePy VideoClip."""
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
            
            return {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "moviepy.video.VideoClip.VideoClip"},
                "files": encoded_path_contents,
            }
        
        @staticmethod
        def deserialize(data: dict[str, Any], context: SerializationContext) -> VideoClip:
            """Deserialize a MoviePy VideoClip."""
            if data.get("_type") != "CustomWeaveType":
                raise ValueError("Expected CustomWeaveType")
            
            if data.get("weave_type", {}).get("type") != "moviepy.video.VideoClip.VideoClip":
                raise ValueError("Expected VideoClip type")
            
            # Reconstruct artifact from files
            files = data.get("files", {})
            artifact = MemTraceFilesArtifact(files, metadata={})
            
            # Find video file
            video_files = [f for f in artifact.path_contents if f.startswith("video.")]
            if not video_files:
                raise ValueError("No video file found in artifact")
            
            path = artifact.path(video_files[0])
            return VideoFileClip(path)

except ImportError:
    pass  # MoviePy not available


# Content handler (conditional)
try:
    from weave.type_wrappers.Content.content import Content
    from weave.type_handlers.Content.content import save as content_save, load as content_load
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
    
    def is_content(obj: Any) -> bool:
        """Check if object is a Content object."""
        return isinstance(obj, Content)
    
    @handler(is_content, priority=70, name="Content")
    class ContentHandler:
        @staticmethod
        def serialize(obj: Content, context: SerializationContext) -> dict[str, Any]:
            """Serialize a Content object."""
            # Create artifact for file storage
            artifact = MemTraceFilesArtifact()
            
            # Save content using its save method
            content_save(obj, artifact, "content")
            
            # Get encoded files
            encoded_path_contents = {
                k: (v.encode("utf-8") if isinstance(v, str) else v)
                for k, v in artifact.path_contents.items()
            }
            
            return {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
                "files": encoded_path_contents,
            }
        
        @staticmethod
        def deserialize(data: dict[str, Any], context: SerializationContext) -> Content:
            """Deserialize a Content object."""
            if data.get("_type") != "CustomWeaveType":
                raise ValueError("Expected CustomWeaveType")
            
            if data.get("weave_type", {}).get("type") != "weave.type_wrappers.Content.content.Content":
                raise ValueError("Expected Content type")
            
            # Reconstruct artifact from files
            files = data.get("files", {})
            artifact = MemTraceFilesArtifact(files, metadata={})
            
            # Load content using its load method
            return content_load(artifact, "content")

except ImportError:
    pass  # Content not available


# File handler (conditional)
try:
    from weave.type_handlers.File.file import File
    from weave.type_handlers.File.file import save as file_save, load as file_load
    from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
    
    def is_file(obj: Any) -> bool:
        """Check if object is a File object."""
        return isinstance(obj, File)
    
    @handler(is_file, priority=70, name="File")
    class FileHandler:
        @staticmethod
        def serialize(obj: File, context: SerializationContext) -> dict[str, Any]:
            """Serialize a File object."""
            # Create artifact for file storage
            artifact = MemTraceFilesArtifact()
            
            # Save file using its save method
            file_save(obj, artifact, "file")
            
            # Get encoded files
            encoded_path_contents = {
                k: (v.encode("utf-8") if isinstance(v, str) else v)
                for k, v in artifact.path_contents.items()
            }
            
            return {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "weave.type_handlers.File.file.File"},
                "files": encoded_path_contents,
            }
        
        @staticmethod
        def deserialize(data: dict[str, Any], context: SerializationContext) -> File:
            """Deserialize a File object."""
            if data.get("_type") != "CustomWeaveType":
                raise ValueError("Expected CustomWeaveType")
            
            if data.get("weave_type", {}).get("type") != "weave.type_handlers.File.file.File":
                raise ValueError("Expected File type")
            
            # Reconstruct artifact from files
            files = data.get("files", {})
            artifact = MemTraceFilesArtifact(files, metadata={})
            
            # Load file using its load method
            return file_load(artifact, "file")

except ImportError:
    pass  # File not available


def register_media_handlers():
    """Register all media and special type handlers."""
    # The decorator-based handlers auto-register via handler_registry
    from weave.trace.serialization.handlers.handler_registry import register_pending_handlers
    register_pending_handlers()