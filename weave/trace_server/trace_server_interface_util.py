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
    if any(
        val.startswith(scheme + ":///") for scheme in valid_internal_schemes
    ):
        try:
            parsed = refs_internal.parse_internal_uri(val)
            if parsed.uri() == val:
                return parsed
        except Exception:
            pass
    return False

def _visit_refs(
    vals: Any,
    visit_fn: Callable[[str], Any],
) -> Any:
    def _visit(val: Any) -> Any:
        if isinstance(val, dict):
            return {k: _visit(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [_visit(v) for v in val]
        elif isinstance(val, str):
            if parsed := _maybe_parse_ref(val):
                return visit_fn(parsed)
        return val
    return _visit(vals)

def extract_refs_from_values(
    vals: Any,
) -> list[str]:
    refs = []

    def visit_fn(parsed: refs_internal.InternalRef) -> Any:
        refs.append(parsed)

    _visit_refs(vals, visit_fn)

    return refs


def assert_non_null_wb_user_id(obj: Any) -> None:
    if not hasattr(obj, "wb_user_id") or obj.wb_user_id is None:
        raise ValueError("wb_user_id cannot be None")


def assert_null_wb_user_id(obj: Any) -> None:
    if hasattr(obj, "wb_user_id") and obj.wb_user_id is not None:
        raise ValueError("wb_user_id must be None")


def calculate_unbounded_inputs_hash(inputs: dict[str, Any], bounded_input_key: str = "self") -> str:
    """
    This function calculates a hash of the unbounded inputs. This is useful as
    it can be used to local calls which have identical inputs (other than the `self`
    argument).

    Critically, this also converts all refs to their location-agnostic representation.

    PROBLEM: this doesn't work for cases where you want to exclude one of the inputs from the hash. (eg. model from p_a_s)
    """

    def _visit_fn(parsed: refs_internal.InternalRef) -> Any:
        agnostic_ref = parsed.digest
        if hasattr(parsed, "extra"):
            agnostic_ref += "/".join(parsed.extra)
        return agnostic_ref
    
    inputs_without_bounded_input = {k: v for k, v in inputs.items() if k != bounded_input_key}

    bounded_inputs = _visit_refs(inputs_without_bounded_input, _visit_fn)
    return str_digest(json.dumps(bounded_inputs))