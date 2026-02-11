from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

from weave.trace_server.object_class_util import process_incoming_object_val
from weave.trace_server.trace_server_interface_util import bytes_digest, str_digest


@dataclasses.dataclass(frozen=True)
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
    json_val = json.dumps(processed_val)
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
    row_json = json.dumps(row)
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
