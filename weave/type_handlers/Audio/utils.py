import wave

from typing import Any, Optional, Protocol, TypeVar, Union
from enum import Enum
import shutil
from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

try:
    from pydub import AudioSegment
    has_pydub = True
except ImportError:
    AudioSegment = None
    has_pydub = False

from os import PathLike
class AudioFormat(str, Enum):
    """
    These are NOT the list of formats we accept from the user
    Rather, these are the list of formats we can save to weave servers
    If we detect that the file is in these formats, we copy it over directly
    Otherwise, we encode it to one of these formats using ffmpeg (mp3 by default)
    """

    MP3 = "mp3"
    WAV = "wav"
    UNSUPPORTED = "unsupported"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: Any) -> "AudioFormat":
        return cls.UNSUPPORTED

SUPPORTED_FORMATS = [fmt.value for fmt in AudioFormat if fmt != AudioFormat.UNSUPPORTED]

DEFAULT_VIDEO_FORMAT = AudioFormat.MP3

def get_format_from_filename(filename: str) -> AudioFormat:
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
        return AudioFormat.UNSUPPORTED

    # Get the extension without the dot
    return AudioFormat(filename[last_dot + 1 :])

class AudioFile:
    path: str
    file_ext: AudioFormat

    def __init__(self, path: str, file_ext: Optional[str] = None) -> None:
        file_ext = AudioFormat(file_ext.lower()) if file_ext else get_format_from_filename(path)

        if file_ext == AudioFormat.UNSUPPORTED:
            raise ValueError(f"Unsupported or missing file format: {path} - Supported Extensions: {' '.join(SUPPORTED_FORMATS)}")
        self.path = path
        self.file_ext = file_ext

    @property
    def format(self) -> str:
        return self.file_ext.value

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return repr(self.path)

    def __fspath__(self):
        return str(self.path)

    def export(self, fp: str) -> None:
        shutil.copyfile(self.path, fp)
