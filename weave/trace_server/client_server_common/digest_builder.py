"""This module contains the shared functions for building digests in Weave.

While small, it is extremely critical to the integrity of the system that it is
stable and consistent. Digests are used throughout the system to generate stable
identities for objects.

This needs to be consistent between the client and server and cannot change over time.

If changes are made to this module, then all newly minted digests will be different than
before, breaking our ability to dedupe and recognize the same object. Change this file
with extreme caution!! Talk to Tim Sweeney before making any changes.

* For low-level binary digests, use bytes_digest.
* For string digests, use str_digest.
* For JSON digests, use ref_aware_json_digest (recommended) or ref_unaware_json_digest (dangerous).
* For table digests, use table_digest_from_row_digests.

"""

import base64
import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

EXTERNAL_REF_PREFIX = "weave:///"
INTERNAL_REF_PREFIX = "weave-trace-internal:///"
# NOTE: This string becomes part of the stabilized value that is hashed. Changing it
# changes digests and should be treated as a migration-level change *once shipped*.
STABILIZED_REF_URI_PREFIX = "weave-anonymous:///_/_/"


def bytes_digest(bytes_val: bytes) -> str:
    """Generate a stable digest for raw bytes.

    This is the lowest-level digest primitive used throughout the system. The output is a
    SHA-256 digest encoded as urlsafe base64 with a couple of tweaks:
      - `=` padding is stripped
      - `-` and `_` are replaced so the result is alphanumeric-only

    Args:
        bytes_val (bytes): The input bytes.

    Returns:
        str: Stable digest string.

    Examples:
        >>> bytes_digest(b"abc") == bytes_digest(b"abc")
        True
        >>> bytes_digest(b"abc") == bytes_digest(b"abcd")
        False
    """
    hasher = hashlib.sha256()
    hasher.update(bytes_val)
    hash_bytes = hasher.digest()
    base64_encoded_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64_encoded_hash.replace("-", "X").replace("_", "Y").rstrip("=")


def str_digest(str_val: str) -> str:
    """Generate a stable digest for a string.

    This is just `bytes_digest` applied to UTF-8 encoded text.

    Args:
        str_val (str): Input string.

    Returns:
        str: Stable digest string.

    Examples:
        >>> str_digest("hello") == bytes_digest(b"hello")
        True
    """
    return bytes_digest(str_val.encode())


def ref_unaware_json_digest(json_val: Any) -> str:
    """Generate a stable digest for JSON-like data (ref-unaware).

    Notes:
        - Dict keys are sorted to make the digest independent of insertion order.
        - Sets are encoded deterministically as a tagged object, since sets are not JSON.
        - This function does NOT stabilize Weave ref strings. If you want digests that are
          robust to owner/entity prefixes inside refs, use `ref_aware_json_digest`.
    """
    canonical_json_val = _canonicalize_json_like(json_val)
    return _json_digest(canonical_json_val)


def ref_aware_json_digest(json_val: Any) -> str:
    """Generate a stable digest for JSON-like data (ref-aware).

    This is the recommended digest for values that may contain Weave refs, because it
    normalizes ref strings so that owner/entity/project-like prefixes do not “pollute”
    the digest.

    Normalization rules:
      - External refs (`weave:///entity/project/...`) are stabilized by replacing the
        `entity/project` segments with `_/_` while keeping the remaining path.
      - Internal refs (`weave-trace-internal:///project_id/...`) are stabilized by
        replacing `project_id` with `_/_` while keeping the remaining path.
      - Malformed refs are left unchanged (no stabilization, no error).

    Args:
        json_val (Any): JSON-like value to digest.

    Returns:
        str: Stable digest string.

    Examples:
        >>> d = ref_unaware_json_digest({"a": 1})
        >>> ref_aware_json_digest({"r": f"weave:///ent/proj/object/X:{d}"}) == ref_aware_json_digest({"r": f"weave-trace-internal:///pid/object/X:{d}"})
        True
    """

    def mapper(val: Any) -> Any:
        if isinstance(val, str):
            return _stabilize_ref_str(val)
        return val

    mapped_json_val = _map_val(json_val, mapper)
    canonical_json_val = _canonicalize_json_like(mapped_json_val)
    res = _json_digest(canonical_json_val)

    return res


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
    return str_digest(json.dumps(json_val, sort_keys=True))


E = TypeVar("E")


def _map_val(obj: E, func: Callable[[E], E]) -> E:
    if isinstance(obj, dict):
        return cast(E, {k: _map_val(v, func) for k, v in obj.items()})
    if isinstance(obj, list):
        return cast(E, [_map_val(v, func) for v in obj])
    if isinstance(obj, tuple):
        return cast(E, tuple(_map_val(v, func) for v in obj))
    if isinstance(obj, set):
        # Important: `_map_val` is for applying a value-level transform; it should not
        # encode container semantics. We preserve set-ness here and handle JSON encoding
        # deterministically in `_canonicalize_json_like`.
        return cast(E, {_map_val(v, func) for v in obj})
    return func(obj)


def _canonicalize_json_like(obj: Any) -> Any:
    """Canonicalize JSON-like objects for stable hashing.

    This is intentionally ref-unaware: it only deals with deterministic encoding of
    containers (dict/list/tuple/set) so that stable hashing is possible.
    """
    if isinstance(obj, dict):
        # Canonicalize in a deterministic key order *recursively*.
        # We still keep json.dumps(sort_keys=True) in _json_digest as an extra guardrail.
        return {
            k: _canonicalize_json_like(obj[k])
            for k in sorted(obj.keys(), key=_stable_json_sort_key)
        }
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


def _stable_json_sort_key(val: Any) -> str:
    """Return a stable string sort key for JSON-like values."""
    try:
        return json.dumps(val, sort_keys=True)
    except TypeError:
        # Fallback: make a best-effort stable ordering for unexpected key types.
        return repr(val)


def _make_stabilized_ref_str(stable_content_address: str) -> str:
    return f"{STABILIZED_REF_URI_PREFIX}{stable_content_address}"


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
    if ref.startswith(EXTERNAL_REF_PREFIX):
        # Remove EXTERNAL_REF_PREFIX and the first two path segments (entity/project)
        ref_body = ref[len(EXTERNAL_REF_PREFIX) :]
        parts = ref_body.split("/")
        if len(parts) < 3:
            # Malformed ref: don't stabilize.
            return ref
        # join everything after first two segments (entity and project)
        stable_content_address = "/".join(parts[2:])
        return _make_stabilized_ref_str(stable_content_address)
    elif ref.startswith(INTERNAL_REF_PREFIX):
        # Remove INTERNAL_REF_PREFIX and the first path segment (project_id)
        ref_body = ref[len(INTERNAL_REF_PREFIX) :]
        parts = ref_body.split("/")
        if len(parts) < 2:
            # Malformed ref: don't stabilize.
            return ref
        # join everything after first segment (project_id)
        stable_content_address = "/".join(parts[1:])
        return _make_stabilized_ref_str(stable_content_address)
    return ref
