from __future__ import annotations

import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import magic

try:
    _MAGIC_INSTANCE_FOR_CHECK = magic.Magic(mime=True)
    MAGIC_LIB_AVAILABLE = True
    del _MAGIC_INSTANCE_FOR_CHECK  # Clean up
except magic.MagicException as e:
    MAGIC_LIB_AVAILABLE = False


logger = logging.getLogger(__name__)


# TODO: Mypy is really unfriendly to kwargs. Can we use pydantic or something to not make this so repetitive?
class BaseContentArgs(TypedDict):
    extension: str
    mimetype: str
    filename: str
    size: int


class ContentOptionalArgs(TypedDict):
    extension: str | None
    mimetype: str | None
    filename: str | None
    path: str | None
    size: int | None
    extra: dict[str, Any]


class ContentKeywordArgs(TypedDict, total=False):
    extension: str
    mimetype: str
    filename: str
    path: str
    size: int
    extra: dict[str, Any]


def is_valid_path(input: str | Path) -> bool:
    if isinstance(input, str):
        input = Path(input)
    try:
        return input.exists() and input.is_file()
    except Exception as _:
        return False


def default_filename(
    extension: str,
) -> str:
    now = datetime.now()
    datetime_str = now.strftime("%Y%m%d_%H%M%S")
    return datetime_str + "." + extension


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
    *,
    mimetype: str | None,
    extension: str | None,
    filename: str | None,
    buffer: bytes | None,
) -> tuple[str, str]:
    if mimetype and extension:
        return mimetype, extension
    elif mimetype and not extension:
        return mimetype, get_extension_from_mimetype(mimetype)

    if filename is not None:
        mimetype = guess_from_filename(filename)
    if not mimetype and extension is not None:
        mimetype = guess_from_extension(extension)
    if not mimetype and buffer is not None:
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
