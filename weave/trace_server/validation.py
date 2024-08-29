import re
import typing

from weave.trace_server import refs_internal

from . import validation_util

# Temporary flag to disable database-side validation of object ids.
# We want to enable this be default, but we need to wait until >95% of users
# are on weave>=0.51.1, when we can enforce the charset check on the db
# side.
#
# Actions:
# 1. (ETA: Sept 30) - Verify that 95% of users are on weave>=0.51.1, or
#    that 95% of new objects have the valid charset.
# 2. Remove this flag (thereby setting this to True), and add a check to the
#    server-side validation code to ensure that the charset is valid.
# 3. Release and deploy backend.
SHOULD_ENFORCE_OBJ_ID_CHARSET = False


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
        invalid_char_set = list(set(invalid_chars))
        raise ValueError(
            f"Invalid object name: {name}. Contains invalid characters: {invalid_char_set}. Please upgrade your `weave` package to `>0.51.0` to prevent this error."
        )

    if not name:
        raise ValueError("Object name cannot be empty")


def object_id_validator(s: str) -> str:
    if SHOULD_ENFORCE_OBJ_ID_CHARSET:
        _validate_object_name_charset(s)
    return validation_util.require_max_str_len(s, 128)


def refs_list_validator(s: typing.List[str]) -> typing.List[str]:
    return [validation_util.require_internal_ref_uri(ref) for ref in s]
