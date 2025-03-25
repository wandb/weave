import base64
import uuid
from typing import Optional

from weave.trace_server import refs_internal


class CHValidationError(Exception):
    pass


def require_otel_trace_id(s: str) -> str:
    lower_s = s.lower()
    if lower_s != s:
        raise CHValidationError(f"Invalid Trace ID: {s}. Trace ID must be lowercase")

    # 16 Bytes is a hex string of len 32
    if len(s) != 32:
        raise CHValidationError(f"Invalid Trace ID: {s}. Trace ID must be 16 bytes")
    return s


def require_otel_span_id(s: str) -> str:
    lower_s = s.lower()
    if lower_s != s:
        raise CHValidationError(f"Invalid Span ID: {s}. Span ID must be lowercase")

    # 8 Bytes is a hex string of len 16
    if len(s) != 16:
        raise CHValidationError(f"Invalid Span ID: {s}. Span ID must be 8 bytes")
    return s


def require_uuid(s: str) -> str:
    lower_s = s.lower()
    if lower_s != s:
        raise CHValidationError(f"Invalid UUID: {s}. UUID must be lowercase")

    try:
        s_prime = str(uuid.UUID(s))
    except ValueError:
        raise CHValidationError(f"Invalid UUID: {s}. Unable to parse")

    if s_prime != s:
        raise CHValidationError(f"Invalid UUID: {s}. UUID did not round-trip")

    return s


def require_base64(s: str) -> str:
    try:
        s_prime = base64.b64encode(base64.b64decode(s)).decode("utf-8")
    except Exception as e:
        raise CHValidationError(f"Invalid base64 string: {s}.")

    if s_prime != s:
        raise CHValidationError(
            f"Invalid base64 string: {s}. Base64 did not round-trip"
        )

    return s


def require_internal_ref_uri(s: str, refClass: Optional[type] = None) -> str:
    if not s.startswith(
        f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///"
    ) and not s.startswith(f"{refs_internal.ARTIFACT_REF_SCHEME}:///"):
        raise CHValidationError(
            f"Invalid ref: {s}. Must start with {refs_internal.WEAVE_INTERNAL_SCHEME}:/// "
            f"or {refs_internal.ARTIFACT_REF_SCHEME}:///"
        )

    parsed = refs_internal.parse_internal_uri(s)

    if refClass is not None and not isinstance(parsed, refClass):
        raise CHValidationError(f"Invalid ref: {s}. Must be of type {str(refClass)}")
    parsed_str = parsed.uri()
    if parsed_str != s:
        raise CHValidationError(f"Invalid ref: {s}. Ref did not round-trip")
    return s


def require_max_str_len(s: str, length: int) -> str:
    if len(s) > length:
        raise CHValidationError(f"String too long: {s}. Max length is {length}")
    return s
