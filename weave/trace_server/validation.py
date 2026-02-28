import re
from typing import Any, Literal

from weave.shared import refs_internal
from weave.trace_server import validation_util
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH, MAX_OP_NAME_LENGTH
from weave.trace_server.errors import InvalidFieldError, InvalidRequest

# --- Tag and Alias validation ---
# Follows W&B Models conventions:
#   - Tags: alphanumeric, hyphens, underscores, single spaces between words,
#     max 256 chars.  Matches W&B Models TAG_REGEX.
#   - Aliases: broad charset, disallow "/" and ":", length 1-128,
#     reserve "latest" and version patterns (v\d+), reject whitespace-only.

MAX_ALIAS_LENGTH = 128
MAX_TAG_LENGTH = 256
TAG_REGEX = re.compile(r"^[-\w]+( [-\w]+)*$")
_INVALID_ALIAS_CHARACTERS = frozenset("/:")
_VERSION_LIKE_PATTERN = re.compile(r"^v\d+$")
_RESERVED_ALIAS_NAMES = {"latest"}


def validate_tag_name(name: str) -> None:
    """Validate a tag name against W&B Models TAG_REGEX.

    Allowed: alphanumeric, hyphens, underscores, single spaces between words.
    Max length: 256 characters.
    """
    if not name:
        raise ValueError("tag name must not be empty")
    if len(name) > MAX_TAG_LENGTH:
        raise ValueError(f"tag name must be at most {MAX_TAG_LENGTH} characters")
    if not TAG_REGEX.match(name):
        raise ValueError(
            f"tag name {name!r} is invalid: only alphanumeric characters, "
            "hyphens, underscores, and single spaces between words are allowed"
        )


def validate_alias_name(name: str) -> None:
    """Validate an alias name. Disallows '/' and ':', reserves 'latest' and version indices."""
    if not name:
        raise ValueError("alias name must not be empty")
    if not name.strip():
        raise ValueError("alias name must not be whitespace-only")
    if len(name) > MAX_ALIAS_LENGTH:
        raise ValueError(f"alias name must be at most {MAX_ALIAS_LENGTH} characters")
    for ch in name:
        if ch in _INVALID_ALIAS_CHARACTERS:
            raise ValueError(f"alias name cannot contain character '{ch}'")
    if _VERSION_LIKE_PATTERN.match(name):
        raise ValueError(
            f"alias name '{name}' is reserved (matches version pattern v<number>)"
        )
    if name in _RESERVED_ALIAS_NAMES:
        raise ValueError(f"alias name '{name}' is reserved")


def project_id_validator(s: str) -> str:
    return validation_util.require_base64(s)


def call_id_validator(s: str) -> str:
    try:
        return validation_util.require_otel_span_id(s)
    except validation_util.CHValidationError:
        return validation_util.require_uuid(s)


def trace_id_validator(s: str) -> str:
    try:
        return validation_util.require_otel_trace_id(s)
    except validation_util.CHValidationError:
        return validation_util.require_uuid(s)


def parent_id_validator(s: str | None) -> str | None:
    if s is None:
        return None
    return call_id_validator(s)


def display_name_validator(s: str | None) -> str | None:
    if s is None:
        return None
    return validation_util.require_max_str_len(s, MAX_DISPLAY_NAME_LENGTH)


def op_name_validator(s: str) -> str:
    if refs_internal.string_will_be_interpreted_as_ref(s):
        validation_util.require_internal_ref_uri(s, refs_internal.InternalOpRef)
    else:
        validation_util.require_max_str_len(s, MAX_OP_NAME_LENGTH)

    return s


def wb_user_id_validator(s: str | None) -> str | None:
    if s is None:
        return None
    return validation_util.require_base64(s)


def wb_run_id_validator(s: str | None) -> str | None:
    if s is None:
        return None
    splits = s.split(":")

    if len(splits) != 2:
        raise ValueError(f"Invalid run id: {s}")

    validation_util.require_base64(splits[0])

    return s


def wb_run_step_validator(s: int | None) -> int | None:
    if s is None:
        return None
    if not isinstance(s, int):
        raise TypeError("wb_run_step must be an int")
    if s < 0:
        raise ValueError("wb_run_step must be non-negative")
    return s


def _validate_object_name_charset(name: str) -> None:
    # Object names must be alphanumeric with dashes
    invalid_chars = re.findall(r"[^\w._-]", name)
    if invalid_chars:
        invalid_char_set = list(set(invalid_chars))
        raise InvalidFieldError(
            f"Invalid object name: {name}. Contains invalid characters: {invalid_char_set}. Please upgrade your `weave` package to `>0.51.0` to prevent this error."
        )

    if not name:
        raise InvalidFieldError("Object name cannot be empty")


def object_id_validator(s: str) -> str:
    _validate_object_name_charset(s)
    return validation_util.require_max_str_len(s, 128)


def refs_list_validator(s: list[str]) -> list[str]:
    return [validation_util.require_internal_ref_uri(ref) for ref in s]


# Invalid purge should only trigger if the user calls directly to the server with a query that is not ( eq_ id or in_ ids )
MESSAGE_INVALID_PURGE = "Can only purge by specifying one or more ids"


# Validate a dictionary only has one specific key
def validate_dict_one_key(d: dict, key: str, _type: type) -> Any:
    if not isinstance(d, dict):
        raise InvalidRequest(f"Expected a dictionary, got {d}")
    keys = list(d.keys())
    if len(keys) != 1:
        raise InvalidRequest(f"Expected a dictionary with one key, got {d}")
    if keys[0] != key:
        raise InvalidRequest(f"Expected key {key}, got {keys[0]}")
    val = d[key]
    if not isinstance(val, _type):
        raise InvalidRequest(f"Expected value of type {_type}, got {type(val)}")
    return val


# Only allowed to use eq_ id or in_ ids for purge requests
def validate_purge_req_one(
    value: Any,
    invalid_message: str = MESSAGE_INVALID_PURGE,
    operator: Literal["eq_", "in_"] = "eq_",
) -> None:
    tup = validate_dict_one_key(value, operator, tuple)
    if len(tup) != 2:
        raise InvalidRequest(invalid_message)
    get_field = validate_dict_one_key(tup[0], "get_field_", str)
    if get_field != "id":
        raise InvalidRequest(invalid_message)

    if operator == "eq_":
        literal = validate_dict_one_key(tup[1], "literal_", str)
        if not isinstance(literal, str):
            raise InvalidRequest(invalid_message)
    elif operator == "in_":
        for literal_obj in tup[1]:
            literal = validate_dict_one_key(literal_obj, "literal_", str)
            if not isinstance(literal, str):
                raise InvalidRequest(invalid_message)


# validate a purge query with multiple eq conditions
def validate_purge_req_multiple(
    value: Any, invalid_message: str = MESSAGE_INVALID_PURGE
) -> None:
    if not isinstance(value, list):
        raise InvalidRequest(invalid_message)
    for item in value:
        validate_purge_req_one(item)
