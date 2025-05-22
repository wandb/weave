from __future__ import annotations

import mimetypes
from pathlib import Path
import magic

try:
    _MAGIC_INSTANCE_FOR_CHECK = magic.Magic(mime=True)
    MAGIC_LIB_AVAILABLE = True
    del _MAGIC_INSTANCE_FOR_CHECK  # Clean up
except magic.MagicException as e:
    MAGIC_LIB_AVAILABLE = False

def get_extension_from_mimetype(mimetype: str) -> str:
    extension = mimetypes.guess_extension(mimetype)
    if not extension:
        raise ValueError(f"Got mime-type {mimetype} but failed to resolve a valid extension")
    return extension

def guess_from_buffer(buffer: bytes) -> str | None:
    if not MAGIC_LIB_AVAILABLE:
        return None
    return magic.Magic(mime=True).from_buffer(buffer)

def guess_from_filename(filename: str) -> str | None:
    return mimetypes.guess_type(filename)[0]

def guess_from_extension(extension: str) -> str | None:
    filename = f"file.{extension.lstrip('.')}"
    return guess_from_filename(filename)

def guess_from_path(path: Path) -> str | None:
    mimetype = guess_from_filename(path.name)
    return mimetype


def get_mime_and_extension(**kwargs) -> tuple[str, str]:
    mimetype = kwargs.get("mimetype")
    extension = kwargs.get("extension")

    if mimetype and extension:
        return mimetype, extension
    elif mimetype and not extension:
        return mimetype, get_extension_from_mimetype(mimetype)

    for key in ["mimetype", "filename", "extension", "path", "buffer"]:
        if not key in kwargs or kwargs[key] is None:
            continue

        value = kwargs[key]

        if key == "mimetype":
            mimetype = value
        elif key == "filename":
            mimetype = guess_from_filename(value)
        elif key == "extension":
            mimetype = guess_from_extension(value)
            # Only set if we got a valid mime type from it
        elif key == "path":
            value = Path(value)
            mimetype = guess_from_path(value)
            if mimetype is None and kwargs.get("buffer") is None:
                mimetype = guess_from_buffer(value.read_bytes()[:2048])
        elif key == "buffer":
            mimetype = guess_from_buffer(value)

        if mimetype:
            break

    if mimetype and extension:
        return mimetype, extension
    elif mimetype and not extension:
        return mimetype, get_extension_from_mimetype(mimetype)
    elif not MAGIC_LIB_AVAILABLE:
        raise RuntimeError(
            "Failed to determine MIME type from file extension and cannot infer from data"
            "MIME type detection from raw data requires a functional python-magic library "
            "and its underlying libmagic dependency. Please install or configure them correctly."
            "See: https://pypi.org/project/python-magic/ for detailed instructions"
        )
    else:
        raise RuntimeError(
            "Failed to determine MIME type from file extension and cannot infer from data"
        )


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
