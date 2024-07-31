import datetime
import typing

import weave.trace_server.trace_server_interface as tsi


def _make_call_status_from_exception_and_ended_at(
    exception: typing.Optional[str], ended_at: typing.Optional[datetime.datetime]
) -> typing.Literal["success", "error", "running"]:
    if exception is not None:
        return "error"
    elif ended_at is None:
        return "running"
    return "success"


def _op_name_simple_from_ref_str(ref_str: typing.Optional[str]) -> typing.Optional[str]:
    if ref_str is None:
        return None
    return ref_str.split("/")[-1].split(":")[0]


def make_derived_summary_map(
    summary_dump: typing.Optional[dict],
    started_at: typing.Optional[datetime.datetime],
    ended_at: typing.Optional[datetime.datetime],
    exception: typing.Optional[str],
    display_name: typing.Optional[str],
    op_name: typing.Optional[str],
) -> tsi.SummaryMap:
    status = _make_call_status_from_exception_and_ended_at(exception, ended_at)
    latency = (
        None if not started_at or not ended_at else (ended_at - started_at).microseconds
    )
    display_name = display_name or _op_name_simple_from_ref_str(op_name)
    weave_derived_fields = tsi.WeaveSummarySchema(
        nice_trace_name=display_name,
        status=status,
        latency=latency,
    )
    summary = summary_dump or {}
    summary["_weave"] = weave_derived_fields
    return typing.cast(tsi.SummaryMap, summary)
