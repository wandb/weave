"""Stable client identity for WAL directory namespacing.

When multiple clients write to the same entity/project (e.g. different API
keys), each client needs its own WAL subdirectory so that senders never
pick up records belonging to a different client.

The directory name is SHA-256 of the API key.  This is deterministic (same
key → same directory → crash recovery works) and stable across machines.
"""

from __future__ import annotations

import hashlib
import os

WAL_ROOT = os.path.join(os.path.expanduser("~"), ".weave", "wal")


def compute_client_id(api_key: str) -> str:
    """Derive a stable directory name from an API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
