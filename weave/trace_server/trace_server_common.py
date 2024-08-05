import datetime
import typing


def make_call_status_from_exception_and_ended_at(
    exception: typing.Optional[str], ended_at: typing.Optional[datetime.datetime]
) -> typing.Literal["success", "error", "running"]:
    if exception is not None:
        return "error"
    elif ended_at is None:
        return "running"
    return "success"


def op_name_simple_from_ref_str(ref_str: typing.Optional[str]) -> typing.Optional[str]:
    if ref_str is None:
        return None
    return ref_str.split("/")[-1].split(":")[0]
