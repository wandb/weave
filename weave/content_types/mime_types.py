from __future__ import annotations

import mimetypes
from typing import (  # Removed Protocol and cast as they are no longer needed here
    Dict,
    List,
    Literal,
    TypeVar,
    get_args,
)

# --- Attempt to import python-magic ---
try:
    import magic

    _MAGIC_MODULE_IMPORTED = True
    # Check if libmagic is actually working by attempting to instantiate
    try:
        _MAGIC_INSTANCE_FOR_CHECK = magic.Magic(mime=True)
        MAGIC_LIB_AVAILABLE = True
        del _MAGIC_INSTANCE_FOR_CHECK  # Clean up
    except magic.MagicException as e:
        print(
            f"Warning: python-magic module is installed, but libmagic seems to be missing or broken: {e}. "
            "MIME detection from buffer will not be available."
        )
        MAGIC_LIB_AVAILABLE = False
except ImportError:
    _MAGIC_MODULE_IMPORTED = False
    MAGIC_LIB_AVAILABLE = False
    print(
        "Info: python-magic module not found. "
        "MIME detection from buffer will not be available."
    )


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
# Added text/plain as a fallback from python-magic for simple files
YamlMimeTypes = Literal[
    "application/yaml", "text/yaml", "application/x-yaml", "text/x-yaml", "text/plain"
]
CsvMimeTypes = Literal["text/csv"]
# Added text/plain as a fallback from python-magic for simple files
MarkdownMimeTypes = Literal["text/markdown", "text/x-markdown", "text/plain"]
PlainTextMimeTypes = Literal["text/plain"]
# Added text/x-script.python for python-magic output
PythonMimeTypes = Literal[
    "application/x-python-code", "text/x-python", "text/python", "text/x-script.python"
]
# Added text/plain as a fallback from python-magic for simple files
JavaScriptMimeTypes = Literal["application/javascript", "text/javascript", "text/plain"]
# Added text/plain as a fallback from python-magic for simple files
TypeScriptMimeTypes = Literal[
    "application/typescript", "text/typescript", "text/x-typescript", "text/plain"
]


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
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "audio/ogg": ".ogg",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "video/webm": ".webm",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/json": ".json",
    "application/yaml": ".yaml",
    "text/yaml": ".yaml",
    "text/x-yaml": ".yml",
    "application/x-yaml": ".yml",
    "text/csv": ".csv",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "text/plain": ".txt",
    "application/x-python-code": ".py",
    "text/x-python": ".py",
    "text/python": ".py",
    "text/x-script.python": ".py",
    "application/javascript": ".js",
    "text/javascript": ".js",
    "application/typescript": ".ts",
    "text/typescript": ".ts",
    "text/x-typescript": ".ts",
}


# --- Mimetype System Initialization ---
def _initialize_mimetypes():
    """Initializes and enhances the mimetypes system."""
    mimetypes.init()
    mimetypes.add_type("text/markdown", ".md", strict=True)
    mimetypes.add_type("text/yaml", ".yaml", strict=True)
    mimetypes.add_type("text/yaml", ".yml", strict=True)
    mimetypes.add_type("text/x-python", ".py", strict=True)
    mimetypes.add_type("application/javascript", ".js", strict=True)
    mimetypes.add_type(
        "text/x-typescript", ".ts", strict=True
    )  # Prioritize this for .ts
    mimetypes.add_type("application/typescript", ".ts", strict=True)
    mimetypes.add_type("text/csv", ".csv", strict=True)
    mimetypes.add_type("application/pdf", ".pdf", strict=True)
    mimetypes.add_type("application/json", ".json", strict=True)


_initialize_mimetypes()


# --- Public API Functions ---
def guess_mime_type_from_filename(filename: str) -> str | None:
    """
    Guesses the MIME type of a file using ONLY the standard `mimetypes` library
    based on the filename extension.

    Args:
        filename: The filename (e.g., "my_document.pdf").

    Returns:
        The guessed MIME type string (e.g., "application/pdf"), or None if it cannot be determined.
    """
    if not isinstance(filename, str):
        raise TypeError("filename must be a string.")
    # strict=True ensures that user-added types via mimetypes.add_type are preferred.
    mime_type, _ = mimetypes.guess_type(filename, strict=True)
    return mime_type


def guess_mime_type_from_buffer(buffer: bytes) -> str | None:
    """
    Guesses the MIME type from a byte buffer using ONLY the `python-magic` library.

    Args:
        buffer: The byte buffer of the file content.

    Returns:
        The guessed MIME type string (e.g., "image/jpeg"), or None if `python-magic`
        cannot determine it or encounters an error during detection.

    Raises:
        RuntimeError: If `python-magic` module is not installed or `libmagic` is not available/functional.
    """
    if not MAGIC_LIB_AVAILABLE:  # Check if libmagic itself is usable
        raise RuntimeError(
            "MIME type detection from buffer requires a functional python-magic library "
            "and its underlying libmagic dependency. Please install or configure them correctly."
        )
    if not isinstance(buffer, bytes):
        raise TypeError("buffer must be a bytes object.")

    try:
        # It's good practice to create the magic instance when needed,
        # or manage it if used very frequently in a performance-critical path.
        # For this function, creating it on-demand is safer.
        magic_detector = magic.Magic(mime=True)
        return magic_detector.from_buffer(buffer)
    except magic.MagicException as e:
        # This can happen for various reasons, e.g., buffer is too short,
        # or libmagic encounters an issue with the data.
        print(f"python-magic could not determine MIME type from buffer: {e}")
        return None
    except Exception as e:  # Catch any other unexpected errors from magic
        print(f"An unexpected error occurred while using python-magic from buffer: {e}")
        return None


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

    ext = mimetypes.guess_extension(normalized_mime_type, strict=True)
    return ext


# --- Generic TypeVar for MIME type string literals (used by Content class) ---
MimeT = TypeVar("MimeT", bound=str)

# --- Export specific MIME type Literals for direct use if needed ---
__all__ = [
    "guess_mime_type_from_filename",  # Updated function name
    "guess_mime_type_from_buffer",
    "get_supported_mime_types_for_category",
    "get_default_extension_for_mime",
    "MimeT",
    "AudioMimeTypes",
    "VideoMimeTypes",
    "ImageMimeTypes",
    "PdfMimeTypes",
    "JsonMimeTypes",
    "YamlMimeTypes",
    "CsvMimeTypes",
    "MarkdownMimeTypes",
    "PlainTextMimeTypes",
    "PythonMimeTypes",
    "JavaScriptMimeTypes",
    "TypeScriptMimeTypes",
    "MEDIA_MIME_TYPE_REGISTRY",
    "PREFERRED_EXTENSIONS_FOR_MIME",
    "MAGIC_LIB_AVAILABLE",  # Exporting for potential external checks
]
