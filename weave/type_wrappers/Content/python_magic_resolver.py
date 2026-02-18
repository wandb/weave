"""MIME type and extension detection using python-magic (libmagic wrapper).

Provides detection from both file paths (magic.from_file) and byte buffers
(magic.from_buffer). Uses separate Magic instances with mime=True and
extension=True to determine both values in one go.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-initialized python-magic instances.
# We use two separate Magic instances because the mime and extension flags
# use different libmagic modes that cannot be combined in a single instance.
_magic_mime_instance: Any = None
_magic_ext_instance: Any = None
_magic_checked: bool = False


def _get_magic_instances() -> tuple[Any, Any]:
    """Lazily import python-magic and create Magic instances."""
    global _magic_mime_instance, _magic_ext_instance, _magic_checked
    if not _magic_checked:
        _magic_checked = True
        try:
            import magic
            _magic_mime_instance = magic.Magic(mime=True, extension=True) # type: ignore
        except (ImportError, Exception) as e:
            logger.debug("python-magic is not available: %s", e)
    return _magic_mime_instance, _magic_ext_instance


def _normalize_magic_extension(raw_ext: str | None) -> str | None:
    """Normalize the extension string returned by python-magic.

    python-magic with extension=True returns values like:
    - "png" for a single match
    - "jpeg/jpg/jpe/jfif" for multiple alternatives (slash-separated)
    - "???" when the type is unknown

    Returns a normalized extension with a leading dot (e.g. ".png"), or None.
    """
    if not raw_ext or raw_ext.strip() == "???" or not raw_ext.strip():
        return None
    # Take the first alternative if multiple are returned
    ext = raw_ext.split("/")[0].strip()
    if not ext:
        return None
    if not ext.startswith("."):
        ext = f".{ext}"
    return ext


def is_available() -> bool:
    """Check whether python-magic is installed and usable."""
    mime_magic, ext_magic = _get_magic_instances()
    return mime_magic is not None and ext_magic is not None


def detect(
    *, filename: str | None, buffer: bytes | None
) -> tuple[str | None, str | None]:
    """Detect MIME type and extension using python-magic.

    When filename is set to a valid value, tries magic.from_file first.
    If from_file fails because the file is not found, falls back to
    from_buffer when buffer is available.

    Returns (mimetype, extension) tuple; either value may be None.
    """
    mime_magic, ext_magic = _get_magic_instances()
    if mime_magic is None or ext_magic is None:
        return None, None

    # Try from_file when filename is provided
    if filename is not None:
        try:
            mimetype = mime_magic.from_file(filename)
            raw_ext = ext_magic.from_file(filename)
            extension = _normalize_magic_extension(raw_ext)
            if mimetype:
                return mimetype, extension
        except FileNotFoundError:
            # File not found — fall through to from_buffer
            pass
        except Exception as e:
            logger.debug("magic.from_file failed for %r: %s", filename, e)

    # Fall back to from_buffer
    if buffer is not None:
        try:
            mimetype = mime_magic.from_buffer(buffer)
            raw_ext = ext_magic.from_buffer(buffer)
            extension = _normalize_magic_extension(raw_ext)
            if mimetype:
                return mimetype, extension
        except Exception as e:
            logger.debug("magic.from_buffer failed: %s", e)

    return None, None
