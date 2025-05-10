import json
import wave
from typing import (
    Any,
    Union,
)
from .utils import Audio

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact


def save(
    obj: Union[wave.Wave_read, Audio], artifact: MemTraceFilesArtifact, name: str
) -> None:
    with artifact.writeable_file_path("metadata.json") as metadata_path:
        obj_module = obj.__module__
        obj_class = obj.__class__.__name__
        with open(metadata_path, "w") as f:
            metadata = {"_type": f"{obj_module}.{obj_class}"}
            json.dump(metadata, f)

    if isinstance(obj, wave.Wave_read):
        original_frame_position = obj.tell()
        obj.rewind()
        frames = obj.readframes(obj.getnframes())
        params = obj.getparams()
        with artifact.writeable_file_path("audio.wav") as fp:
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
    else:
        with artifact.writeable_file_path(f"audio.{obj.fmt}") as fp:
            obj.export(fp)


def load(artifact: MemTraceFilesArtifact, name: str) -> "wave.Wave_read | Audio":
    pytype = None
    if artifact.path_contents.get("metadata.json"):
        with open(artifact.path("metadata.json")) as f:
            pytype = json.load(f).get("_type")

    for filename in artifact.path_contents:
        path = artifact.path(filename)
        if filename.startswith("audio."):
            if (not pytype and filename.endswith(".wav")) or pytype == "wave.Wave_read":
                return wave.open(path, "rb")
            return Audio(path=path)

    raise ValueError("No audio found for artifact")


def is_audio_instance(obj: Any) -> bool:
    return isinstance(obj, (wave.Wave_read, Audio))


def register() -> None:
    # Register the serializers for the various audio types
    serializer.register_serializer(Audio, save, load)
    serializer.register_serializer(wave.Wave_read, save, load)
