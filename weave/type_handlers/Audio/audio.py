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
    cast,
    get_args,
)

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
SUPPORTED_FORMATS_TYPE = Literal["mp3", "wav"]
SUPPORTED_FORMATS = cast(list[SUPPORTED_FORMATS_TYPE], sorted(get_args(SUPPORTED_FORMATS_TYPE)))
T = TypeVar("T", bound=SUPPORTED_FORMATS_TYPE)

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


def is_base64(data: Union[str, bytes, None]) -> bool:
    """
    Validates if a string is valid base64

    ^: Matches the beginning of the string.
    [A-Za-z0-9+/]{4}: Matches any group of four characters from the Base64 alphabet.
    (?:[A-Za-z0-9+/]{4})*: Matches zero or more occurrences of the four-character group.
    (?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=): Matches either a group of two characters followed by two equals signs (==), or a group of three characters followed by one equal sign (=).
    ?: Makes the optional padding part of the regex optional (0 or 1 occurrence).
    $: Matches the end of the string. 
    """

    if not data:
        return False

    pattern = "^(?:[a-za-z0-9+/]{4})*(?:[a-za-z0-9+/]{2}==|[a-za-z0-9+/]{3}=)?$"

    if isinstance(data, bytes):
        return bool(re.match(pattern.encode(), data))

    return bool(re.match(pattern, data))



class Audio(Generic[T]):
    """
    Audio class to handle audio data.
    Can be initialized with a file path or raw audio data with a format

    Direct initialization in Op pre or post-process function:

    From a file with ext:
    weave.Audio(path='some_file.mp3')

    Filename without ext + format:
    weave.Audio(path='some_file', fmt='mp3')

    Base64 encoded bytes (Like what LLM generations return) + format:
    weave.Audio(data=base64_str_or_bytes, fmt='mp3')

    Raw decoded audio bytes + format:
    with open('some_file.mp3', 'rb') as f:
        raw_audio_bytes = f.read()
    weave.Audio(data=raw_audio_bytes, fmt='mp3')


    Annotated initialization performed by SDK:

    def read_example(path_to_mp3: str) -> Annotated[str, weave.Audio]:
        return path_to_mp3

    def read_example(path_to_mp3: str) -> Annotated[bytes, weave.Audio[Literal["mp3"]]]:
        with open(path_to_mp3, "rb") as f:
            raw_audio_bytes = f.read()
        return raw_audio_bytes

    def gen_audio(prompt: str) -> Annotated[str, weave.Audio[Literal["mp3"]]]:
        completion = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "mp3"},
            messages=[
                {
                    "role": "user",
                    "content": "Is a golden retriever a good family dog?"
                }
            ]
        )

        return completion.choices[0].message.audio.data
    """

    # File Format
    fmt: SUPPORTED_FORMATS_TYPE

    # Raw audio data bytes
    data: bytes

    def __init__(
        self,
        data: bytes,
        fmt: T,
    ) -> None:
        self.data = data
        self.fmt = fmt

    @classmethod
    def _from_base64(cls, data: Union[str, bytes], fmt: T) -> "Audio":
        data = base64.b64decode(data)
        return cls(data=data, fmt=fmt)

    @classmethod
    def from_data(cls, data: Union[str, bytes], fmt: T) -> "Audio":
        if is_base64(data):
            return cls._from_base64(data, fmt)
        elif isinstance(data, str):
            data = data.encode()
        return cls(data=data, fmt=fmt)

    @classmethod
    def from_path(cls, path: Union[str, bytes, Path, os.PathLike]) -> "Audio":
        if isinstance(path, bytes):
            path = path.decode()

        if not os.path.exists(path):
            raise ValueError(f"File {path} does not exist")

        fmt_str = get_format_from_filename(str(path))

        if fmt_str in SUPPORTED_FORMATS:
            fmt: SUPPORTED_FORMATS_TYPE = fmt_str
        else:
            raise ValueError(f"Invalid file path {path}, file must end in one of: mp3 or wav")


        data = open(path, "rb").read()
        return cls(data=data, fmt=cast(T, fmt))

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
            return Audio.from_path(path=path)

    raise ValueError("No audio found for artifact")


def is_audio_instance(obj: Any) -> bool:
    return isinstance(obj, (wave.Wave_read, Audio))


def register() -> None:
    # Register the serializers for the various audio types
    serializer.register_serializer(Audio, save, load)
    serializer.register_serializer(wave.Wave_read, save, load)
