"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.validation_util import (
    OTEL_SPAN_ID_HEX_LENGTH,
    OTEL_TRACE_ID_HEX_LENGTH,
    CHValidationError,
    base64,
    refs_internal,
    require_base64,
    require_internal_ref_uri,
    require_max_str_len,
    require_otel_span_id,
    require_otel_trace_id,
    require_uuid,
    uuid,
)

__all__ = [
    "OTEL_SPAN_ID_HEX_LENGTH",
    "OTEL_TRACE_ID_HEX_LENGTH",
    "CHValidationError",
    "base64",
    "refs_internal",
    "require_base64",
    "require_internal_ref_uri",
    "require_max_str_len",
    "require_otel_span_id",
    "require_otel_trace_id",
    "require_uuid",
    "uuid",
]
