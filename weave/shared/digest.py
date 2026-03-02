"""Deterministic digest calculation helpers to be shared by client and server.

This module centralizes digest calculation logic to ensure consistency between
the client and server, allowing digests to be safely computed client-side,
ultimately supporting a client-side write-ahead-log (WAL).

Use these helpers when computing:
- Object digests
- Table row digests (and the aggregate table digest)
- File/content digests

Do not implement ad-hoc digest calculation logic outside this module, as that
could break ref stability across systems.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from weave.shared.object_class_util import process_incoming_object_val
from weave.shared.refs_internal import (
    InternalObjectRef,
    InternalOpRef,
    InternalTableRef,
)


def bytes_digest(json_val: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(json_val)
    hash_bytes = hasher.digest()
    base64_encoded_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64_encoded_hash.replace("-", "X").replace("_", "Y").rstrip("=")


def str_digest(json_val: str) -> str:
    return bytes_digest(json_val.encode())


@dataclass(frozen=True)
class ObjectDigestResult:
    """Deterministic digest data for object-create style payloads."""

    processed_val: Any
    json_val: str
    digest: str
    base_object_class: str | None
    leaf_object_class: str | None


def compute_object_digest_result(
    val: Any, builtin_object_class: str | None = None
) -> ObjectDigestResult:
    """Compute the object digest using server-equivalent normalization and hashing."""
    processed_result = process_incoming_object_val(val, builtin_object_class)
    processed_val = processed_result["val"]
    # Keep object digests stable regardless of dictionary insertion order.
    json_val = json.dumps(processed_val, sort_keys=True)
    digest = str_digest(json_val)
    return ObjectDigestResult(
        processed_val=processed_val,
        json_val=json_val,
        digest=digest,
        base_object_class=processed_result["base_object_class"],
        leaf_object_class=processed_result["leaf_object_class"],
    )


def compute_object_digest(val: Any, builtin_object_class: str | None = None) -> str:
    """Compute the object digest only."""
    return compute_object_digest_result(val, builtin_object_class).digest


def compute_row_digest(row: dict[str, Any]) -> str:
    """Compute a single row digest exactly as table_create does server-side."""
    # Keep table row digests stable regardless of dictionary insertion order.
    row_json = json.dumps(row, sort_keys=True)
    return str_digest(row_json)


def compute_table_digest(row_digests: list[str]) -> str:
    """Compute table digest from the ordered row digest list."""
    table_hasher = hashlib.sha256()
    for row_digest in row_digests:
        table_hasher.update(row_digest.encode())
    return table_hasher.hexdigest()


def compute_file_digest(content: bytes) -> str:
    """Compute file digest using server-equivalent file hashing."""
    return bytes_digest(content)


def compute_object_ref_uri(
    project_id: str,
    object_id: str,
    val: Any,
    builtin_object_class: str | None = None,
    extra: list[str] | None = None,
) -> str:
    """Compute the internal ref URI for an object.

    Combines digest computation with internal ref construction.
    The project_id must be an internal project ID — typically resolved once
    via project_ids_external_to_internal during weave.init and cached for
    the lifetime of the session.

    Pass extra to append a sub-path (e.g. ["attr", "rows", "id", "<digest>"]
    for a dataset row ref).
    """
    digest = compute_object_digest(val, builtin_object_class)
    return InternalObjectRef(
        project_id=project_id,
        name=object_id,
        version=digest,
        extra=extra or [],
    ).uri()


def compute_op_ref_uri(
    project_id: str,
    op_name: str,
    val: Any,
) -> str:
    """Compute the internal ref URI for an op.

    The project_id must be an internal project ID — typically resolved once
    via project_ids_external_to_internal during weave.init and cached for
    the lifetime of the session.
    """
    digest = compute_object_digest(val)
    return InternalOpRef(
        project_id=project_id,
        name=op_name,
        version=digest,
    ).uri()


def compute_table_ref_uri(
    project_id: str,
    row_digests: list[str],
) -> str:
    """Compute the internal ref URI for a table.

    The project_id must be an internal project ID — typically resolved once
    via project_ids_external_to_internal during weave.init and cached for
    the lifetime of the session.
    """
    digest = compute_table_digest(row_digests)
    return InternalTableRef(
        project_id=project_id,
        digest=digest,
    ).uri()


def compute_file_content_ref_uri(
    project_id: str,
    object_id: str,
    object_val: Any,
    attr_name: str,
) -> str:
    """Compute the internal ref URI for a file attribute within an object.

    Files are stored by digest via file_create and referenced as attributes
    on their parent object.  This returns the object ref with an extra
    path pointing at the attribute (e.g. .../object/name:version/attr/source).

    The project_id must be an internal project ID — typically resolved once
    via project_ids_external_to_internal during weave.init and cached for
    the lifetime of the session.
    """
    return compute_object_ref_uri(
        project_id,
        object_id,
        object_val,
        extra=["attr", attr_name],
    )
