"""Digest calculation functions shared between client and server.

These functions compute content-addressable hashes for weave objects.
The digest algorithm produces identical results on both client and server,
enabling client-side digest computation for parallel publishing.
"""

import base64
import hashlib


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
