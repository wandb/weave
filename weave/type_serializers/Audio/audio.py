from io import BufferedReader
import wave

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact

dependencies_met = False

try:
    from openai._legacy_response import HttpxBinaryResponseContent

    dependencies_met = True
except ImportError:
    pass


def save_httpx(
    obj: HttpxBinaryResponseContent, artifact: MemTraceFilesArtifact, name: str
) -> None:
    with artifact.new_file("audio.wav", binary=True) as f:
        for data in obj.iter_bytes():
            f.write(data)  # type: ignore


def load_httpx(artifact: MemTraceFilesArtifact, name: str) -> BufferedReader:
    path = artifact.path("audio.wav")
    return open(path, "rb")


def save_wave(obj: wave.Wave_read, artifact: MemTraceFilesArtifact, name: str) -> None:
    num_frames = obj.getnframes()
    frames = obj.readframes(num_frames)
    with artifact.writeable_file_path("audio.wav") as fp:
        wav_file = wave.Wave_write(fp)
        wav_file.setnchannels(obj.getnchannels())
        wav_file.setsampwidth(obj.getsampwidth())
        wav_file.setframerate(obj.getframerate())
        wav_file.writeframes(frames)


def load_wave(artifact: MemTraceFilesArtifact, name: str) -> wave.Wave_read:
    path = artifact.path("audio.wav")
    return wave.open(path, "rb")


def register() -> None:
    serializer.register_serializer(HttpxBinaryResponseContent, save_httpx, load_httpx)
    serializer.register_serializer(wave.Wave_read, save_wave, load_wave)
