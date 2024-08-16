import re
import typing

from weave.trace_server import refs_internal

from . import validation_util


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


def _validate_object_name_charset(name: str) -> None:
    # Object names must be alphanumeric with dashes
    invalid_chars = re.findall(r"[^\w._-]", name)
    if invalid_chars:
        raise ValueError(
            f"Invalid object name: {name}. Contains invalid characters: {invalid_chars}"
        )

    if not name:
        raise ValueError("Object name cannot be empty")


def object_id_validator(s: str) -> str:
    _validate_object_name_charset(s)
    return validation_util.require_max_str_len(s, 128)


def refs_list_validator(s: typing.List[str]) -> typing.List[str]:
    return [validation_util.require_internal_ref_uri(ref) for ref in s]
