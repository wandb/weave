import wave

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

AUDIO_FILE_NAME = "audio.wav"


def save(obj: wave.Wave_read, artifact: MemTraceFilesArtifact, name: str) -> None:
    original_frame_position = obj.tell()
    obj.rewind()
    frames = obj.readframes(obj.getnframes())
    params = obj.getparams()
    with artifact.writeable_file_path(AUDIO_FILE_NAME) as fp:
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


def load(artifact: MemTraceFilesArtifact, name: str) -> wave.Wave_read:
    path = artifact.path(AUDIO_FILE_NAME)
    return wave.open(path, "rb")


def register() -> None:
    serializer.register_serializer(wave.Wave_read, save, load)
