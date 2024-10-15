"""Defines the custom Image weave type."""

import logging
import os
from functools import cached_property
from io import BufferedReader

from pydantic import BaseModel

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact

dependencies_met = False

try:
    from openai._legacy_response import HttpxBinaryResponseContent
    from openai._response import StreamedBinaryAPIResponse

    dependencies_met = True
except ImportError:
    pass


logger = logging.getLogger(__name__)


# TODO: this doesn't work if the stream is closed, as in if the user
# has already consumed the content of the stream, either writing it
# to a file or iterating through the bytes. We need to intercept
# the stream and save it to the artifact in chunks while also piping
# the data to the client as it comes in.
def save_stream(
    obj: StreamedBinaryAPIResponse, artifact: MemTraceFilesArtifact, name: str
) -> None:
    try:
        with artifact.new_file("audio.wav", binary=True) as f:
            for data in obj.iter_bytes():
                f.write(data)  # type: ignore
    except Exception as e:
        logger.error(f"Error saving audio: {e}")


def load_stream(artifact: MemTraceFilesArtifact, name: str) -> BufferedReader:
    path = artifact.path("audio.wav")
    # Stream from artifact?
    return open(path, "rb")


# Save the non-stream version of the httpx response
def save_httpx(
    obj: HttpxBinaryResponseContent, artifact: MemTraceFilesArtifact, name: str
) -> None:
    with artifact.new_file("audio.wav", binary=True) as f:
        for data in obj.iter_bytes():
            f.write(data)  # type: ignore


def load_httpx(artifact: MemTraceFilesArtifact, name: str) -> BufferedReader:
    path = artifact.path("audio.wav")
    return open(path, "rb")


class AudioFile(BaseModel):
    model_config: dict = {"arbitrary_types_allowed": True}

    path: str | os.PathLike[str]

    @property
    def content_type(self) -> str:
        if isinstance(self.path, str):
            return self.path.split(".")[-1]
        else:
            return str(self.path).split(".")[-1]

    @cached_property
    def content(self) -> bytes:
        return open(self.path, "rb").read()


# We can either automatically convert audio files to this AudioFile
# type in weave_client.py, which the serializer will pick up, or users
# will have to manually convert to this type before saving.
def save_audio_file(obj: AudioFile, artifact: MemTraceFilesArtifact, name: str) -> None:
    # for now only save to wav
    with artifact.new_file("audio.wav", binary=True) as f:
        f.write(obj.content)  # type: ignore


def load_audio_file(artifact: MemTraceFilesArtifact, name: str) -> AudioFile:
    path = artifact.path("audio.wav")
    return AudioFile(
        path=path, content_type="audio/wav", content=open(path, "rb").read()
    )


def register() -> None:
    serializer.register_serializer(StreamedBinaryAPIResponse, save_stream, load_stream)
    serializer.register_serializer(HttpxBinaryResponseContent, save_httpx, load_httpx)
    serializer.register_serializer(AudioFile, save_audio_file, load_audio_file)
