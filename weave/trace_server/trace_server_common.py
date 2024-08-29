import copy
import datetime
import json
from collections import OrderedDict
from typing import Any, Dict, Literal, Optional, Union

from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi


def make_derived_summary_fields(
    call_dict: Dict[str, Any], summary_key: Literal["summary", "summary_dump"]
) -> tsi.SummaryMap:
    """
    Make derived summary fields for a call.

    Summary is controlled by the user, but the `weave` summary key is
    used to store derived fields, adhering to the tsi.SummaryMap type.

    Args:
        call_dict: The call dict.
        summary_key: The key in the call dict that contains the summary. In
            the clickhouse server this is "summary_dump", but in sqlite
            it's "summary".

    Returns:
        The derived summary fields.
    """
    started_at_dt = _make_datetime_from_any(call_dict["started_at"])
    ended_at_dt = _make_datetime_from_any(call_dict.get("ended_at"))

    status = tsi.TraceStatus.SUCCESS
    if call_dict.get("exception"):
        status = tsi.TraceStatus.ERROR
    elif ended_at_dt is None:
        status = tsi.TraceStatus.RUNNING

    latency = None
    if ended_at_dt and started_at_dt:
        latency = (ended_at_dt - started_at_dt).microseconds

    display_name = call_dict.get("display_name")
    if not display_name:
        if ri.string_will_be_interpreted_as_ref(call_dict["op_name"]):
            op = ri.parse_internal_uri(call_dict["op_name"])
            if isinstance(op, ri.InternalObjectRef):
                display_name = op.name
        else:
            display_name = call_dict["op_name"]

    summary = _load_json_maybe(call_dict.get(summary_key)) or {}
    weave_summary = summary.get("weave", {})
    weave_summary["trace_name"] = display_name
    weave_summary["status"] = status
    if latency is not None:
        weave_summary["latency_ms"] = latency
    summary["weave"] = weave_summary

    return tsi.SummaryMap({"weave": weave_summary})


def _make_datetime_from_any(
    dt: Optional[Union[str, datetime.datetime]],
) -> Optional[datetime.datetime]:
    """
    Flexible datetime parser, accepts None, str and datetime.
    This allows database type agnostic parsing of dates.
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        return datetime.datetime.fromisoformat(dt)
    elif isinstance(dt, datetime.datetime):
        return dt


def _load_json_maybe(value: Any) -> Any:
    """
    Loads a JSON string or returns the value if it's not a string.
    Allows for database type agnostic parsing of JSON strings.
    """
    if isinstance(value, str):
        return json.loads(value)
    elif isinstance(value, dict):
        return value
    return None


def get_nested_key(d: Dict[str, Any], col: str) -> Optional[Any]:
    """
    Get a nested key from a dict. None if not found.

    Example:
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b.c") -> "d"
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b") -> {"c": "d"}
    get_nested_key({"a": {"b": {"c": "d"}}}, "foobar") -> None
    """

    def _get(data: Optional[Any], key: str) -> Optional[Any]:
        if not data or not isinstance(data, dict):
            return None
        return data.get(key)

    keys = col.split(".")
    curr: Optional[Any] = d
    for key in keys[:-1]:
        curr = _get(curr, key)
    return _get(curr, keys[-1])


def set_nested_key(d: Dict[str, Any], col: str, val: Any) -> None:
    """
    Set a nested key in a dict.

    Example:
    set_nested_key({"a": {"b": "c"}}, "a.b", "e") -> {"a": {"b": "e"}}
    set_nested_key({"a": {"b": "e"}}, "a.b.c", "e") -> {"a": {"b": {"c": "e"}}}
    """
    keys = col.split(".")
    if not keys[-1]:
        # If the columns is misformatted just return (ex: "a.b.")
        return

    curr = d
    for key in keys[:-1]:
        if key not in curr or not isinstance(curr[key], dict):
            curr[key] = {}
        curr = curr[key]
    curr[keys[-1]] = copy.deepcopy(val)


class LRUCache(OrderedDict):
    def __init__(self, max_size: int = 1000, *args: Any, **kwargs: Dict[str, Any]):
        self.max_size = max_size
        super().__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self and len(self) >= self.max_size:
            self.popitem(last=False)
        super().__setitem__(key, value)
