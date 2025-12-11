"""Stable digests for Weave identities.

This module must remain stable and consistent between client/server. Changing digest
behavior changes object identities and breaks deduplication.

Public API (intentionally small to reduce misuse):
  - `safe_digest`: stable digest for JSON-like values (ref-aware).
  - `table_digest_from_row_digests`: stable, order-dependent digest for tables.

Notes:
  - `safe_digest` is **ref-aware**: it normalizes Weave ref strings so that owner/entity/
    project-like prefixes do not “pollute” digests.
  - Sets are **not supported** (unordered) and raise.
  - Dict keys must be strings (JSON semantics) and are ordered recursively for stability.
"""

import base64
import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

_EXTERNAL_REF_PREFIX = "weave:///"
_INTERNAL_REF_PREFIX = "weave-trace-internal:///"
# NOTE: This string becomes part of the stabilized value that is hashed. Changing it
# changes digests and should be treated as a migration-level change *once shipped*.
_STABILIZED_REF_URI_PREFIX = "weave-anonymous:///_/_/"

__all__ = ["safe_digest", "table_digest_from_row_digests"]


def _bytes_digest(bytes_val: bytes) -> str:
    """Digest raw bytes (private helper)."""
    hasher = hashlib.sha256()
    hasher.update(bytes_val)
    hash_bytes = hasher.digest()
    base64_encoded_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64_encoded_hash.replace("-", "X").replace("_", "Y").rstrip("=")


def _str_digest(str_val: str) -> str:
    """Digest a string by hashing its UTF-8 bytes (private helper)."""
    return _bytes_digest(str_val.encode())


def safe_digest(val: Any) -> str:
    """Generate a stable digest for JSON-like values (safe default).

    This digest is:
      - **Stable** to dict insertion order (recursively).
      - **Ref-aware**: Weave ref strings are normalized to avoid embedding owner/entity/
        project-like prefixes in the digest.

    Supported types:
      - `None`, `bool`, `int`, `float`, `str`
      - `list`/`tuple` of supported types
      - `dict[str, ...]` of supported types

    Not supported:
      - `set` (unordered): raises `TypeError`
      - dicts with non-`str` keys: raises `TypeError`
    """
    if isinstance(val, (bytes, bytearray, memoryview)):
        return _bytes_digest(bytes(val))
    if isinstance(val, str):
        # If this string is a Weave ref, normalize it first.
        return _str_digest(_stabilize_ref_str(val))
    stabilized = _stabilize_refs_in_json_like(val)
    canonical = _canonicalize_json_like(stabilized)
    return _json_digest(canonical)


def table_digest_from_row_digests(row_digests: list[str]) -> str:
    """Generate a stable digest for a table from row digests.

    The resulting digest is **order-dependent**: `[row1, row2]` hashes differently than
    `[row2, row1]`.

    Args:
        row_digests (list[str]): Row digests in the intended table order.

    Returns:
        str: Hex-encoded SHA-256 digest.
    """
    table_hasher = hashlib.sha256()
    for row_digest in row_digests:
        table_hasher.update(row_digest.encode())
    return table_hasher.hexdigest()


def _json_digest(json_val: Any) -> str:
    # IMPORTANT: This must stay stable over time. We explicitly sort dict keys so that
    # semantically-identical JSON objects (that differ only in insertion order) hash the same.
    #
    # NOTE: We intentionally do *not* change json.dumps separators/whitespace settings here,
    # because that would change all digests. Keep encoding defaults unless there's a strong
    # reason to change them (and a migration plan).
    return _str_digest(json.dumps(json_val, sort_keys=True))


E = TypeVar("E")


def _map_val(obj: E, func: Callable[[E], E]) -> E:
    if isinstance(obj, dict):
        return cast(E, {k: _map_val(v, func) for k, v in obj.items()})
    if isinstance(obj, list):
        return cast(E, [_map_val(v, func) for v in obj])
    if isinstance(obj, tuple):
        return cast(E, tuple(_map_val(v, func) for v in obj))
    if isinstance(obj, set):
        # Sets are not supported anywhere in safe_digest; error early and avoid iterating
        # over an unordered collection.
        raise TypeError(
            "Cannot hash set values in digest_builder; convert to a list/tuple first."
        )
    return func(obj)


def _canonicalize_json_like(obj: Any) -> Any:
    """Canonicalize JSON-like objects for stable hashing.

    This is intentionally ref-unaware: it only deals with deterministic encoding of
    containers (dict/list/tuple/set) so that stable hashing is possible.
    """
    if isinstance(obj, dict):
        for k in obj.keys():
            if not isinstance(k, str):
                raise TypeError(
                    "safe_digest only supports JSON-like dicts with string keys; "
                    f"got key type {type(k)}"
                )
        return {k: _canonicalize_json_like(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_canonicalize_json_like(v) for v in obj]
    if isinstance(obj, tuple):
        return [_canonicalize_json_like(v) for v in obj]
    if isinstance(obj, set):
        # Sets are inherently unordered; hashing them would be sensitive to unstable
        # iteration order. Require callers to convert sets to an ordered type first.
        raise TypeError(
            "Cannot hash set values in digest_builder; convert to a list/tuple first."
        )
    return obj


def _stabilize_refs_in_json_like(val: Any) -> Any:
    """Return a JSON-like value with Weave ref strings normalized."""

    def mapper(v: Any) -> Any:
        if isinstance(v, str):
            return _stabilize_ref_str(v)
        return v

    return _map_val(val, mapper)


def _make_stabilized_ref_str(stable_content_address: str) -> str:
    return f"{_STABILIZED_REF_URI_PREFIX}{stable_content_address}"


def _stabilize_ref_str(ref: str) -> str:
    """Stabilize a ref string by creating a stable content address.

    This strips the prefix, then removes the appropriate number of segments
    (2 for external, 1 for internal), and joins the rest as the stable address.

    Args:
        ref (str): The input reference string.

    Returns:
        str: The stabilized reference string.

    Examples:
        >>> _stabilize_ref_str("weave:///entity/proj/object/Foo:abc123/attr/bar")
        'weave-anonymous:///_/_/object/Foo:abc123/attr/bar'
        >>> _stabilize_ref_str("weave-trace-internal:///proj_id/object/Foo:abc123/attr/bar")
        'weave-anonymous:///_/_/object/Foo:abc123/attr/bar'
    """
    if ref.startswith(_EXTERNAL_REF_PREFIX):
        # Remove _EXTERNAL_REF_PREFIX and the first two path segments (entity/project)
        ref_body = ref[len(_EXTERNAL_REF_PREFIX) :]
        parts = ref_body.split("/")
        if len(parts) < 3:
            # Malformed ref: don't stabilize.
            return ref
        # join everything after first two segments (entity and project)
        stable_content_address = "/".join(parts[2:])
        return _make_stabilized_ref_str(stable_content_address)
    elif ref.startswith(_INTERNAL_REF_PREFIX):
        # Remove _INTERNAL_REF_PREFIX and the first path segment (project_id)
        ref_body = ref[len(_INTERNAL_REF_PREFIX) :]
        parts = ref_body.split("/")
        if len(parts) < 2:
            # Malformed ref: don't stabilize.
            return ref
        # join everything after first segment (project_id)
        stable_content_address = "/".join(parts[1:])
        return _make_stabilized_ref_str(stable_content_address)
    return ref
