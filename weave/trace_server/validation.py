import typing

from . import validation_util


def project_id_validator(s: typing.Optional[str]) -> typing.Optional[s]:
    if s is None:
        return None
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
    return validation_util.assert_str_128(s)


def op_name_validator(s: str) -> str:
    if "://" in s:
        validation_util.assert_valid_ref(s)
    else:
        validation_util.assert_str_128(s)


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
    return validation_util.assert_str_128(s)
