import typing

from weave.trace_server import refs_internal

from . import validation_util
from .errors import InvalidRequest


def project_id_validator(s: str) -> str:
    return validation_util.require_base64(s)


def call_id_validator(s: str) -> str:
    return validation_util.require_uuid(s)


def trace_id_validator(s: str) -> str:
    return validation_util.require_uuid(s)


def parent_id_validator(s: typing.Optional[str]) -> typing.Optional[str]:
    if s is None:
        return None
    return call_id_validator(s)


def display_name_validator(s: typing.Optional[str]) -> typing.Optional[str]:
    if s is None:
        return None
    return validation_util.require_max_str_len(s, 128)


def op_name_validator(s: str) -> str:
    if refs_internal.string_will_be_interpreted_as_ref(s):
        validation_util.require_internal_ref_uri(s, refs_internal.InternalOpRef)
    else:
        validation_util.require_max_str_len(s, 128)

    return s


def wb_user_id_validator(s: typing.Optional[str]) -> typing.Optional[str]:
    if s is None:
        return None
    return validation_util.require_base64(s)


def wb_run_id_validator(s: typing.Optional[str]) -> typing.Optional[str]:
    if s is None:
        return None
    splits = s.split(":")

    if len(splits) != 2:
        raise ValueError(f"Invalid run id: {s}")

    validation_util.require_base64(splits[0])

    return s


def object_id_validator(s: str) -> str:
    return validation_util.require_max_str_len(s, 128)


def refs_list_validator(s: typing.List[str]) -> typing.List[str]:
    return [validation_util.require_internal_ref_uri(ref) for ref in s]


MESSAGE_INVALID_PURGE = "Can only purge by specifying one or more ids"


def validate_dict_one_key(d: dict, key: str, typ: type) -> typing.Any:
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


def validate_purge_req_one(
    value: typing.Any, invalid_message: str = MESSAGE_INVALID_PURGE
) -> None:
    tup = validate_dict_one_key(value, "eq_", tuple)
    if len(tup) != 2:
        raise InvalidRequest(invalid_message)
    get_field = validate_dict_one_key(tup[0], "get_field_", str)
    if get_field != "id":
        raise InvalidRequest(invalid_message)
    literal = validate_dict_one_key(tup[1], "literal_", str)
    if not isinstance(literal, str):
        raise InvalidRequest(invalid_message)


def validate_purge_req_in(
    value: typing.Any, invalid_message: str = MESSAGE_INVALID_PURGE
) -> None:
    tup = validate_dict_one_key(value, "in_", tuple)
    if len(tup) != 2:
        raise InvalidRequest(invalid_message)
    get_field = validate_dict_one_key(tup[0], "get_field_", str)
    if get_field != "id":
        raise InvalidRequest(invalid_message)
    for literal_obj in tup[1]:
        literal = validate_dict_one_key(literal_obj, "literal_", str)
        if not isinstance(literal, str):
            raise InvalidRequest(invalid_message)


def validate_purge_req_multiple(
    value: typing.Any, invalid_message: str = MESSAGE_INVALID_PURGE
) -> None:
    if not isinstance(value, list):
        raise InvalidRequest(invalid_message)
    for item in value:
        validate_purge_req_one(item)
