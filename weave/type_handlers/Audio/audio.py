from __future__ import annotations

import base64
import binascii
import json
import os
import wave
from pathlib import Path
from typing import (
    Any,
    Generic,
    Literal,
    TypeVar,
    cast,
    get_args,
)

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

METADATA_FILE_NAME = "_metadata.json"
AUDIO_FILE_PREFIX = "audio."

SUPPORTED_FORMATS_TYPE = Literal["mp3", "wav"]
SUPPORTED_FORMATS = cast(
    list[SUPPORTED_FORMATS_TYPE], sorted(get_args(SUPPORTED_FORMATS_TYPE))
)
T = TypeVar("T", bound=SUPPORTED_FORMATS_TYPE)


def audio_filename(ext: str) -> str:
    """Generate the standard filename for an audio file.

    Args:
        ext: The file extension (e.g., '.wav', '.mp3')

    Returns:
        str: The formatted filename
    """
    return f"{AUDIO_FILE_PREFIX}{ext}"


def get_format_from_filename(filename: str) -> str:
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
        return ""

    return filename[last_dot + 1 :].lower()


def try_decode(data: str | bytes) -> bytes:
    """Attempt to decode data as base64 or convert to bytes.

    This function tries to decode the input as base64 first. If that fails,
    it will return the data as bytes, converting if needed.

    Args:
        data: Input data as string or bytes, potentially base64 encoded

    Returns:
        bytes: The decoded data as bytes
    """
    try:
        data = base64.b64decode(data, validate=True)
    except binascii.Error:
        pass

    if isinstance(data, str):
        data = data.encode("utf-8")

    return data


class Audio(Generic[T]):
    """A class representing audio data in a supported format (wav or mp3).

    This class handles audio data storage and provides methods for loading from
    different sources and exporting to files.

    Attributes:
        format: The audio format (currently supports 'wav' or 'mp3')
        data: The raw audio data as bytes

    Args:
        data: The audio data (bytes or base64 encoded string)
        format: The audio format ('wav' or 'mp3')
        validate_base64: Whether to attempt base64 decoding of the input data

    Raises:
        ValueError: If audio data is empty or format is not supported
    """

    # File Format
    format: SUPPORTED_FORMATS_TYPE

    # Raw audio data bytes
    data: bytes

    def __init__(
        self,
        data: bytes,
        format: SUPPORTED_FORMATS_TYPE,
        validate_base64: bool = True,
    ) -> None:
        if len(data) == 0:
            raise ValueError("Audio data cannot be empty")

        if validate_base64:
            data = try_decode(data)

        self.data = data
        self.format = format

    @classmethod
    def from_data(cls, data: str | bytes, format: str) -> Audio:
        """Create an Audio object from raw data and specified format.

        Args:
            data: Audio data as bytes or base64 encoded string
            format: Audio format ('wav' or 'mp3')

        Returns:
            Audio: A new Audio instance

        Raises:
            ValueError: If format is not supported
        """
        data = try_decode(data)
        if not format in list(map(str, SUPPORTED_FORMATS)):
            raise ValueError("Unknown format {format}, must be one of: mp3 or wav")

        # We already attempted to decode it as base64 and coerced to bytes so we can skip that step
        return cls(
            data=data,
            format=cast(SUPPORTED_FORMATS_TYPE, format),
            validate_base64=False,
        )

    @classmethod
    def from_path(cls, path: str | bytes | Path | os.PathLike) -> Audio:
        """Create an Audio object from a file path.

        Args:
            path: Path to an audio file (must have .wav or .mp3 extension)

        Returns:
            Audio: A new Audio instance loaded from the file

        Raises:
            ValueError: If file doesn't exist or has unsupported extension
        """
        if isinstance(path, bytes):
            path = path.decode()

        if not os.path.exists(path):
            raise ValueError(f"File {path} does not exist")

        format_str = get_format_from_filename(str(path))
        if not format_str in list(map(str, SUPPORTED_FORMATS)):
            raise ValueError(
                f"Invalid file path {path}, file must end in one of: mp3 or wav"
            )

        data = open(path, "rb").read()
        return cls(data=data, format=cast(SUPPORTED_FORMATS_TYPE, format_str))

    def export(self, path: str | bytes | Path | os.PathLike) -> None:
        """Export audio data to a file.

        Args:
            path: Path where the audio file should be written
        """
        with open(path, "wb") as f:
            f.write(self.data)


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
        with artifact.writeable_file_path(audio_filename("wav")) as fp:
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
