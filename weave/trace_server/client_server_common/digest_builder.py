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
* For JSON digests, use ref_stable_json_digest.
* For table digests, use table_digest_from_row_digests.

"""

import base64
import hashlib
import json
from typing import Any, Callable, TypeVar, cast

external_ref_prefix = "weave:///"
internal_ref_prefix = "weave-trace-internal:///"


# TODO: Should we call this "dangerous" or "unstable"?
def bytes_digest(bytes_val: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(bytes_val)
    hash_bytes = hasher.digest()
    base64_encoded_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64_encoded_hash.replace("-", "X").replace("_", "Y").rstrip("=")


# TODO: Should we call this "dangerous" or "unstable"?
def str_digest(str_val: str) -> str:
    return bytes_digest(str_val.encode())


def ref_stable_json_digest(json_val: Any) -> str:
    def mapper(val: Any) -> Any:
        if isinstance(val, str):
            return _stabilize_ref_str(val)
        return val

    mapped_json_val = _map_val(json_val, mapper)
    res = _json_digest(mapped_json_val)

    return res


def table_digest_from_row_digests(row_digests: list[str]) -> str:
    table_hasher = hashlib.sha256()
    for row_digest in row_digests:
        table_hasher.update(row_digest.encode())
    return table_hasher.hexdigest()


def _json_digest(json_val: Any) -> str:
    return str_digest(json.dumps(json_val))


E = TypeVar("E")


def _map_val(obj: E, func: Callable[[E], E]) -> E:
    if isinstance(obj, dict):
        return cast(E, {k: _map_val(v, func) for k, v in obj.items()})
    if isinstance(obj, list):
        return cast(E, [_map_val(v, func) for v in obj])
    if isinstance(obj, tuple):
        return cast(E, tuple(_map_val(v, func) for v in obj))
    if isinstance(obj, set):
        return cast(E, {_map_val(v, func) for v in obj})
    return func(obj)


def _make_stabilized_ref_str(stable_content_address: str) -> str:
    # TODO: Make a call on this name - we really can't change it once it is in there
    return f"__stabilized_ref__:///{stable_content_address}"


def _stabilize_ref_str(ref: str) -> str:
    """Stabilize a ref string by creating a stable content address.

    This strips the prefix, then removes the appropriate number of segments
    (2 for external, 1 for internal), and joins the rest as the stable address.

    Args:
        ref (str): The input reference string.

    Returns:
        str: The stabilized reference string.

    Raises:
        ValueError: If the URI doesn't have the required number of segments.

    Examples:
        >>> _stabilize_ref_str("weave:///entity/proj/object/Foo:abc123/attr/bar")
        '__stabilized_ref__:///object/Foo:abc123/attr/bar'
        >>> _stabilize_ref_str("weave-trace-internal:///proj_id/object/Foo:abc123/attr/bar")
        '__stabilized_ref__:///object/Foo:abc123/attr/bar'
    """
    if ref.startswith(external_ref_prefix):
        # Remove external_ref_prefix and the first two path segments (entity/project)
        ref_body = ref[len(external_ref_prefix) :]
        parts = ref_body.split("/")
        if len(parts) < 3:
            raise ValueError(f"Invalid URI: {ref}")
        # join everything after first two segments (entity and project)
        stable_content_address = "/".join(parts[2:])
        return _make_stabilized_ref_str(stable_content_address)
    elif ref.startswith(internal_ref_prefix):
        # Remove internal_ref_prefix and the first path segment (project_id)
        ref_body = ref[len(internal_ref_prefix) :]
        parts = ref_body.split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid URI: {ref}")
        # join everything after first segment (project_id)
        stable_content_address = "/".join(parts[1:])
        return _make_stabilized_ref_str(stable_content_address)
    return ref
