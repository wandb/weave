import copy
from collections import OrderedDict, defaultdict
from typing import Any, Dict, Literal, Optional

from weave.trace_server.refs_internal import InternalCallRef
from weave.trace_server.trace_server_interface import (
    FeedbackQueryReq,
    Query,
    TraceServerInterface,
)


def hydrate_calls_with_feedback(
    trace_server: TraceServerInterface,
    calls: list[dict[str, Any]],
    feedback_format: Literal["all", "counts"],
) -> list[dict[str, Any]]:
    feedback_map = defaultdict(list)

    # Batch feedback queries by project_id
    project_id_to_weave_refs = defaultdict(list)
    for call in calls:
        weave_ref = InternalCallRef(project_id=call["project_id"], id=call["id"])
        project_id_to_weave_refs[call["project_id"]].append(weave_ref.uri())

    # This goes project by project for extra safety, even though
    # calls_stream_query should only return calls in a single project
    for project_id, call_refs in project_id_to_weave_refs.items():
        query = Query(
            **{
                "$expr": {
                    "$in": [
                        {"$getField": "weave_ref"},
                        [{"$literal": call_ref} for call_ref in call_refs],
                    ]
                }
            }
        )
        feedback_query_req = FeedbackQueryReq(
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
        feedback = trace_server.feedback_query(req=feedback_query_req).result
        for feedback_item in feedback:
            _id = feedback_item["weave_ref"].split("/")[-1]
            feedback_map[_id].append(feedback_item)

    for call in calls:
        feedback_items = feedback_map.get(call["id"]) or []
        if "summary" not in call:
            call["summary"] = {}

        if feedback_format == "all":
            call["summary"]["feedback"] = feedback_items
        elif feedback_format == "counts":
            count = 0
            notes: list[str] = []
            for feedback_item in feedback_items:
                if feedback_item["feedback_type"] == "wandb.reaction.1":
                    count += 1
                elif (
                    feedback_format == "emoji+note"
                    and feedback_item["feedback_type"] == "wandb.note.1"
                ):
                    notes += [feedback_item["payload"]["note"]]

            call["summary"]["feedback"] = {
                "emoji_count": count,
                "notes": " | ".join(notes),
            }
        else:
            raise ValueError(f"Unknown feedback_format '{feedback_format}'")

    return calls


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
