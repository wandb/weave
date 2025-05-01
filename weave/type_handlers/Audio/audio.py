import os
import wave
from typing import TYPE_CHECKING, Any, Union

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

from .utils import (
    DEFAULT_VIDEO_FORMAT,
    SUPPORTED_FORMATS,
    AudioFile,
    AudioFormat,
    get_format_from_filename,
)

try:
    import pydub

    has_pydub = True
except ImportError:
    has_pydub = False

if TYPE_CHECKING:
    import pydub

DEFAULT_AUDIO_FORMAT = AudioFormat.MP3

AudioType = Union[wave.Wave_read, AudioFile, "pydub.AudioSegment"]


def save_wave(obj: wave.Wave_read, artifact: MemTraceFilesArtifact, name: str) -> None:
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


def save(obj: AudioType, artifact: MemTraceFilesArtifact, name: str) -> None:
    # Represents a wrapped audio file path which should be copied directly
    if isinstance(obj, AudioFile):
        # If file does not exist we can't copy it directly
        exists = os.path.exists(obj.path)
        if not exists:
            raise ValueError(f"Audio file does not exist: {obj.path}")

        ext = obj.file_ext
        # If it's not supported we can't copy it directly
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported audio format: {ext} - Supported formats are: {' '.join(SUPPORTED_FORMATS)}"
            )

        # Copy the file to the artifact
        fname = f"audio.{ext}"
        with artifact.writeable_file_path(fname) as fp:
            obj.export(fp)

    elif has_pydub and isinstance(obj, pydub.AudioSegment):
        with artifact.writeable_file_path(f"audio.{DEFAULT_VIDEO_FORMAT}") as fp:
            obj.export(
                fp,
                format=DEFAULT_VIDEO_FORMAT.value,
            )
    elif isinstance(obj, wave.Wave_read):
        # Object is a wave.Wave_read object
        save_wave(obj, artifact, name)
    else:
        # Should never occur, just to make type checker happy
        raise ValueError(
            "Recieved pydub.AudioSegment but failed to resolve pydub import"
        )


def load(
    artifact: MemTraceFilesArtifact, name: str
) -> "wave.Wave_read | pydub.AudioSegment":
    for filename in artifact.path_contents:
        path = artifact.path(filename)
        if filename.startswith("audio."):
            fmt = get_format_from_filename(filename)
            if fmt == AudioFormat.UNSUPPORTED:
                raise ValueError(
                    f"Unsupported audio format: {filename} - Supported formats are: {' '.join(SUPPORTED_FORMATS)}"
                )

            elif fmt != AudioFormat.WAV:
                try:
                    # We do this so that we can give the user a more descriptive error message.
                    # The client running the load op might not be the same as the client that ran save
                    # Since this fn is serialized for isolated execution, we need an env check
                    from pydub import AudioSegment

                    return AudioSegment.from_file(path, format=fmt.value)
                except ImportError:
                    raise ValueError(
                        f"Pydub is required to retrieve {fmt.value} audio files"
                    )
            else:
                # File is in WAV format, return it as a wave.Wave_read object
                wave_file = wave.open(path, "rb")
                return wave_file

    raise ValueError("No audio found for artifact")


def is_audio_instance(obj: Any) -> bool:
    if has_pydub:
        return isinstance(obj, (AudioFile, pydub.AudioSegment, wave.Wave_read))
    else:
        return isinstance(obj, (AudioFile, wave.Wave_read))


def register() -> None:
    # Register the serializers for the various audio types
    serializer.register_serializer(AudioFile, save, load)
    serializer.register_serializer(wave.Wave_read, save, load)
    if has_pydub:
        serializer.register_serializer(pydub.AudioSegment, save, load)
