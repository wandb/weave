from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

# The types module is imported here as it has no external dependencies
# and is used in the `_get_mimetypes_module` helper.
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote_to_bytes

from weave.type_wrappers.Content.content_types import (
    DataUrl,
    DataUrlBase64,
    DataUrlBase64WithEncoding,
    DataUrlSimple,
    DataUrlWithEncoding,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # This block is only for static analysis and does not cause an import at runtime.
    from polyfile.magic import MagicMatcher

# See: https://mimesniff.spec.whatwg.org/
# Buffer size should be >= 1445 for deterministic results in most cases
# Most documentation uses 2048 to slightly exceed this requirement
# If the data is smaller than 2048 just use the entire thing
MIME_DETECTION_BUFFER_SIZE = 2048

# A global variable to hold the lazily imported mimetypes module.
_mimetypes_module: ModuleType | None = None

DATA_URL_PATTERN = re.compile(
    r"^data:(?P<media_type>[\w\/\-\+\.]+(?:;[\w\-]+\=[\w\-\.]+)*)?(?P<base64>;base64)?,(?P<data>.*)$"
)


def _get_mimetypes_module() -> ModuleType:
    """Lazily import and initialize the mimetypes module.

    This ensures the module is only loaded into memory when it's first needed
    and that its custom types are only added once.
    """
    global _mimetypes_module
    if _mimetypes_module is None:
        import mimetypes as _m

        # Mimetypes is missing text/markdown, add it on first use.
        _m.add_type("text/markdown", ".md")
        _mimetypes_module = _m
    return _mimetypes_module


def full_name(obj: Any) -> str:
    cls = obj.__class__
    module = cls.__module__
    if module == "builtins":
        return cls.__qualname__  # avoid outputs like 'builtins.str'
    return f"{module}.{cls.__qualname__}"


def is_valid_b64(input: str | bytes) -> bool:
    if len(input) == 0:
        return False

    # Normalize to bytes and verify it is not unicode
    if isinstance(input, str):
        try:
            input = input.encode("ascii")
        except UnicodeEncodeError:
            return False
    try:
        base64.b64decode(input, validate=True)

    except (ValueError, TypeError) as _:
        return False

    return True


def is_valid_path(input: str | Path) -> bool:
    if isinstance(input, str):
        input = Path(input)
    try:
        return input.exists() and input.is_file()
    except Exception:
        return False


def default_filename(
    extension: str | None,
    mimetype: str,
    digest: str,
) -> str:
    type_name, _ = mimetype.split("/")
    if type_name == "application":
        # This seems a bit more 'presentable'
        type_name = "file"

    digest_suffix = digest[:4]
    return f"{type_name}-{digest_suffix}{extension}"


def get_extension_from_mimetype(mimetype: str) -> str | None:
    mimetypes = _get_mimetypes_module()
    extension = mimetypes.guess_extension(mimetype)
    if not extension:
        logger.warning(
            f"Got mime-type {mimetype} but failed to resolve a valid extension"
        )
    return extension


def guess_from_buffer(buffer: bytes) -> str | None:
    """Guess the mimetype from a byte buffer using polyfile."""
    if len(buffer) == 0:
        return None

    try:
        # Lazily import polyfile only when needed.
        from polyfile.magic import MagicMatcher
    except (ImportError, ModuleNotFoundError):
        logger.warning(
            "Failed to determine MIME type from file extension and cannot infer from data\n"
            "MIME type detection from raw data requires the polyfile library\n"
            "Install it by running: `pip install polyfile `\n"
            "See: https://pypi.org/project/polyfile for detailed instructions"
        )
        return None

    try:
        matcher = cast("MagicMatcher", MagicMatcher.DEFAULT_INSTANCE)
        return next(matcher.match(buffer)).mimetypes[0]
    except IndexError:
        # This occurs if polyfile is installed but finds no match.
        return None


def guess_from_filename(filename: str) -> str | None:
    mimetypes = _get_mimetypes_module()
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
    default_mimetype: str = "application/octet-stream",
    default_extension: str = "",
) -> tuple[str, str]:
    # Set it to none if empty
    if buffer and len(buffer) == 0:
        buffer = None

    if extension is not None and len(extension) > 0:
        extension = f".{extension.lstrip('.')}"
    if mimetype and extension:
        return mimetype, extension

    elif (
        mimetype
        and not extension
        and (guessed_ext := get_extension_from_mimetype(mimetype))
    ):
        return mimetype, guessed_ext

    elif (
        extension and not mimetype and (guessed_type := guess_from_extension(extension))
    ):
        return guessed_type, extension

    if filename is not None:
        mimetype = guess_from_filename(filename)

    if not mimetype and extension is not None:
        mimetype = guess_from_extension(extension)

    if not mimetype and buffer is not None:
        mimetype = guess_from_buffer(buffer[:MIME_DETECTION_BUFFER_SIZE])

    if mimetype and extension:
        return mimetype, extension

    elif (
        mimetype
        and not extension
        and (extension := get_extension_from_mimetype(mimetype))
    ):
        return mimetype, extension

    if filename is not None:
        idx = filename.rfind(".")
        if idx != -1:
            extension = filename[idx:]

    return mimetype or default_mimetype, extension or default_extension


def match_data_url(url: str) -> re.Match[str] | None:
    return DATA_URL_PATTERN.match(url)


def try_parse_data_url(url: str) -> DataUrl | None:
    """Parses a data URI, extracting the media type, encoding (charset),
    base64 flag, and data.
    """
    match = match_data_url(url)

    if not match:
        return None

    groups = match.groupdict()
    data_str = groups.get("data")
    if data_str is None:
        return None

    full_media_type = groups.get("media_type")
    is_base64 = groups.get("base64") is not None

    # Initialize default values as per RFC 2397
    base_media_type = "text/plain"
    encoding = None  # Default for data URIs

    # If a media type is present, parse it
    if full_media_type:
        parts = [p.strip() for p in full_media_type.split(";")]
        base_media_type = str(parts[0].lower()) if parts[0] else "text/plain"

        # Find the charset parameter and override the default
        for param in parts[1:]:
            if param.lower().startswith("charset="):
                charset = param.split("=", 1)[1]
                if charset and isinstance(charset, str):
                    encoding = charset
                # Map to a Python-compatible encoding name (lowercase)
                break

    data_bytes: bytes
    if is_base64:
        try:
            data_bytes = base64.b64decode(data_str)
        except (ValueError, TypeError):
            logger.warning("Invalid base64 data in data URL.")
            return None
    else:
        # It's percent-encoded
        data_bytes = unquote_to_bytes(data_str)

    if encoding and is_base64:
        return DataUrl(
            params=DataUrlBase64WithEncoding(
                mimetype=base_media_type,
                data=data_bytes,
                content_type="data_url:encoding:base64",
                encoding=encoding,
            )
        )
    elif encoding:
        return DataUrl(
            params=DataUrlWithEncoding(
                mimetype=base_media_type,
                data=data_bytes,
                content_type="data_url:encoding",
                encoding=encoding,
            )
        )
    elif base64:
        return DataUrl(
            params=DataUrlBase64(
                mimetype=base_media_type,
                data=data_bytes,
                content_type="data_url:base64",
            )
        )
    return DataUrl(
        params=DataUrlSimple(
            mimetype=base_media_type,
            data=data_bytes,
            content_type="data_url",
        )
    )
