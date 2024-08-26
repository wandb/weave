import datetime
from typing import Any, Dict, Literal, Optional, cast

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


def _make_datetime_from_any(
    dt: Optional[str | datetime.datetime],
) -> Optional[datetime.datetime]:
    """
    Flexible datetime parser, accepts None, str and datetime.
    This allows database agnostic parsing of datetime objects.
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        return datetime.datetime.fromisoformat(dt)
    elif isinstance(dt, datetime.datetime):
        return dt
    return None


def make_derived_summary_fields(
    call_dict: Dict[str, Any], summary_key: str
) -> tsi.SummaryMap:
    display_name = call_dict.get("display_name")
    started_at_dt = _make_datetime_from_any(call_dict["started_at"])
    ended_at_dt = _make_datetime_from_any(call_dict.get("ended_at"))
    status = _make_call_status_from_exception_and_ended_at(
        call_dict.get("exception"), ended_at_dt
    )
    latency = None if not ended_at_dt else (ended_at_dt - started_at_dt).microseconds
    if not display_name:
        op = parse_internal_uri(call_dict["op_name"])
        if isinstance(op, InternalObjectRef):
            display_name = op.name
        else:
            display_name = call_dict["op_name"]

    weave_derived_fields = tsi.WeaveSummarySchema(
        nice_trace_name=display_name,
        status=status,
        latency=latency,
    )
    summary = call_dict.get(summary_key) or {}
    summary["weave"] = weave_derived_fields
    return cast(tsi.SummaryMap, summary)
