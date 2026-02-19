"""MIME type and extension detection using python-magic (libmagic wrapper).

Provides detection from both file paths (magic.from_file) and byte buffers
(magic.from_buffer). Creates fresh Magic instances per call to avoid
contention — each instance has its own internal lock and libmagic cookie.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Cached availability flags.  Set once on first call; read-only afterwards.
# Because Python's GIL protects simple attribute reads/writes, and the worst
# case of a race is redundant initialisation (idempotent), no lock is needed.
_magic_available: bool | None = None
_magic_has_extension: bool = False


def _check_availability() -> tuple[bool, bool]:
    """One-time check for python-magic availability."""
    global _magic_available, _magic_has_extension
    if _magic_available is not None:
        return _magic_available, _magic_has_extension
    try:
        import magic

        magic.Magic(mime=True)
        _magic_available = True
    except (ImportError, Exception) as e:
        logger.debug("python-magic is not available: %s", e)
        _magic_available = False
        return False, False
    try:
        magic.Magic(extension=True)  # type: ignore[call-overload]
        _magic_has_extension = True
    except NotImplementedError:
        logger.warning(
            "libmagic version out of date, upgrade libmagic to version above 524 for extension detection."
        )
    return _magic_available, _magic_has_extension


def _make_magic_instances() -> tuple[Any, Any]:
    """Create fresh Magic instances for this call.

    Each Magic instance carries its own threading.Lock and libmagic cookie,
    so concurrent callers never share C-level state.
    """
    available, has_extension = _check_availability()
    if not available:
        return None, None

    import magic

    mime_inst = magic.Magic(mime=True)
    ext_inst = magic.Magic(extension=True) if has_extension else None  # type: ignore[call-overload]
    return mime_inst, ext_inst


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


def _resolve_extension(raw_ext: str | None, mimetype: str) -> str | None:
    """Normalize a libmagic extension, falling back to stdlib mimetypes."""
    import mimetypes

    extension = _normalize_magic_extension(raw_ext)
    if extension is None:
        extension = mimetypes.guess_extension(mimetype)
    return extension


def is_available() -> bool:
    """Check whether python-magic is installed and usable.

    Only requires the MIME-detection instance; extension detection is optional
    (it needs a newer libmagic that may not be bundled on Windows).
    """
    available, _ = _check_availability()
    return available


def detect(
    *, filename: str | None, buffer: bytes | None
) -> tuple[str | None, str | None]:
    """Detect MIME type and extension using python-magic.

    When filename is set to a valid value, tries magic.from_file first.
    If from_file fails because the file is not found, falls back to
    from_buffer when buffer is available.

    Extension detection uses libmagic's extension mode when available,
    otherwise falls back to stdlib mimetypes.guess_extension().

    Returns (mimetype, extension) tuple; either value may be None.
    """
    mime_magic, ext_magic = _make_magic_instances()
    if mime_magic is None:
        return None, None

    # Try from_file when filename is provided
    if filename is not None:
        try:
            mimetype = mime_magic.from_file(filename)
            if mimetype:
                raw_ext = ext_magic.from_file(filename) if ext_magic else None
                return mimetype, _resolve_extension(raw_ext, mimetype)
        except FileNotFoundError:
            # File not found — fall through to from_buffer
            pass
        except Exception as e:
            logger.debug("magic.from_file failed for %r: %s", filename, e)

    # Fall back to from_buffer
    if buffer is not None:
        try:
            mimetype = mime_magic.from_buffer(buffer)
            if mimetype:
                raw_ext = ext_magic.from_buffer(buffer) if ext_magic else None
                return mimetype, _resolve_extension(raw_ext, mimetype)
        except Exception as e:
            logger.debug("magic.from_buffer failed: %s", e)

    return None, None
