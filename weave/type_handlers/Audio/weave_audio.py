import wave
from enum import Enum
import os
import io
from typing import Any, Optional, Union, BinaryIO
from pathlib import Path

from .adapter import AudioBackendAdapter, AudioBackendError
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact

class AudioFormat(str, Enum):
    MP3 = "mp4"
    M4A = "m4a"
    WAV = "wav"
    OGG = "ogg"
    FLAC = "flac"
    UNSUPPORTED = "unsupported"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def _missing_(cls, value: Any) -> "AudioFormat":
        return cls('unsupported')


DEFAULT_AUDIO_FORMAT = AudioFormat.WAV


def get_format_from_filename(filename: str) -> AudioFormat:
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
        return AudioFormat.UNSUPPORTED

    # Get the extension without the dot
    return AudioFormat(filename[last_dot + 1 :])

class Audio:
    """A wrapper class for audio data that works with various backend libraries."""
    
    DEFAULT_FORMAT = 'wav'
    
    def __init__(self, 
                 audio_data: Union[bytes, BinaryIO, str, Path, Any], 
                 audio_format: Optional[str] = None):
        """
        Initialize an Audio object.
        
        Args:
            audio_data: The audio data. Can be:
                - bytes: Raw audio data
                - file-like object: With audio data
                - str: Path to an audio file
                - Path: pathlib.Path to an audio file
                - Any: Audio object from backend library
            audio_format: Optional format extension (e.g., 'wav', 'mp3'). 
                          If not provided, will attempt to detect from the data.
        """
        self._audio_adapter = AudioBackendAdapter()
        self._buffer = io.BytesIO()
        self.audio_format = audio_format or self.DEFAULT_FORMAT
        
        # Handle different input types
        if isinstance(audio_data, bytes):
            self._from_bytes(audio_data)
        elif hasattr(audio_data, 'read') and callable(audio_data.read):
            self._from_file_object(audio_data)
        elif isinstance(audio_data, str) and os.path.exists(audio_data):
            self._from_file_path(audio_data)
        elif isinstance(audio_data, Path) and audio_data.exists():
            self._from_file_path(audio_data)
        elif isinstance(audio_data, wave.Wave_read):
            self._from_wave_object(audio_data)
        else:
            # Assume it's a backend library audio object
            self._from_backend_object(audio_data)
    
    def _from_bytes(self, data: bytes) -> None:
        """Initialize from raw bytes."""
        self._buffer.write(data)
        self._buffer.seek(0)
        
    def _from_file_object(self, file_obj: BinaryIO) -> None:
        """Initialize from a file-like object."""
        self._buffer.write(file_obj.read())
        self._buffer.seek(0)
        
    def _from_file_path(self, file_path: Union[str, Path]) -> None:
        """Initialize from a file path."""
        # Handle both string paths and Path objects
        if isinstance(file_path, Path):
            file_ext = file_path.suffix[1:].lower()
            path_str = str(file_path)
        else:
            file_ext = os.path.splitext(file_path)[1][1:].lower()
            path_str = file_path
        
        # If file has a supported extension like mp3, stream bytes directly
        try:
            format_enum = AudioFormat(file_ext)
            if format_enum != AudioFormat.UNSUPPORTED:
                with open(path_str, 'rb') as f:
                    self._buffer.write(f.read())
                    self._buffer.seek(0)
                self.audio_format = file_ext
                return
        except ValueError:
            pass
            # Not a recognized format, continue with backend adapters
            
        # If file doesn't have an extension or not supported, try the backend
        try:
            # Try to read using the backend adapter
            data, samplerate = self._audio_adapter.read(path_str)
            
            # Get format from file extension if not provided, or use default
            if self.audio_format == self.DEFAULT_FORMAT:
                self.audio_format = file_ext or self.DEFAULT_FORMAT
            
            # Write to buffer in the detected format
            self._audio_adapter.write(self._buffer, data, samplerate, format=self.audio_format)
            self._buffer.seek(0)
            
        except AudioBackendError:
            # Fallback to direct file reading if no backend is available
            with open(path_str, 'rb') as f:
                self._buffer.write(f.read())
                self._buffer.seek(0)
                # Use the file extension as the format or default
                if self.audio_format == self.DEFAULT_FORMAT:
                    self.audio_format = file_ext or self.DEFAULT_FORMAT
    
    def _from_wave_object(self, wave_obj: wave.Wave_read) -> None:
        """Initialize from a wave.Wave_read object."""
        # Save the original position
        original_position = wave_obj.tell()
        
        # Rewind to read all frames
        wave_obj.rewind()
        frames = wave_obj.readframes(wave_obj.getnframes())
        params = wave_obj.getparams()
        
        # Create a new wave file in the buffer
        with wave.open(self._buffer, 'wb') as wav_file:
            wav_file.setframerate(params.framerate)
            wav_file.setnchannels(params.nchannels)
            wav_file.setsampwidth(params.sampwidth)
            wav_file.setcomptype(params.comptype, params.compname)
            wav_file.writeframes(frames)
        
        # Restore the original position of the input wave object
        wave_obj.setpos(original_position)
        
        # Reset buffer position
        self._buffer.seek(0)
        
        # Set format to wav
        self.audio_format = 'wav'
    
    def _from_backend_object(self, audio_obj: Any) -> None:
        """Initialize from a backend library audio object."""
        # First check if it's a numpy array
        try:
            # Check if numpy is available, and if audio_obj is an ndarray
            import importlib.util
            numpy_spec = importlib.util.find_spec("numpy")
            
            if numpy_spec is not None:
                import numpy as np
                if isinstance(audio_obj, np.ndarray):
                    # For numpy arrays, assume standard sample rate if not provided
                    samplerate = getattr(audio_obj, 'samplerate', 44100)
                    self._audio_adapter.write(self._buffer, audio_obj, samplerate, format=self.audio_format)
                    self._buffer.seek(0)
                    return
            elif hasattr(audio_obj, '__class__') and audio_obj.__class__.__name__ == 'ndarray':
                # If we get here, it's likely an ndarray but numpy isn't available
                raise ImportError(
                    "NumPy is required to load audio from ndarray objects. "
                    "Please install numpy to use this functionality."
                )
        except ImportError as e:
            # Re-raise import errors with the specific message
            raise ImportError(
                "NumPy is required to load audio from ndarray objects. "
                "Please install numpy to use this functionality."
            ) from e
            
        try:
            # Identify which backend and handle appropriately
            backend_name = self._audio_adapter.backend_name
            
            if backend_name == 'soundfile':
                # For SoundFile objects
                audio_obj.seek(0)
                data = audio_obj.read()
                self._audio_adapter.write(self._buffer, data, audio_obj.samplerate, format=self.audio_format)
            
            elif backend_name == 'pydub':
                # Export the AudioSegment to our buffer in the specified format
                audio_obj.export(self._buffer, format=self.audio_format)
            
            else:
                # Generic fallback - try to export to wav format
                self._audio_adapter.write(self._buffer, audio_obj, 
                                         getattr(audio_obj, 'samplerate', 
                                                getattr(audio_obj, 'frame_rate', 44100)), 
                                         format=self.audio_format)
            
            # Reset buffer position
            self._buffer.seek(0)
            
        except Exception as e:
            # If we can't handle this object type, raise a meaningful error
            raise ValueError(f"Failed to process audio object of type {type(audio_obj)}: {str(e)}")
    
    def get_bytes(self) -> bytes:
        """Get the raw audio bytes."""
        current_pos = self._buffer.tell()
        self._buffer.seek(0)
        data = self._buffer.read()
        self._buffer.seek(current_pos)
        return data
    
    def get_buffer(self) -> io.BytesIO:
        """Get the underlying BytesIO buffer."""
        return self._buffer
    
    def save_to_artifact(self, artifact: MemTraceFilesArtifact, name: str) -> None:
        """Save audio data to an artifact."""
        filename = f"audio.{self.audio_format}"
        with artifact.writeable_file_path(filename) as fp:
            with open(fp, 'wb') as f:
                f.write(self.get_bytes())
    
    @classmethod
    def load_from_artifact(cls, artifact: MemTraceFilesArtifact, name: str) -> 'Audio':
        """Load audio data from an artifact."""
        # Try to find any audio file in the artifact
        for ext in AudioFormat:
            filename = f"audio.{ext.value}"
            path = artifact.path(filename)
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    return cls(f.read(), audio_format=ext)
        
        # Fallback to the default wav file
        path = artifact.path("audio.wav")
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return cls(f.read(), audio_format='wav')
        
        raise FileNotFoundError("No audio file found in artifact")
