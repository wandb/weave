import re
from typing import Any, Literal, Optional

from weave.trace_server import refs_internal, validation_util
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH, MAX_OP_NAME_LENGTH
from weave.trace_server.errors import InvalidFieldError, InvalidRequest


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


def parent_id_validator(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return call_id_validator(s)


def display_name_validator(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return validation_util.require_max_str_len(s, MAX_DISPLAY_NAME_LENGTH)


def op_name_validator(s: str) -> str:
    if refs_internal.string_will_be_interpreted_as_ref(s):
        validation_util.require_internal_ref_uri(s, refs_internal.InternalOpRef)
    else:
        validation_util.require_max_str_len(s, MAX_OP_NAME_LENGTH)

    return s


def wb_user_id_validator(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return validation_util.require_base64(s)


def wb_run_id_validator(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    splits = s.split(":")

    if len(splits) != 2:
        raise ValueError(f"Invalid run id: {s}")

    validation_util.require_base64(splits[0])

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
def validate_dict_one_key(d: dict, key: str, typ: type) -> Any:
    if not isinstance(d, dict):
        raise InvalidRequest(f"Expected a dictionary, got {d}")
    keys = list(d.keys())
    if len(keys) != 1:
        raise InvalidRequest(f"Expected a dictionary with one key, got {d}")
    if keys[0] != key:
        raise InvalidRequest(f"Expected key {key}, got {keys[0]}")
    val = d[key]
    if not isinstance(val, typ):
        raise InvalidRequest(f"Expected value of type {typ}, got {type(val)}")
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
