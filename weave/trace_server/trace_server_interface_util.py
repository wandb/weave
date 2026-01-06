from typing import Any

from weave.trace_server import refs_internal
from weave.trace_server.client_server_common.digest import bytes_digest, str_digest

# Re-export for backward compatibility
__all__ = ["bytes_digest", "str_digest"]

TRACE_REF_SCHEME = "weave"
ARTIFACT_REF_SCHEME = "wandb-artifact"
WILDCARD_ARTIFACT_VERSION_AND_PATH = ":*"


def _order_dict(dictionary: dict) -> dict:
    return {
        k: _order_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(dictionary.items())
    }


valid_internal_schemes = [
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
            val.startswith(scheme + ":///") for scheme in valid_internal_schemes
        ):
            try:
                parsed = refs_internal.parse_internal_uri(val)
                if parsed.uri() == val:
                    refs.append(val)
            except Exception:
                pass

    _visit(vals)
    return refs


def assert_non_null_wb_user_id(obj: Any) -> None:
    if not hasattr(obj, "wb_user_id") or obj.wb_user_id is None:
        raise ValueError("wb_user_id cannot be None")


def assert_null_wb_user_id(obj: Any) -> None:
    if hasattr(obj, "wb_user_id") and obj.wb_user_id is not None:
        raise ValueError("wb_user_id must be None")
