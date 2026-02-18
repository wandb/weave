"""MIME type detection using polyfile (pure Python libmagic implementation).

Polyfile only supports buffer-based detection and does not provide
file extension information.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polyfile.magic import MagicMatcher


def is_available() -> bool:
    """Check whether polyfile is installed and usable."""
    try:
        from polyfile.magic import MagicMatcher  # noqa: F811

        return True
    except (ImportError, ModuleNotFoundError):
        return False


def detect(
    *, filename: str | None, buffer: bytes | None
) -> tuple[str | None, str | None]:
    """Detect MIME type from a byte buffer using polyfile.

    Polyfile does not support file-based detection or extension detection,
    so the filename parameter is ignored and extension is always None.

    Returns (mimetype, None) tuple; mimetype may be None.
    """
    if buffer is None or len(buffer) == 0:
        return None, None

    try:
        from polyfile.magic import MagicMatcher  # noqa: F811
    except (ImportError, ModuleNotFoundError):
        return None, None

    try:
        matcher = cast("MagicMatcher", MagicMatcher.DEFAULT_INSTANCE)
        mimetype = next(matcher.match(buffer)).mimetypes[0]
        return mimetype, None
    except (IndexError, StopIteration):
        return None, None
