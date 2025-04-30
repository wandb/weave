import wave

from typing import TYPE_CHECKING, Any, Union, Protocol
from enum import Enum
import os
import shutil
from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from .utils import DEFAULT_VIDEO_FORMAT, AudioFile, AudioFormat, SUPPORTED_FORMATS, get_format_from_filename

try:
    import pydub
    has_pydub = True
except ImportError:
    has_pydub = False

if TYPE_CHECKING:
    import pydub


class SupportsAudioSegmentExport(Protocol):
    def export(self, out_f=None, format='mp3', codec=None, bitrate=None, parameters=None, tags=None, id3v2_version='4', cover=None):
        ...

DEFAULT_AUDIO_FORMAT = AudioFormat.MP3

AudioType = Union[wave.Wave_read, AudioFile, "pydub.AudioSegment"]


def save_wave(obj: wave.Wave_read, artifact: MemTraceFilesArtifact, name: str) -> None:
    original_frame_position = obj.tell()
    obj.rewind()
    frames = obj.readframes(obj.getnframes())
    params = obj.getparams()
    with artifact.writeable_file_path('audio.wav') as fp:
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
    if isinstance(obj, AudioFile):
        exists = os.path.exists(obj.path)
        if not exists:
            raise ValueError(f"Audio file does not exist: {obj.path}")
        ext = obj.extension
        # If it's not supported we can't copy it directly
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported audio format: {ext} - Supported formats are: {' '.join(SUPPORTED_FORMATS)}")
        fname = f"audio.{ext}"
        with artifact.writeable_file_path(fname) as fp:
            # Copy the file to the artifact
            obj.export(fp)
    elif isinstance(obj, "pydub.AudioSegment"):
        obj.export(artifact.writeable_file_path(f"audio.{DEFAULT_VIDEO_FORMAT}"), format=DEFAULT_VIDEO_FORMAT)
    else:
        # Object is a wave.Wave_read object
        save_wave(obj, artifact, name)


def load(artifact: MemTraceFilesArtifact, name: str) -> wave.Wave_read | pydub.AudioSegment:
    for filename in artifact.path_contents:
        path = artifact.path(filename)
        if filename.startswith("video."):
            fmt = get_format_from_filename(filename)
            if fmt == AudioFormat.UNSUPPORTED:
                raise ValueError(f"Unsupported audio format: {filename} - Supported formats are: {' '.join(SUPPORTED_FORMATS)}")
            elif fmt != AudioFormat.WAV:
                if not has_pydub:
                    raise ValueError(f"Pydub is required to retrieve {fmt.value} audio files")
                # If the file is in a supported format, we can load it directly
                return pydub.AudioSegment.from_file(path, format=fmt.value)
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
    serializer.register_serializer(wave.Wave_read, save, load)
