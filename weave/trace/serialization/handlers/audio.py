"""Serialization handlers for audio types."""

from __future__ import annotations

import json
import wave
from typing import Any

from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.registry import SerializationContext, register

# Import Audio class if available
try:
    from weave.type_handlers.Audio.audio import (
        Audio,
        export_wave_read,
        audio_filename,
        METADATA_FILE_NAME,
    )
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    Audio = None


def serialize_wave_read(obj: wave.Wave_read, context: SerializationContext) -> dict[str, Any]:
    """Serialize a wave.Wave_read object."""
    # Create artifact for file storage
    artifact = MemTraceFilesArtifact()
    
    # Save metadata
    with artifact.writeable_file_path(METADATA_FILE_NAME) as metadata_path:
        obj_module = obj.__module__
        obj_class = obj.__class__.__name__
        with open(metadata_path, "w") as f:
            metadata = {"_type": f"{obj_module}.{obj_class}"}
            json.dump(metadata, f)
    
    # Save wave data
    with artifact.writeable_file_path(audio_filename("wav")) as fp:
        export_wave_read(obj, fp, "audio")
    
    # Get encoded files
    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)
        for k, v in artifact.path_contents.items()
    }
    
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "wave.Wave_read"},
        "files": encoded_path_contents,
    }
    
    return result


def deserialize_wave_read(data: dict[str, Any], context: SerializationContext) -> wave.Wave_read | None:
    """Deserialize a wave.Wave_read object."""
    if data.get("_type") != "CustomWeaveType":
        return None
    
    if data.get("weave_type", {}).get("type") != "wave.Wave_read":
        return None
    
    # Reconstruct artifact from files
    files = data.get("files", {})
    artifact = MemTraceFilesArtifact(files, metadata={})
    
    # Find audio file
    audio_files = [f for f in artifact.path_contents if f.startswith("audio.")]
    if not audio_files:
        raise ValueError("No audio file found in artifact")
    
    path = artifact.path(audio_files[0])
    return wave.open(path, "r")


def serialize_audio(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize an Audio object."""
    if not AUDIO_AVAILABLE:
        return {"_type": "FallbackString", "_value": str(obj)}
    
    # Create artifact for file storage
    artifact = MemTraceFilesArtifact()
    
    # Save metadata
    with artifact.writeable_file_path(METADATA_FILE_NAME) as metadata_path:
        obj_module = obj.__module__
        obj_class = obj.__class__.__name__
        with open(metadata_path, "w") as f:
            metadata = {"_type": f"{obj_module}.{obj_class}"}
            json.dump(metadata, f)
    
    # Save audio data
    with artifact.writeable_file_path(audio_filename(obj.format)) as fp:
        obj.export(fp)
    
    # Get encoded files
    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)
        for k, v in artifact.path_contents.items()
    }
    
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "weave.type_handlers.Audio.audio.Audio"},
        "files": encoded_path_contents,
    }
    
    return result


def deserialize_audio(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize an Audio object."""
    if not AUDIO_AVAILABLE:
        return None
    
    if data.get("_type") != "CustomWeaveType":
        return None
    
    if data.get("weave_type", {}).get("type") != "weave.type_handlers.Audio.audio.Audio":
        return None
    
    # Reconstruct artifact from files
    files = data.get("files", {})
    artifact = MemTraceFilesArtifact(files, metadata={})
    
    # Find audio file
    audio_files = [f for f in artifact.path_contents if f.startswith("audio.")]
    if not audio_files:
        raise ValueError("No audio file found in artifact")
    
    audio_file = audio_files[0]
    path = artifact.path(audio_file)
    return Audio.from_file(path)


def is_wave_read(obj: Any) -> bool:
    """Check if object is a wave.Wave_read."""
    return isinstance(obj, wave.Wave_read)


def is_audio(obj: Any) -> bool:
    """Check if object is an Audio object."""
    if not AUDIO_AVAILABLE:
        return False
    return isinstance(obj, Audio)


def register_audio_handlers():
    """Register all audio-related serialization handlers."""
    # Register wave.Wave_read handler
    register(
        wave.Wave_read,
        serialize_wave_read,
        deserialize_wave_read,
        priority=75,
        check_func=is_wave_read
    )
    
    # Register Audio handler if available
    if AUDIO_AVAILABLE:
        register(
            Audio,
            serialize_audio,
            deserialize_audio,
            priority=75,
            check_func=is_audio
        )