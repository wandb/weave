import wave
import os
from typing import Any, Union

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from .adapter import AudioBackendAdapter, AudioBackendError

AUDIO_FILE_NAME = "audio.wav"
audio_adapter = AudioBackendAdapter()


def save(obj: Union[wave.Wave_read, Any], artifact: MemTraceFilesArtifact, name: str) -> None:
    # Handle wave.Wave_read objects
    if isinstance(obj, wave.Wave_read):
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
    # Handle objects from audio backends
    else:
        try:
            # Check if the object is from one of our supported backends
            backend_name = audio_adapter.backend_name
            
            # Try to get information about the audio object to verify it's a valid audio object
            # This implementation may need adjustment based on the actual type of obj
            if hasattr(obj, 'samplerate') or hasattr(obj, 'frame_rate') or hasattr(obj, 'getparams'):
                # Convert and save as wav to maintain compatibility
                with artifact.writeable_file_path(AUDIO_FILE_NAME) as fp:
                    if hasattr(obj, 'export'):  # pydub AudioSegment
                        obj.export(fp, format='wav')
                    elif hasattr(obj, 'write'):  # soundfile or similar
                        obj.write(fp)
                    else:
                        # Generic fallback approach
                        if hasattr(obj, 'get_array_of_samples'):  # pydub
                            import numpy as np
                            samples = np.array(obj.get_array_of_samples())
                            sr = obj.frame_rate
                        elif hasattr(obj, 'samplerate'):  # soundfile
                            samples = obj
                            sr = obj.samplerate
                        else:
                            raise ValueError(f"Unsupported audio object type: {type(obj)}")
                        
                        with wave.open(fp, 'w') as wav_file:
                            wav_file.setnchannels(1 if len(samples.shape) == 1 else 2)
                            wav_file.setsampwidth(2)  # 16-bit
                            wav_file.setframerate(sr)
                            wav_file.writeframes(samples.tobytes())
            else:
                raise ValueError(f"Object doesn't appear to be a valid audio object: {type(obj)}")
        except Exception as e:
            raise ValueError(f"Failed to save audio object: {str(e)}. Please ensure you have one of these libraries installed: soundfile, librosa, or pydub.")


def load(artifact: MemTraceFilesArtifact, name: str) -> Any:
    path = artifact.path(AUDIO_FILE_NAME)
    
    # Always try to open as a wave file first for backward compatibility
    try:
        return wave.open(path, "rb")
    except wave.Error:
        # If it's not a valid wave file, try using the audio adapter
        try:
            return audio_adapter.read(path)[0]
        except AudioBackendError:
            raise ValueError(
                "Cannot load non-wave audio file. Please install one of these libraries to support additional audio formats: "
                "soundfile, librosa, or pydub."
            )
        except Exception as e:
            raise ValueError(f"Failed to load audio file: {str(e)}")


def register() -> None:
    # Register the wave.Wave_read serializer for backward compatibility
    serializer.register_serializer(wave.Wave_read, save, load)
    
    # Try to register other audio types if backends are available
    try:
        backend_name = audio_adapter.backend_name
        
        # Register backend-specific types
        if backend_name == 'soundfile':
            import soundfile as sf
            serializer.register_serializer(sf.SoundFile, save, load)
        elif backend_name == 'pydub':
            from pydub import AudioSegment
            serializer.register_serializer(AudioSegment, save, load)
        # librosa doesn't have a specific audio object type, it uses numpy arrays
    except AudioBackendError:
        # If no backend is available, only wave.Wave_read will be supported
        pass
