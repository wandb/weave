import copy
import datetime
import json
from collections import OrderedDict, defaultdict
from typing import Any, Dict, Literal, Optional, Union

from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi


def make_feedback_query_req(
    project_id: str,
    calls: list[dict[str, Any]],
) -> tsi.FeedbackQueryReq:
    # make list of weave refs to calls, to be used in feedback query
    call_refs = []
    for call in calls:
        ref = ri.InternalCallRef(project_id=call["project_id"], id=call["id"])
        call_refs.append(ref.uri())

    # construct mogo style query
    query = tsi.Query(
        **{
            "$expr": {
                "$in": [
                    {"$getField": "weave_ref"},
                    [{"$literal": call_ref} for call_ref in call_refs],
                ]
            }
        }
    )
    feedback_query_req = tsi.FeedbackQueryReq(
        project_id=project_id,
        fields=[
            "feedback_type",
            "weave_ref",
            "payload",
            "creator",
            "created_at",
            "wb_user_id",
        ],
        query=query,
    )
    return feedback_query_req


def hydrate_calls_with_feedback(
    calls: list[dict[str, Any]], feedback: tsi.FeedbackQueryRes
) -> None:
    """Hydrate calls with feedback inplace."""
    feedback_map = defaultdict(list)
    # map feedback to calls
    for feedback_item in feedback.result:
        uri = ri.parse_internal_uri(feedback_item["weave_ref"])
        if isinstance(uri, ri.InternalCallRef):
            feedback_map[uri.id].append(feedback_item)

    for call in calls:
        feedback_items = feedback_map.get(call["id"], [])
        if not call.get("summary"):
            call["summary"] = {}
        if not call["summary"].get("weave"):
            call["summary"]["weave"] = {}
        call["summary"]["weave"]["feedback"] = feedback_items


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

    return tsi.SummaryMap(**summary)


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


def _load_json_maybe(value: Any) -> Optional[Dict[str, Any]]:
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
