from __future__ import annotations

import logging
import mimetypes
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import puremagic
try:
    import puremagic

    MAGIC_LIB_AVAILABLE = True
except Exception as e:
    MAGIC_LIB_AVAILABLE = False

# See: https://mimesniff.spec.whatwg.org/
# Buffer size should be >= 1445 for deterministic results in most cases
# Most documentation uses 2048 to slightly exceed this requirement
# If the data is smaller than 2048 just use the entire thing
MIME_DETECTION_BUFFER_SIZE = 2048


class ContentArgs(TypedDict):
    extension: str | None
    mimetype: str | None
    filename: str | None
    path: str | None
    size: int | None
    encoding: str | None
    extra: dict[str, Any]


class ContentKeywordArgs(TypedDict, total=False):
    extension: str
    mimetype: str
    filename: str
    path: str
    size: int
    encoding: str
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
    # Do not give the file an empty extension. Prefer none
    if len(extension) == 0:
        return datetime_str

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

    match = puremagic.magic_stream(BytesIO(buffer))[0]
    return match.mime_type


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
        mimetype = guess_from_buffer(buffer[:MIME_DETECTION_BUFFER_SIZE])

    if mimetype and extension:
        return mimetype, extension
    elif mimetype and not extension:
        return mimetype, get_extension_from_mimetype(mimetype)
    elif not MAGIC_LIB_AVAILABLE:
        logger.warning(
            "Failed to determine MIME type from file extension and cannot infer from data\n"
            "MIME type detection from raw data requires the puremagic library\n"
            "Install it by running: `pip install puremagic`\n"
            "See: https://pypi.org/project/puremagic for detailed instructions"
        )
    if filename is not None:
        idx = filename.rfind(".")
        if idx != -1:
            extension = filename[idx:]

    return "application/octet-stream", ""
