import copy
import datetime
import json
from collections import OrderedDict
from typing import Any, Dict, Literal, Optional, Union, cast

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.refs_internal import InternalObjectRef, parse_internal_uri


def make_derived_summary_fields(
    call_dict: Dict[str, Any], summary_key: Literal["summary", "summary_dump"]
) -> tsi.SummaryMap:
    display_name = call_dict.get("display_name")
    started_at_dt = _make_datetime_from_any(call_dict["started_at"])
    ended_at_dt = _make_datetime_from_any(call_dict.get("ended_at"))
    status = _make_call_status_from_exception_and_ended_at(
        call_dict.get("exception"), ended_at_dt
    )

    latency = None
    if ended_at_dt and started_at_dt:
        latency = (ended_at_dt - started_at_dt).microseconds

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
    summary = _load_json_maybe(call_dict.get(summary_key)) or {}
    summary["weave"] = weave_derived_fields
    return cast(tsi.SummaryMap, summary)


def _make_call_status_from_exception_and_ended_at(
    exception: Optional[str], ended_at: Optional[datetime.datetime]
) -> Literal["success", "error", "running"]:
    if exception is not None:
        return "error"
    elif ended_at is None:
        return "running"
    return "success"


def _make_datetime_from_any(
    dt: Optional[Union[str, datetime.datetime]],
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


def _load_json_maybe(value: Any) -> Any:
    """
    Loads a JSON string or returns the value if it's not a string.
    Allows for database agnostic parsing of JSON strings.
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
