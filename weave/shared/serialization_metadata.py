"""Serialization metadata filtering shared by passive schemas and SDK objects."""

from typing import Any

# Metadata keys added by weave serialization that are not real model fields.
# These must be stripped before Pydantic validation since Object uses extra="forbid".
# Pydantic forbids underscore-prefixed fields by default, so there's no risk of collision.
_WEAVE_SERIALIZATION_METADATA_KEYS = {"_type", "_class_name", "_bases"}


def strip_weave_serialization_metadata(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            k: v for k, v in data.items() if k not in _WEAVE_SERIALIZATION_METADATA_KEYS
        }
    return data
