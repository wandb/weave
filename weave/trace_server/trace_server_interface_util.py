import base64
import hashlib
import json
from typing import Any, Callable, Optional

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


def any_digest(item: Any) -> str:
    return str_digest(json.dumps(item))


def _replace_refs_with_content_ids(item: Any) -> Any:
    """
    This is a critical function as it allows us to convert any primtive payload
    into a location-agnostic payload. Specifically: any occurance of a "ref" in an
    object contains the ownership path and the digest itself. for example:

    weave-internal:///project_id/object_id/digest/extra

    `weave-internal:///project_id/object_id` is simply the location of the object (NOT the content id),

    but

    `digest/extra` is the digest of the object and the extra path (if it exists) - this is unique based on the content of the object

    This function replaces all occurance of refs with the digest/extra string.
    """

    def _visit_fn(parsed: refs_internal.InternalRef, val: str) -> str:
        if isinstance(
            parsed, (refs_internal.InternalObjectRef, refs_internal.InternalTableRef)
        ):
            return parsed.content_id()
        return val

    return _visit_refs(item, _visit_fn)


def _ref_aware_any_digest(item: Any) -> str:
    """This function returns the weave digest for any item, replacing all refs with their content digests."""
    ref_replaced_item = _replace_refs_with_content_ids(item)
    return any_digest(ref_replaced_item)


def _order_dict(dictionary: dict) -> dict:
    return {
        k: _order_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(dictionary.items())
    }


valid_internal_schemes = [
    ARTIFACT_REF_SCHEME,
    refs_internal.WEAVE_INTERNAL_SCHEME,
]


def _maybe_parse_ref(val: Any) -> Optional[refs_internal.InternalRef]:
    if any(val.startswith(scheme + ":///") for scheme in valid_internal_schemes):
        try:
            parsed = refs_internal.parse_internal_uri(val)
            if parsed.uri() == val:
                return parsed
        except Exception:
            pass
    return None


def _visit_refs(
    vals: Any,
    visit_fn: Callable[[refs_internal.InternalRef, str], Any],
) -> Any:
    def _visit(val: Any) -> Any:
        if isinstance(val, dict):
            return {k: _visit(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [_visit(v) for v in val]
        elif isinstance(val, str):
            if parsed := _maybe_parse_ref(val):
                return visit_fn(parsed, val)
        return val

    return _visit(vals)


def extract_refs_from_values(
    vals: Any,
) -> list[str]:
    refs: list[str] = []

    def visit_fn(parsed: refs_internal.InternalRef, val: str) -> Any:
        refs.append(val)
        return val

    _visit_refs(vals, visit_fn)

    return refs


def assert_non_null_wb_user_id(obj: Any) -> None:
    if not hasattr(obj, "wb_user_id") or obj.wb_user_id is None:
        raise ValueError("wb_user_id cannot be None")


def assert_null_wb_user_id(obj: Any) -> None:
    if hasattr(obj, "wb_user_id") and obj.wb_user_id is not None:
        raise ValueError("wb_user_id must be None")


def calculate_input_digests(inputs: dict[str, Any]) -> dict[str, str]:
    """This calculates the digest for each input"""
    return {k: _ref_aware_any_digest(v) for k, v in inputs.items()}
