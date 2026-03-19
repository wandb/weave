from typing import Any

from weave.shared import refs_internal

TRACE_REF_SCHEME = "weave"
ARTIFACT_REF_SCHEME = "wandb-artifact"
WILDCARD_ARTIFACT_VERSION_AND_PATH = ":*"


valid_internal_schemes = [
    ARTIFACT_REF_SCHEME,
    refs_internal.WEAVE_INTERNAL_SCHEME,
]


def split_exact_and_wildcard_values(values: list[str]) -> tuple[list[str], list[str]]:
    exact_values: list[str] = []
    wildcard_values: list[str] = []
    for value in values:
        if value.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
            wildcard_values.append(value)
        else:
            exact_values.append(value)
    return exact_values, wildcard_values


def wildcard_version_value_to_ref_prefix(value: str) -> str:
    if not value.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
        raise ValueError(f"Value does not end with wildcard suffix: {value}")
    return value[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + ":"


def wildcard_version_value_to_like_prefix(value: str) -> str:
    return wildcard_version_value_to_ref_prefix(value) + "%"


def extract_refs_from_values(
    vals: Any,
) -> list[str]:
    seen: dict[str, None] = {}

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
                if parsed.uri == val:
                    seen[val] = None
            except Exception:
                pass

    _visit(vals)
    return list(seen)


def assert_non_null_wb_user_id(obj: Any) -> None:
    if not hasattr(obj, "wb_user_id") or obj.wb_user_id is None:
        raise ValueError("wb_user_id cannot be None")


def assert_null_wb_user_id(obj: Any) -> None:
    if hasattr(obj, "wb_user_id") and obj.wb_user_id is not None:
        raise ValueError("wb_user_id must be None")
