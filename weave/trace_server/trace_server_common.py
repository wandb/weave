import datetime
from typing import Literal, Optional, cast

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.refs_internal import InternalObjectRef, parse_internal_uri


def _make_call_status_from_exception_and_ended_at(
    exception: Optional[str], ended_at: Optional[datetime.datetime]
) -> Literal["success", "error", "running"]:
    if exception is not None:
        return "error"
    elif ended_at is None:
        return "running"
    return "success"


def make_derived_summary_fields(call_dict: dict, summary_key: str) -> tsi.SummaryMap:
    started_at = call_dict["started_at"]
    ended_at = call_dict.get("ended_at")
    exception = call_dict.get("exception")
    display_name = call_dict.get("display_name")
    op_name = call_dict["op_name"]
    ended_at_dt = (
        None if ended_at is None else datetime.datetime.fromisoformat(ended_at)
    )
    started_at_dt = datetime.datetime.fromisoformat(started_at)
    status = _make_call_status_from_exception_and_ended_at(exception, ended_at_dt)
    latency = None if not ended_at_dt else (ended_at_dt - started_at_dt).microseconds
    if not display_name:
        op = parse_internal_uri(op_name)
        if isinstance(op, InternalObjectRef):
            display_name = op.name
        else:
            display_name = op_name

    weave_derived_fields = tsi.WeaveSummarySchema(
        nice_trace_name=display_name,
        status=status,
        latency=latency,
    )
    summary = call_dict.get(summary_key) or {}
    summary["weave"] = weave_derived_fields
    return cast(tsi.SummaryMap, summary)
