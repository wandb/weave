"""MIME type detection using polyfile (pure Python libmagic implementation).

Polyfile only supports buffer-based detection and does not provide
file extension information.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


def is_available() -> bool:
    """Check whether polyfile is installed and usable."""
    matcher = None
    try:
        from polyfile.magic import MagicMatcher

        matcher = MagicMatcher
    except (ImportError, ModuleNotFoundError):
        pass
    return matcher is not None


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

    if not is_available():
        return None, None

    from polyfile.magic import MagicMatcher

    try:
        mimetype = next(MagicMatcher.DEFAULT_INSTANCE.match(buffer)).mimetypes[0]
    except (IndexError, StopIteration):
        return None, None
    else:
        return mimetype, None
