"""Shared digest validation helpers for trace servers."""

from __future__ import annotations

import logging

from weave.trace_server.errors import DigestMismatchError

logger = logging.getLogger(__name__)


def validate_expected_digest(
    *,
    expected: str | None,
    actual: str,
    label: str,
) -> None:
    """Check a client-provided expected digest against the server-computed one.

    Args:
        expected: The digest the client computed (None on fallback path).
        actual: The digest the server computed.
        label: Human-readable context for log/error messages (e.g. "obj 'my_obj'",
               "table (5 rows)", "file").

    Raises:
        DigestMismatchError: If *expected* is not None and differs from *actual*.
    """
    if expected is not None:
        if expected != actual:
            raise DigestMismatchError(
                f"Client {label} digest {expected} != server digest {actual}"
            )
        logger.debug(
            "Server digest: %s FAST PATH verified (client=%s, server=%s)",
            label,
            expected,
            actual,
        )
    else:
        logger.debug(
            "Server digest: %s FALLBACK PATH (server=%s)",
            label,
            actual,
        )
