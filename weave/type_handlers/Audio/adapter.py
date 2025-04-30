"""Audio file handling adapter that selects available backends."""
import importlib.util
from typing import Any, Tuple, Union
import warnings
import io
from pathlib import Path


class AudioBackendError(Exception):
    """Exception raised when no suitable audio backend is available."""
    pass


class AudioBackendAdapter:
    """Adapter that selects from available audio processing backends."""
    _initialized: bool

    def __init__(self):
        self._backend = None
        self._backend_name = None
        self._find_available_backend()

    def _check_module_exists(self, module_name: str) -> bool:
        """Check if a module can be imported."""
        spec = importlib.util.find_spec(module_name)
        return spec is not None

    def _find_available_backend(self) -> None:
        """Find an available audio backend."""
        # Order of preference for backends
        backends = [
            ("soundfile", self._init_soundfile),
            ("pydub", self._init_pydub)
        ]

        for name, init_func in backends:
            if self._check_module_exists(name):
                try:
                    init_func()
                    self._backend_name = name
                    self._initialized = True
                    return
                except Exception as e:
                    warnings.warn(f"Failed to initialize {name} backend: {str(e)}")

        # If we get here, no backend was successfully initialized
        raise AudioBackendError(
            "No audio backend available. Please install one of: soundfile, librosa, or pydub."
        )

    def _init_soundfile(self) -> None:
        """Initialize soundfile backend."""
        import soundfile as sf
        
        def _sf_write(file_path, data, samplerate, **kwargs):
            """Handle different file_path types for soundfile."""
            if isinstance(file_path, (str, Path)):
                return sf.write(file_path, data, samplerate, **kwargs)
            elif isinstance(file_path, io.BytesIO):
                return sf.write(file_path, data, samplerate, **kwargs)
            else:
                raise TypeError(f"Unsupported file_path type: {type(file_path)}")
        
        self._backend = {
            "module": sf,
            "read": lambda file_path, **kwargs: sf.read(file_path),
            "write": _sf_write,
            "info": lambda file_path: sf.info(file_path)
        }

    def _init_pydub(self) -> None:
        """Initialize pydub backend."""
        from pydub import AudioSegment
        import numpy as np

        def _pydub_read(file_path, **kwargs):
            audio = AudioSegment.from_file(file_path)
            samples = np.array(audio.get_array_of_samples())

            # Convert to float32 normalized between -1 and 1
            if audio.sample_width > 1:
                samples = samples.astype(np.float32) / (1 << (8 * audio.sample_width - 1))

            # Convert to mono if stereo
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))

            return samples, audio.frame_rate

        def _pydub_write(file_path, data, samplerate, **kwargs):
            import os
            
            # Get format from kwargs or try to determine from file_path
            format = kwargs.get('format')
            
            if format is None and isinstance(file_path, str):
                format = os.path.splitext(file_path)[1][1:]  # Get format from extension
            elif format is None and isinstance(file_path, Path):
                format = file_path.suffix[1:]  # Get format from extension
            elif format is None:
                format = 'wav'  # Default format for BytesIO
            
            # Convert float to int16
            if data.dtype == np.float32 or data.dtype == np.float64:
                data = (data * (1 << 15)).astype(np.int16)

            # Create AudioSegment
            channels = 2 if len(data.shape) > 1 and data.shape[1] == 2 else 1

            if channels == 2:
                # Stereo
                segment = AudioSegment(
                    data.tobytes(),
                    frame_rate=samplerate,
                    sample_width=data.dtype.itemsize,
                    channels=2
                )
            else:
                # Mono
                segment = AudioSegment(
                    data.tobytes(),
                    frame_rate=samplerate,
                    sample_width=data.dtype.itemsize,
                    channels=1
                )

            # Handle different file_path types
            if isinstance(file_path, (str, Path)):
                segment.export(file_path, format=format)
            elif isinstance(file_path, io.BytesIO):
                segment.export(file_path, format=format)
            else:
                raise TypeError(f"Unsupported file_path type: {type(file_path)}")

        def _pydub_info(file_path):
            audio = AudioSegment.from_file(file_path)
            import os

            return type('PydubInfo', (), {
                'samplerate': audio.frame_rate,
                'frames': len(audio),
                'format': os.path.splitext(file_path)[1][1:],
                'subtype': f'PCM_{audio.sample_width * 8}',
                'duration': len(audio) / 1000.0  # pydub uses milliseconds
            })

        self._backend = {
            "module": AudioSegment,
            "read": _pydub_read,
            "write": _pydub_write,
            "info": _pydub_info
        }

    @property
    def backend_name(self) -> str:
        """Get the name of the active backend."""
        if self._backend_name is None:
            raise AudioBackendError("No audio backend available.")
        return self._backend_name

    @property
    def module(self) -> Any:
        """Get the backend module."""
        if self._backend is None:
            raise AudioBackendError("No audio backend available.")
        return self._backend["module"]

    def read(self, file_path: str, **kwargs) -> Tuple[Any, int]:
        """Read an audio file and return samples and sample rate."""
        if self._backend is None:
            raise AudioBackendError("No audio backend available.")
        return self._backend["read"](file_path, **kwargs)

    def write(self, file_path: Union[str, io.BytesIO, Path], data: Any, samplerate: int, **kwargs) -> None:
        """
        Write audio data to a file or buffer.
        
        Args:
            file_path: Path to output file or BytesIO buffer
            data: Audio data to write
            samplerate: Sample rate of the audio data
            **kwargs: Additional arguments to pass to the backend
        """
        if self._backend is None:
            raise AudioBackendError("No audio backend available.")
        return self._backend["write"](file_path, data, samplerate, **kwargs)

    def info(self, file_path: str) -> Any:
        """Get information about an audio file."""
        if self._backend is None:
            raise AudioBackendError("No audio backend available.")
        return self._backend["info"](file_path)
