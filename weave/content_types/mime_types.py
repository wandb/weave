from __future__ import annotations

import mimetypes
from typing import Protocol, Literal, List, Dict, TypeVar, get_args, cast

try:
    import magic
    MAGIC_AVAILABLE = True
    # Check if libmagic is actually working
    try:
        magic.Magic(mime=True) # Test instantiation
    except magic.MagicException as e:
        # This can happen if python-magic is installed but libmagic is not found or broken
        print(f"Warning: python-magic is installed, but libmagic seems to be missing or broken: {e}. Falling back to standard mimetypes.")
        MAGIC_AVAILABLE = False
except ImportError:
    MAGIC_AVAILABLE = False
    print("Info: python-magic not found. Falling back to standard mimetypes library for MIME detection.")


# --- MIME Type Literals ---
AudioMimeTypes = Literal[
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/aac", "audio/flac", "audio/ogg"
]
VideoMimeTypes = Literal[
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"
]
ImageMimeTypes = Literal[
    "image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp"
]
PdfMimeTypes = Literal["application/pdf"]
JsonMimeTypes = Literal["application/json"]
YamlMimeTypes = Literal["application/yaml", "text/yaml", "application/x-yaml", "text/x-yaml"]
CsvMimeTypes = Literal["text/csv"]
MarkdownMimeTypes = Literal["text/markdown", "text/x-markdown"]
PlainTextMimeTypes = Literal["text/plain"]
PythonMimeTypes = Literal["application/x-python-code", "text/x-python", "text/python"]
JavaScriptMimeTypes = Literal["application/javascript", "text/javascript"]
TypeScriptMimeTypes = Literal["application/typescript", "text/typescript", "text/x-typescript"]

# --- Central Registry for Media MIME Types ---
MEDIA_MIME_TYPE_REGISTRY: Dict[str, List[str]] = {
    "audio": sorted(list(set(get_args(AudioMimeTypes)))),
    "video": sorted(list(set(get_args(VideoMimeTypes)))),
    "image": sorted(list(set(get_args(ImageMimeTypes)))),
    "pdf": sorted(list(set(get_args(PdfMimeTypes)))),
    "json": sorted(list(set(get_args(JsonMimeTypes)))),
    "yaml": sorted(list(set(get_args(YamlMimeTypes)))),
    "csv": sorted(list(set(get_args(CsvMimeTypes)))),
    "markdown": sorted(list(set(get_args(MarkdownMimeTypes)))),
    "plaintext": sorted(list(set(get_args(PlainTextMimeTypes)))),
    "python": sorted(list(set(get_args(PythonMimeTypes)))),
    "javascript": sorted(list(set(get_args(JavaScriptMimeTypes)))),
    "typescript": sorted(list(set(get_args(TypeScriptMimeTypes)))),
}

# --- Preferred Extensions ---
PREFERRED_EXTENSIONS_FOR_MIME: Dict[str, str] = {
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/aac": ".aac",
    "audio/flac": ".flac", "audio/ogg": ".ogg",
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv", "video/webm": ".webm",
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/bmp": ".bmp", "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/json": ".json",
    "application/yaml": ".yaml", "text/yaml": ".yaml", "text/x-yaml": ".yml", "application/x-yaml": ".yml",
    "text/csv": ".csv",
    "text/markdown": ".md", "text/x-markdown": ".md",
    "text/plain": ".txt",
    "application/x-python-code": ".py", "text/x-python": ".py", "text/python": ".py",
    "application/javascript": ".js", "text/javascript": ".js",
    "application/typescript": ".ts", "text/typescript": ".ts", "text/x-typescript": ".ts",
}

# --- Mimetype System Initialization ---
def _initialize_mimetypes():
    """Initializes and enhances the mimetypes system."""
    mimetypes.init()
    # Add custom or ensure specific types (strict=False to avoid issues if already present, True to prepend)
    # For some, like .ts, the default might be video/mp2t, so we want to override.
    mimetypes.add_type("text/markdown", ".md", strict=True)
    mimetypes.add_type("text/yaml", ".yaml", strict=True)
    mimetypes.add_type("text/yaml", ".yml", strict=True) # Ensure .yml is also text/yaml
    mimetypes.add_type("text/x-python", ".py", strict=True)
    mimetypes.add_type("application/javascript", ".js", strict=True)
    mimetypes.add_type("text/x-typescript", ".ts", strict=True)
    mimetypes.add_type("application/typescript", ".ts", strict=True)
    mimetypes.add_type("text/csv", ".csv", strict=True)
    mimetypes.add_type("application/pdf", ".pdf", strict=True)
    mimetypes.add_type("application/json", ".json", strict=True)

_initialize_mimetypes()


# --- MimeDetector Protocol and Implementations ---
class MimeDetector(Protocol):
    """Protocol for MIME type detection strategies."""
    def guess_mime_from_path(self, path: str) -> str | None:
        """Guesses MIME type from a file path."""
        ...

    def guess_mime_from_buffer(self, buffer: bytes) -> str | None:
        """Guesses MIME type from a byte buffer."""
        ...

