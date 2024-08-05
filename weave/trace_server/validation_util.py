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
        s_prime = base64.b64encode(base64.b64decode(s))
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {s}")

    if s_prime != s:
        raise ValueError(f"Invalid base64 string: {s}")

    return s


def assert_valid_ref(s: str) -> str:
    parsed = refs_internal.parse_internal_uri(s)
    parsed_str = parsed.uri()
    if parsed_str != s:
        raise ValueError(f"Invalid ref: {s}")
    return s


def make_assert_valid_len_str(length: int) -> typing.Callable[[str], str]:
    def assert_valid_len_str(s: str) -> str:
        if len(s) >= length:
            raise ValueError(f"String too long: {s}")
        return s

    return assert_valid_len_str


assert_str_128 = make_assert_valid_len_str(128)
