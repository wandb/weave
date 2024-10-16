import wave

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact

AUDIO_FILE_NAME = "audio.wav"


def save(obj: wave.Wave_read, artifact: MemTraceFilesArtifact, name: str) -> None:
    frames = obj.readframes(obj.getnframes())
    params = obj.getparams()
    with artifact.writeable_file_path(AUDIO_FILE_NAME) as fp:
        wav_file = wave.open(fp, "wb")
        wav_file.setparams(params)
        wav_file.writeframes(frames)
        wav_file.close()
    obj.rewind()


def load(artifact: MemTraceFilesArtifact, name: str) -> wave.Wave_read:
    path = artifact.path(AUDIO_FILE_NAME)
    return wave.open(path, "rb")


def register() -> None:
    serializer.register_serializer(wave.Wave_read, save, load)
