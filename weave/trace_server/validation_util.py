import base64
import typing
import uuid

from . import refs_internal


def require_uuid(s: str) -> str:
    lower_s = s.lower()
    if lower_s != s:
        raise ValueError(f"UUIDs must be lowercase: {s}")

    try:
        s_prime = str(uuid.UUID(s))
    except ValueError:
        raise ValueError(f"Invalid UUID: {s}")

    if s_prime != s:
        raise ValueError(f"Invalid UUID: {s}")

    return s


def require_base64(s: str) -> str:
    try:
        s_prime = base64.b64encode(base64.b64decode(s)).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {s}")

    if s_prime != s:
        raise ValueError(f"Invalid base64 string: {s}")

    return s


def require_internal_ref_uri(
    s: str, refClass: typing.Optional[typing.Type] = None
) -> str:
    if not s.startswith(f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///"):
        raise ValueError(f"Invalid ref: {s}")

    parsed = refs_internal.parse_internal_uri(s)

    if refClass is not None and not isinstance(parsed, refClass):
        raise ValueError(f"Invalid ref: {s}")
    parsed_str = parsed.uri()
    if parsed_str != s:
        raise ValueError(f"Invalid ref: {s}")
    return s


def require_max_str_len(s: str, length: int) -> str:
    if len(s) >= length:
        raise ValueError(f"String too long: {s}")
    return s
