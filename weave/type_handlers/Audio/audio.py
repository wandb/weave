import base64
import json
import os
import re
import wave
from pathlib import Path
from typing import (
    Any,
    Generic,
    Literal,
    TypeVar,
    Union,
    get_args,
)

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

SupportedFormatType = Literal["mp3", "wav"]


def get_format_from_filename(filename: str) -> Union[str, None]:
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
        return None

    fmt = filename[last_dot + 1 :].lower()

    if not fmt in get_args(SupportedFormatType):
        return None

    return fmt


def is_base64(data: Union[str, bytes, None]) -> bool:
    # check if a string is base64 encoded.
    if not data:
        return False

    pattern = "^(?:[a-za-z0-9+/]{4})*(?:[a-za-z0-9+/]{2}==|[a-za-z0-9+/]{3}=)?$"

    if isinstance(data, bytes):
        return bool(re.match(pattern.encode(), data))

    return bool(re.match(pattern, data))


F = TypeVar("F", bound=SupportedFormatType)


class Audio(Generic[F]):
    # File Format
    fmt: str

    # Base64 encoded audio data
    data: str

    def __init__(
        self,
        path: Union[str, bytes, Path, os.PathLike, None] = None,
        data: Union[bytes, str, None] = None,
        fmt: Union[SupportedFormatType, None] = None,
    ):
        if not path and not (data and fmt):
            raise ValueError("Must provide either path or raw data and format")
        elif data and not fmt:
            raise ValueError("Format is required when passing raw data")

        if path:
            if isinstance(path, bytes):
                path = path.decode()
            fmt_str = fmt or get_format_from_filename(str(path))

            if not fmt_str or fmt_str.lower() not in get_args(SupportedFormatType):
                raise ValueError(
                    f"Invalid file path {path}, file must end in one of: mp3 or wav"
                )
            if not os.path.exists(path):
                raise ValueError(f"File {path} does not exist")
            self.data = base64.b64encode(open(path, "rb").read()).decode("ascii")
            self.fmt = fmt_str
            return

        elif data and fmt:
            # Case 1: Receive encoded audio data
            is_encoded = is_base64(data)

            # Case 2: Receive raw audio data
            if not is_encoded:
                if isinstance(data, str):
                    bytes_data = data.encode()
                    self.data = base64.b64encode(bytes_data).decode("ascii")
                    self.fmt = fmt
                    return
                else:
                    self.data = base64.b64encode(data).decode("ascii")
                    self.fmt = fmt
                    return

    def export(self, path: Union[str, bytes, Path, os.PathLike]) -> None:
        with open(path, "wb") as f:
            f.write(base64.b64decode(self.data))


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
