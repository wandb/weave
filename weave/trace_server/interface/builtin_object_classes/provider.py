"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.interface.builtin_object_classes.provider import (
    BLOCKED_HEADER_RE,
    INVALID_BASE_URL_MSG,
    ConfigDict,
    Enum,
    Field,
    InvalidRequest,
    Provider,
    ProviderModel,
    ProviderReturnType,
    _validate_provider_base_url,
    base_object_def,
    field_validator,
    is_publicly_routable_url,
    re,
    sanitize_name_for_object_id,
    urlparse,
)

__all__ = [
    "BLOCKED_HEADER_RE",
    "INVALID_BASE_URL_MSG",
    "ConfigDict",
    "Enum",
    "Field",
    "InvalidRequest",
    "Provider",
    "ProviderModel",
    "ProviderReturnType",
    "_validate_provider_base_url",
    "base_object_def",
    "field_validator",
    "is_publicly_routable_url",
    "re",
    "sanitize_name_for_object_id",
    "urlparse",
]
