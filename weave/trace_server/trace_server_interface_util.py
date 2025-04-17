import base64
import hashlib
from typing import Any

from weave.trace_server import refs_internal

TRACE_REF_SCHEME = "weave"
ARTIFACT_REF_SCHEME = "wandb-artifact"
WILDCARD_ARTIFACT_VERSION_AND_PATH = ":*"


def bytes_digest(json_val: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(json_val)
    hash_bytes = hasher.digest()
    base64_encoded_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64_encoded_hash.replace("-", "X").replace("_", "Y").rstrip("=")


def str_digest(json_val: str) -> str:
    return bytes_digest(json_val.encode())


def _order_dict(dictionary: dict) -> dict:
    return {
        k: _order_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(dictionary.items())
    }


valid_schemes = [
    TRACE_REF_SCHEME,
    ARTIFACT_REF_SCHEME,
    refs_internal.WEAVE_INTERNAL_SCHEME,
]


def extract_refs_from_values(
    vals: Any,
) -> list[str]:
    refs = []

    def _visit(val: Any) -> Any:
        if isinstance(val, dict):
            for v in val.values():
                _visit(v)
        elif isinstance(val, list):
            for v in val:
                _visit(v)
        elif isinstance(val, str) and any(
            val.startswith(scheme + "://") for scheme in valid_schemes
        ):
            refs.append(val)

    _visit(vals)
    return refs


def assert_non_null_wb_user_id(obj: Any) -> None:
    if not hasattr(obj, "wb_user_id") or obj.wb_user_id is None:
        raise ValueError("wb_user_id cannot be None")


def assert_null_wb_user_id(obj: Any) -> None:
    if hasattr(obj, "wb_user_id") and obj.wb_user_id is not None:
        raise ValueError("wb_user_id must be None")
