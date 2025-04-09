import copy
import datetime
from collections import OrderedDict, defaultdict
from collections.abc import Iterator
from typing import Any, Optional, cast

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
            "runnable_ref",
            "call_ref",
            "trigger_ref",
            "annotation_ref",
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
    summary: dict[str, Any],
    op_name: str,
    started_at: Optional[datetime.datetime] = None,
    ended_at: Optional[datetime.datetime] = None,
    exception: Optional[str] = None,
    display_name: Optional[str] = None,
) -> tsi.SummaryMap:
    """
    Make derived summary fields for a call.

    Summary is controlled by the user, but the `weave` summary key is
    used to store derived fields, adhering to the tsi.SummaryMap type.
    """
    weave_summary = summary.pop("weave", {})

    status = tsi.TraceStatus.SUCCESS
    if exception:
        status = tsi.TraceStatus.ERROR
    elif ended_at is None:
        status = tsi.TraceStatus.RUNNING
    weave_summary["status"] = status

    if ended_at and started_at:
        days = (ended_at - started_at).days
        seconds = (ended_at - started_at).seconds
        milliseconds = (ended_at - started_at).microseconds // 1000
        weave_summary["latency_ms"] = (
            days * 24 * 60 * 60 + seconds
        ) * 1000 + milliseconds

    if display_name:
        weave_summary["display_name"] = display_name
    else:
        if ri.string_will_be_interpreted_as_ref(op_name):
            op = ri.parse_internal_uri(op_name)
            if isinstance(op, ri.InternalObjectRef):
                weave_summary["trace_name"] = op.name
        else:
            weave_summary["trace_name"] = op_name

    summary["weave"] = weave_summary
    return cast(tsi.SummaryMap, summary)


def empty_str_to_none(val: Optional[str]) -> Optional[str]:
    return val if val != "" else None


def get_nested_key(d: dict[str, Any], col: str) -> Optional[Any]:
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


def set_nested_key(d: dict[str, Any], col: str, val: Any) -> None:
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
    def __init__(self, max_size: int = 1000, *args: Any, **kwargs: dict[str, Any]):
        self.max_size = max_size
        super().__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self and len(self) >= self.max_size:
            self.popitem(last=False)
        super().__setitem__(key, value)


class DynamicBatchProcessor:
    """Helper class to handle dynamic batch processing with growing batch sizes."""

    def __init__(self, initial_size: int, max_size: int, growth_factor: int):
        self.batch_size = initial_size
        self.max_size = max_size
        self.growth_factor = growth_factor

    def make_batches(self, iterator: Iterator[Any]) -> Iterator[list[Any]]:
        batch = []

        for item in iterator:
            batch.append(item)

            if len(batch) >= self.batch_size:
                yield batch

                batch = []
                self.batch_size = self._compute_batch_size()

        if batch:
            yield batch

    def _compute_batch_size(self) -> int:
        return min(self.max_size, self.batch_size * self.growth_factor)


def digest_is_version_like(digest: str) -> tuple[bool, int]:
    """
    Check if a digest is a version like string.

    Examples:
    - v1 -> True, 1
    - oioZ7zgsCq4K7tfFQZRubx3ZGPXmFyaeoeWHHd8KUl8 -> False, -1
    """
    if not digest.startswith("v"):
        return (False, -1)
    try:
        return (True, int(digest[1:]))
    except ValueError:
        return (False, -1)


MAX_FILTER_LENGTH = 1000


def assert_parameter_length_less_than_max(
    param_name: str, arr_len: int, max_length: int = MAX_FILTER_LENGTH
) -> None:
    if arr_len > max_length:
        raise ValueError(
            f"Parameter: '{param_name}' request length is greater than max length ({max_length}). Actual length: {arr_len}"
        )
