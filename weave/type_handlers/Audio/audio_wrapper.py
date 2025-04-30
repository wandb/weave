import os
import io
from pathlib import Path
from typing import Protocol, Union, Optional, TypeVar, Generic, Any, TYPE_CHECKING, runtime_checkable
from enum import Enum, EnumMeta

from pydub import audio_segment
try:
    from pydub import AudioSegment
    has_pydub = True
except ImportError:
    has_pydub = False

if TYPE_CHECKING:
    from pydub import AudioSegment

class AudioFormat(str, Enum):
    MP3 = "mp4"
    M4A = "m4a"
    WAV = "wav"
    AAC = "aac"
    OGG = "ogg"
    FLAC = "flac"
    UNSUPPORTED = "unsupported"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: Any) -> "AudioFormat":
        return cls('unsupported')

SUPPORTED_FORMATS = [fmt.value for fmt in AudioFormat]

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

def is_pathlike(data: Any) -> bool:
    return isinstance(data, (str, Path, os.PathLike))

def is_byteslike(data: Any) -> bool:
    return isinstance(data, (str, Path))

class Readable(Protocol):
    def read(self) -> bytes:
        ...

@runtime_checkable
class SupportsToBytes(Protocol):
    def tobytes(self) -> bytes:
        ...

@runtime_checkable
class SupportsRead(Protocol):
    def read(self, size: int = -1) -> bytes:
        ...

Audio = Union[
    str,
    Path,
    tuple[str, str],
    tuple[Path, str],
    tuple[bytes, str],
    tuple[SupportsToBytes, str],
    tuple[SupportsRead, str]
]
# Define type variables
AudioSource = TypeVar('AudioSource', bound=Audio)

class AudioHandler(Generic[AudioSource]):
    """Class for annotating audio data from various sources."""
    data: io.BytesIO
    audio_format: str

    def __init__(
        self,
        data: AudioSource,
    ):
        """
        Initialize an Audio object.

        Args:
            data: The audio data. Can be:
                - str or Path: Path to an audio file
                - bytes: Raw audio data
                - BinaryIO: File-like object with audio data
            audio_format: Required when data is bytes or BinaryIO. The audio format (e.g., 'mp3', 'wav').
                    Must be one of the supported exts.

        Raises:
            TypeError: If data is not a supported type
            ValueError: If ext is required but not provided or if format is not supported
        """
        if isinstance(data, (str, Path)):
            audio_format = get_format_from_filename(str(data))
            if not audio_format or audio_format not in SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported audio_format: {audio_format}. Supported formats: {', '.join(SUPPORTED_FORMATS)}")
            with open(data, 'rb') as f:
                data_bytes = f.read()
                self.data = io.BytesIO(data_bytes)
            self.audio_format = audio_format
            return

        if isinstance(data, tuple):
            data_source, audio_format = data
            if isinstance(data_source, (str, Path)):
                audio_format = audio_format or get_format_from_filename(str(data_source))
                if not audio_format or audio_format not in SUPPORTED_FORMATS:
                    formats = [fmt.value for fmt in AudioFormat]
                    raise ValueError(f"Unsupported audio_format: {audio_format}. Supported formats: {', '.join(SUPPORTED_FORMATS)}")
                self.audio_format = audio_format
                with open(data_source, 'rb') as f:
                    data_bytes = f.read()
                    self.data = io.BytesIO(data_bytes)
            else:
                data_source = data_source
                if not audio_format:
                    formats = [fmt.value for fmt in AudioFormat]
                    raise ValueError(f"audio_format must be specified when data is bytes or file-like object. Supported formats: {', '.join(formats)}")
                elif audio_format not in AudioFormat:
                    formats = [fmt.value for fmt in AudioFormat]
                    raise ValueError(f"Unsupported audio_format: {audio_format}. Supported formats: {', '.join(formats)}")
                self.audio_format = audio_format
                if isinstance(data_source, bytes):
                    self.data = io.BytesIO(data_source)
                elif issubclass(data_source.__class__, SupportsToBytes):
                    data_bytes: bytes = getattr(data_source, 'tobytes')()
                    self.data = io.BytesIO(data_bytes)
                elif issubclass(data_source.__class__, SupportsRead):
                    data_bytes: bytes = getattr(data_source, 'read')()
                    self.data = io.BytesIO(data_bytes)

    def get_data(self) -> io.BytesIO:
        """Return the audio data."""
        return self.data

    def get_ext(self) -> str:
        """Return the audio ext."""
        return self.audio_format

    def export(self, path: str) -> None:
        """Write the audio data to a file."""
        # We do this because it handles some headers from the audio file for us
        audio_segment = AudioSegment.from_file(self.data, format=self.audio_format)
        with open(path, 'wb') as f:
            audio_segment.export(f, format=self.audio_format)

    def __repr__(self) -> str:
        if isinstance(self.data, (str, Path)):
            return f"Audio(path='{self.data}', audio_format='{self.audio_format}')"
        elif isinstance(self.data, bytes):
            return f"Audio(bytes of length {len(self.data)}, audio_format='{self.audio_format}')"
        else:
            return f"Audio(BinaryIO, audio_format='{self.audio_format}')"
