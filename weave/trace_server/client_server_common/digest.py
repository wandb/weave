"""Stable digests for Weave identities.

This module centralizes ALL digest calculation logic shared between client and server.
Changing digest behavior changes object identities and breaks deduplication.

Public API:
  - `bytes_digest`: digest for raw bytes (e.g., file contents)
  - `str_digest`: digest for strings (UTF-8 encoded)
  - `json_digest`: stable digest for JSON-serializable values (sorted keys)
  - `table_digest_from_row_digests`: stable, order-dependent digest for tables

IMPORTANT: These functions must remain stable. Any changes affect object identity
and require migration planning.
"""

import base64
import hashlib
import json
from typing import Any


def bytes_digest(data: bytes) -> str:
    """Compute SHA-256 digest of bytes, encoded as URL-safe base64.

    The encoding replaces '-' with 'X' and '_' with 'Y' to avoid
    characters that could cause issues in URIs, and strips padding.

    Args:
        data: Raw bytes to hash.

    Returns:
        A 43-character string representing the digest.
    """
    hasher = hashlib.sha256()
    hasher.update(data)
    hash_bytes = hasher.digest()
    base64_encoded_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64_encoded_hash.replace("-", "X").replace("_", "Y").rstrip("=")


def str_digest(data: str) -> str:
    """Compute SHA-256 digest of a string (UTF-8 encoded).

    Args:
        data: String to hash.

    Returns:
        A 43-character string representing the digest.
    """
    return bytes_digest(data.encode())


def json_digest(val: Any) -> str:
    """Compute stable digest for a JSON-serializable value.

    This function ensures stability by:
    - Sorting dict keys recursively (so {"a": 1, "b": 2} == {"b": 2, "a": 1})
    - Using consistent JSON encoding

    IMPORTANT: This must stay stable over time. Do not change json.dumps
    separators/whitespace settings without a migration plan.

    Args:
        val: JSON-serializable value (dict, list, str, int, float, bool, None).

    Returns:
        A 43-character string representing the digest.
    """
    return str_digest(json.dumps(val, sort_keys=True))


def table_digest_from_row_digests(row_digests: list[str]) -> str:
    """Generate a stable digest for a table from row digests.

    The resulting digest is **order-dependent**: `[row1, row2]` hashes differently
    than `[row2, row1]`.

    Args:
        row_digests: Row digests in the intended table order.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    table_hasher = hashlib.sha256()
    for row_digest in row_digests:
        table_hasher.update(row_digest.encode())
    return table_hasher.hexdigest()
