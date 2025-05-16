from __future__ import annotations

import json
import wave
from typing import (
    Any,
)

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from weave.trace.type_wrappers import Audio

METADATA_FILE_NAME = "_metadata.json"
AUDIO_FILE_PREFIX = "audio."

def audio_filename(ext: str) -> str:
    """Generate the standard filename for an audio file.

    Args:
        ext: The file extension (e.g., '.wav', '.mp3')

    Returns:
        str: The formatted filename
    """
    return f"{AUDIO_FILE_PREFIX}{ext}"

def export_wave_read(obj: wave.Wave_read, fp: str, name: str) -> None:
    """Export a wave.Wave_read object to a file.

    Args:
        obj: The wave.Wave_read object to export
        fp: File path to write to
        name: Name for the audio file

    Note:
        This preserves the original frame position of the wave reader.
    """
    original_frame_position = obj.tell()
    obj.rewind()
    frames = obj.readframes(obj.getnframes())
    params = obj.getparams()
    with wave.open(fp, "w") as wav_file:
        # Exclude nframes param, it is often set as the maximum number of frames
        # which bumps into the 4GB max file size when creating the wave.Wave_write
        # header on close.
        wav_file.setframerate(params.framerate)
        wav_file.setnchannels(params.nchannels)
        wav_file.setsampwidth(params.sampwidth)
        wav_file.setcomptype(params.comptype, params.compname)
        wav_file.writeframes(frames)
    # Rewind to the original position
    obj.setpos(original_frame_position)


def save(
    obj: wave.Wave_read | Audio, artifact: MemTraceFilesArtifact, name: str
) -> None:
    """Save an audio object to a trace files artifact.

    Args:
        obj: The audio object to save (either wave.Wave_read or Audio)
        artifact: The artifact to save the audio to
        name: Name for the audio file in the artifact
    """
    with artifact.writeable_file_path(METADATA_FILE_NAME) as metadata_path:
        obj_module = obj.__module__
        obj_class = obj.__class__.__name__
        with open(metadata_path, "w") as f:
            metadata = {"_type": f"{obj_module}.{obj_class}"}
            json.dump(metadata, f)

    if isinstance(obj, wave.Wave_read):
        with artifact.writeable_file_path(audio_filename(".wav")) as fp:
            return export_wave_read(obj, fp, name)

    with artifact.writeable_file_path(audio_filename(obj.format)) as fp:
        obj.export(fp)


def load(artifact: MemTraceFilesArtifact, name: str) -> wave.Wave_read | Audio:
    """Load an audio object from a trace files artifact.

    Args:
        artifact: The artifact containing the audio data
        name: Name of the audio file in the artifact

    Returns:
        Either a wave.Wave_read object or an Audio object, depending on the stored type

    Raises:
        ValueError: If no audio is found in the artifact
    """
    pytype = None
    if artifact.path_contents.get(METADATA_FILE_NAME):
        with open(artifact.path(METADATA_FILE_NAME)) as f:
            pytype = json.load(f).get("_type")

    for filename in artifact.path_contents:
        path = artifact.path(filename)
        if filename.startswith(AUDIO_FILE_PREFIX):
            if (
                pytype is None and filename.endswith(".wav")
            ) or pytype == "wave.Wave_read":
                return wave.open(path, "rb")
            return Audio.from_path(path=path)

    raise ValueError("No audio found for artifact")


def is_audio_instance(obj: Any) -> bool:
    """Check if an object is an audio instance.

    Args:
        obj: The object to check

    Returns:
        bool: True if the object is a wave.Wave_read or Audio instance
    """
    return isinstance(obj, (wave.Wave_read, Audio))


def register() -> None:
    """Register serializers for audio types with the Weave serialization system.

    This function must be called to enable serialization of Audio and wave.Wave_read objects.
    """
    # Register the serializers for the various audio types
    serializer.register_serializer(Audio, save, load, is_audio_instance)
    serializer.register_serializer(wave.Wave_read, save, load)
