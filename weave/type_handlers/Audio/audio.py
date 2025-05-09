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
    """
    Attempts to decode the data as base64 in validation mode
    Otherwise, returns the data as is if bytes, or encodes to bytes if str
    """
    try:
        data = base64.b64decode(data, validate=True)
    except binascii.Error:
        pass

    if isinstance(data, str):
        data = data.encode("utf-8")

    return data


class Audio(Generic[T]):
    """
    Audio class to handle audio data.
    Can be initialized with a file path or raw audio data with a format

    Direct initialization in Op pre or post-process function:

    From a file with ext:
    weave.Audio(path='some_file.mp3')

    Filename without ext + format:
    weave.Audio(path='some_file', format='mp3')

    Base64 encoded bytes (Like what LLM generations return) + format:
    weave.Audio(data=base64_str_or_bytes, format='mp3')

    Raw decoded audio bytes + format:
    with open('some_file.mp3', 'rb') as f:
        raw_audio_bytes = f.read()
    weave.Audio(data=raw_audio_bytes, format='mp3')


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
    format: SUPPORTED_FORMATS_TYPE

    # Raw audio data bytes
    data: bytes

    # TODO: Should format accept any string and coerce here instead?
    # It ruins the type info, but it's more usable
    def __init__(
        self,
        data: bytes,
        format: SUPPORTED_FORMATS_TYPE,
        validate_base64: bool = True,
    ) -> None:
        if validate_base64:
            data = try_decode(data)
        self.data = data
        self.format = cast(SUPPORTED_FORMATS_TYPE, format)

    @classmethod
    def from_data(cls, data: str | bytes, format: SUPPORTED_FORMATS_TYPE) -> Audio:
        data = try_decode(data)

        # We already attempted to decode it as base64 and coerced to bytes so we can skip that step
        return cls(data=data, format=format, validate_base64=False)

    @classmethod
    def from_path(cls, path: str | bytes | Path | os.PathLike) -> Audio:
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
        with open(path, "wb") as f:
            f.write(self.data)


def save(
    obj: wave.Wave_read | Audio, artifact: MemTraceFilesArtifact, name: str
) -> None:
    with artifact.writeable_file_path(METADATA_FILE_NAME) as metadata_path:
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
        with artifact.writeable_file_path(audio_filename(".wav")) as fp:
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
        return

    with artifact.writeable_file_path(audio_filename(obj.format)) as fp:
        obj.export(fp)


def load(artifact: MemTraceFilesArtifact, name: str) -> wave.Wave_read | Audio:
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
    return isinstance(obj, (wave.Wave_read, Audio))


def register() -> None:
    # Register the serializers for the various audio types
    serializer.register_serializer(Audio, save, load, is_audio_instance)
    serializer.register_serializer(wave.Wave_read, save, load)
