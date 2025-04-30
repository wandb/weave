from typing_extensions import Annotated
import wave
import os
from typing import Any, Union
from pydub import AudioSegment

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from weave.type_handlers.Audio.audio_wrapper import AudioHandler, Audio

def save(obj: Union[Audio, wave.Wave_read, AudioHandler], artifact: MemTraceFilesArtifact, name: str) -> None:
    if isinstance(obj, wave.Wave_read):
        original_frame_position = obj.tell()
        obj.rewind()
        frames = obj.readframes(obj.getnframes())
        params = obj.getparams()
        with artifact.writeable_file_path('audio.wav') as fp:
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
    # Handle objects from audio backends
    else:
        try:
            if not isinstance(obj, AudioHandler):
                handler = AudioHandler(obj)
            else:
                handler = obj
            # Convert and save as wav to maintain compatibility
            with artifact.writeable_file_path(f"audio.{handler.audio_format}") as fp:
                handler.data.seek(0)
                handler.export(fp)
        except Exception as e:
            raise ValueError(f"Failed to save audio object: {str(e)}.")


def load(artifact: MemTraceFilesArtifact, name: str) -> None:
    return None
    # path = artifact.path(AUDIO_FILE_NAME)
    # 
    # # Always try to open as a wave file first for backward compatibility
    # try:
    #     return wave.open(path, "rb")
    # except wave.Error:
    #     # If it's not a valid wave file, try using the audio adapter
    #     try:
    #         return audio_adapter.read(path)[0]
    #     except AudioBackendError:
    #         raise ValueError(
    #             "Cannot load non-wave audio file. Please install one of these libraries to support additional audio formats: "
    #             "soundfile, librosa, or pydub."
    #         )
    #     except Exception as e:
    #         raise ValueError(f"Failed to load audio file: {str(e)}")

def instance_check(obj: Any) -> bool:
    return obj.__metadata__ == "weave.type_handlers.Audio.audio_wrapper.AudioHandler" or isinstance(obj, AudioHandler) or isinstance(obj, wave.Wave_read)

def register() -> None:
    # Register the wave.Wave_read serializer for backward compatibility
    serializer.register_serializer(wave.Wave_read, save, load)
