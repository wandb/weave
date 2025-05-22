from __future__ import annotations

import logging
import mimetypes
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict, Unpack

import magic

try:
    _MAGIC_INSTANCE_FOR_CHECK = magic.Magic(mime=True)
    MAGIC_LIB_AVAILABLE = True
    del _MAGIC_INSTANCE_FOR_CHECK  # Clean up
except magic.MagicException as e:
    MAGIC_LIB_AVAILABLE = False


logger = logging.getLogger(__name__)


class BaseContentArgs(TypedDict):
    extension: str
    mimetype: str
    filename: str
    path: str
    size: int
    data: bytes
    extra: dict[str, Any]


class ContentOptionalArgs(TypedDict, total=False):
    extension: str | None
    mimetype: str | None
    filename: str | None
    path: str | None
    size: int | None
    data: bytes | None
    extra: dict[str, Any] | None


def default_name_fn(mimetype: str, extension: str) -> str:
    return mimetype.split("/")[1] + "." + extension


def is_valid_path(input: str | Path) -> bool:
    if isinstance(input, str):
        input = Path(input)
    return input.exists() and input.is_file()


def resolve_filename(
    default_fn: Callable[..., str] = default_name_fn,
    **kwargs: Unpack[ContentOptionalArgs],
) -> str:
    if filename := kwargs.get("filename", None):
        return filename
    elif path := kwargs.get("path", None):
        return Path(path).name

    return default_fn(**kwargs)


def get_extension_from_mimetype(mimetype: str) -> str:
    extension = mimetypes.guess_extension(mimetype)
    if not extension:
        raise ValueError(
            f"Got mime-type {mimetype} but failed to resolve a valid extension"
        )
    return extension.lstrip(".")


def guess_from_buffer(buffer: bytes) -> str | None:
    if not MAGIC_LIB_AVAILABLE:
        return None
    return magic.Magic(mime=True).from_buffer(buffer)


def guess_from_filename(filename: str) -> str | None:
    return mimetypes.guess_type(filename)[0]


def guess_from_extension(extension: str) -> str | None:
    filename = f"file.{extension.lstrip('.')}"
    return guess_from_filename(filename)


def guess_from_path(path: str | Path) -> str | None:
    path = Path(path)
    mimetype = guess_from_filename(path.name)
    return mimetype


def get_mime_and_extension(
    buffer: bytes | None, **kwargs: Unpack[ContentOptionalArgs]
) -> tuple[str, str]:
    mimetype = kwargs.get("mimetype", None)
    extension = kwargs.get("mimetype", None)

    if mimetype and extension:
        return mimetype, extension
    elif mimetype and not extension:
        return mimetype, get_extension_from_mimetype(mimetype)

    for key in ["mimetype", "filename", "extension", "path"]:
        if not key in kwargs or kwargs.get(key) is None:
            continue

        value = str(kwargs.get(key))

        if key == "mimetype":
            mimetype = value
        elif key == "filename":
            mimetype = guess_from_filename(value)
        elif key == "extension":
            mimetype = guess_from_extension(value)
            # Only set if we got a valid mime type from it
        elif key == "path":
            mimetype = guess_from_path(Path(value))
            if mimetype is None and buffer is None:
                mimetype = guess_from_buffer(Path(value).read_bytes()[:2048])
        if mimetype:
            break

    if not mimetype and buffer:
        mimetype = guess_from_buffer(buffer)

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

    raise RuntimeError(
        "Failed to determine MIME type from file extension and cannot infer from data"
    )
