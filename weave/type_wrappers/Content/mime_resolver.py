from __future__ import annotations

import mimetypes

try:
    import magic
    try:
        # Try to create a magic instance to check if the library is installed + functional
        _MAGIC_INSTANCE_FOR_CHECK = magic.Magic(mime=True)
        MAGIC_LIB_AVAILABLE = True
        del _MAGIC_INSTANCE_FOR_CHECK  # Clean up
    except magic.MagicException as e:
        MAGIC_LIB_AVAILABLE = False

except ImportError:
    MAGIC_LIB_AVAILABLE = False

def guess_extension(mime_type: str) -> str | None:
    ext = mimetypes.guess_extension(mime_type)
    return ext.lstrip(".") if ext else None

def guess_mime_type(**kwargs) -> str | None:
    mime_type = None

    if filename := kwargs.get("filename"):
        mime_type = mimetypes.guess_type(filename)[0]
    elif extension := kwargs.get("extension"):
        mime_type = mimetypes.guess_type(f"file.{extension}")[0]

    if mime_type is None and "buffer" in kwargs:
        if not MAGIC_LIB_AVAILABLE:  # Check if libmagic itself is usable
            raise RuntimeError(
                "Failed to determine MIME type from file extension and cannot infer from data"
                "MIME type detection from raw data requires a functional python-magic library "
                "and its underlying libmagic dependency. Please install or configure them correctly."
            )
        magic_detector = magic.Magic(mime=True)
        return magic_detector.from_buffer(kwargs.get("buffer"))

    return None

def is_mime_type(mime_string):
    """
    Checks if a string is a valid MIME type.

    Args:
        mime_string: The string to check.

    Returns:
        True if the string is a valid MIME type, False otherwise.
    """
    if not isinstance(mime_string, str):
        return False
    return mimetypes.guess_type(mime_string)[0] is not None

def is_valid_extension(extension):
    """
    Checks if a string is a valid file extension.
    Args:
        extension: The string to check.
    Returns:
        True if the string is a valid file extension, False otherwise.
    """
    if not isinstance(extension, str):
        return False

    # Ensure we have a leading dot
    extension = f".{extension.lstrip('.')}"
    return mimetypes.guess_extension(extension) is not None