class PythonMagicMimeDetector(MimeDetector):
    """MIME detector using python-magic library."""
    def __init__(self):
        # Initialize magic instance for MIME types
        # This might raise magic.MagicException if libmagic is not found/setup correctly
        self._magic_mime = magic.Magic(mime=True)
        # It's good practice to also have one for uncompressed, if you need to differentiate
        # self._magic_uncompressed = magic.Magic(mime=True, uncompress=True)

    def guess_mime_from_path(self, path: str) -> str | None:
        try:
            return self._magic_mime.from_file(path)
        except magic.MagicException as e:
            print(f"PythonMagic Error (from_file: {path}): {e}")
            return None
        except FileNotFoundError: # magic.from_file can raise this
            raise
        except Exception as e: # Catch other potential issues
            print(f"Unexpected PythonMagic Error (from_file: {path}): {e}")
            return None


    def guess_mime_from_buffer(self, buffer: bytes) -> str | None:
        try:
            return self._magic_mime.from_buffer(buffer)
        except magic.MagicException as e:
            print(f"PythonMagic Error (from_buffer): {e}")
            return None
        except Exception as e: # Catch other potential issues
            print(f"Unexpected PythonMagic Error (from_buffer): {e}")
            return None

class StandardLibMimeDetector(MimeDetector):
    """MIME detector using Python's standard mimetypes library."""
    def guess_mime_from_path(self, path: str) -> str | None:
        # mimetypes.guess_type uses strict=True by default if the global files are used.
        # We use strict=True here to ensure our mimetypes.add_type calls are prioritized.
        mime_type, _ = mimetypes.guess_type(path, strict=True)
        return mime_type

    def guess_mime_from_buffer(self, buffer: bytes) -> str | None:
        # The standard mimetypes library cannot guess from a buffer.
        # For a more advanced fallback, one might try to infer from known file signatures
        # if the buffer is small and matches, but that's complex.
        # print("Warning: StandardLibMimeDetector cannot guess MIME type from buffer. Returning None.")
        return None


# --- Factory for MimeDetector ---
def get_mime_detector_instance() -> MimeDetector:
    """
    Returns an instance of the best available MIME detector.
    Prefers PythonMagicMimeDetector if python-magic and libmagic are available and working.
    Falls back to StandardLibMimeDetector otherwise.
    """
    if MAGIC_AVAILABLE:
        try:
            # Further check if magic can be instantiated, as MAGIC_AVAILABLE might be true
            # but the constructor could fail (e.g. if libmagic path is wrong after install)
            return PythonMagicMimeDetector()
        except Exception as e: # Catch broad exceptions during instantiation
            print(f"Warning: Failed to instantiate PythonMagicMimeDetector ({e}). Falling back to standard mimetypes.")
            # Fall through to standard lib if magic instantiation fails
    return StandardLibMimeDetector()

# --- Global MimeDetector Instance ---
# This instance will be used by the public API functions.
_current_mime_detector: MimeDetector = get_mime_detector_instance()
print(f"Info: Using MIME detector: {_current_mime_detector.__class__.__name__}")


# --- Public API Functions ---
def guess_mime_type_from_path(path: str) -> str | None:
    """
    Guesses the MIME type of a file using the configured detector.
    Args:
        path: The path to the file.
    Returns:
        The guessed MIME type string, or None if it cannot be determined.
    Raises:
        FileNotFoundError: If the path does not exist (can be raised by underlying detectors).
    """
    return _current_mime_detector.guess_mime_from_path(path)

def guess_mime_type_from_buffer(buffer: bytes) -> str | None:
    """
    Guesses the MIME type from a byte buffer using the configured detector.
    Note: Accuracy is higher with python-magic. Standard library will return None.
    Args:
        buffer: The byte buffer.
    Returns:
        The guessed MIME type string, or None.
    """
    return _current_mime_detector.guess_mime_from_buffer(buffer)

def get_supported_mime_types_for_category(media_category: str) -> List[str]:
    """Retrieves the list of supported MIME type strings for a given media category key."""
    mime_types = MEDIA_MIME_TYPE_REGISTRY.get(media_category.lower())
    return mime_types if mime_types is not None else []

def get_default_extension_for_mime(mime_type: str) -> str | None:
    """
    Gets a preferred file extension (including the leading dot) for a given MIME type.
    Args:
        mime_type: The MIME type string (e.g., "image/jpeg").
    Returns:
        The preferred extension (e.g., ".jpg") or None if not found.
    """
    normalized_mime_type = mime_type.lower()
    if normalized_mime_type in PREFERRED_EXTENSIONS_FOR_MIME:
        return PREFERRED_EXTENSIONS_FOR_MIME[normalized_mime_type]
    
    # Fallback to standard library if no preferred extension is listed
    # mimetypes.guess_extension also normalizes case.
    ext = mimetypes.guess_extension(normalized_mime_type, strict=True)
    return ext

# --- Generic TypeVar for MIME type string literals (used by Media class) ---
MimeT = TypeVar("MimeT", bound=str)

# --- Export specific MIME type Literals for direct use if needed ---
# This allows the Media subclasses to type hint their mime_type argument precisely.
__all__ = [
    "guess_mime_type_from_path",
    "guess_mime_type_from_buffer",
    "get_supported_mime_types_for_category",
    "get_default_extension_for_mime",
    "MimeT",
    "AudioMimeTypes", "VideoMimeTypes", "ImageMimeTypes", "PdfMimeTypes",
    "JsonMimeTypes", "YamlMimeTypes", "CsvMimeTypes", "MarkdownMimeTypes",
    "PlainTextMimeTypes", "PythonMimeTypes", "JavaScriptMimeTypes", "TypeScriptMimeTypes",
    "MEDIA_MIME_TYPE_REGISTRY", # Exposing for potential external use/inspection
    "PREFERRED_EXTENSIONS_FOR_MIME",
]
