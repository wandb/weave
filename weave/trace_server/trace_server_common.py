import copy
import datetime
import json
from collections import OrderedDict, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from weave.shared import refs_internal as ri
from weave.trace_server import constants
from weave.trace_server import trace_server_interface as tsi

CallStatus = Literal["running", "completed", "failed"]

FEEDBACK_QUERY_FIELDS = [
    "id",
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
    "scorer_tags",
    "scorer_tag_reasons",
    "scorer_tag_confidences",
    "scorer_ratings",
    "scorer_rating_reasons",
    "scorer_rating_confidences",
]


def make_feedback_query_req(
    project_id: str,
    calls: list[dict[str, Any]],
) -> tsi.FeedbackQueryReq:
    # make list of weave refs to calls, to be used in feedback query
    call_refs = []
    for call in calls:
        ref = ri.InternalCallRef(project_id=call["project_id"], id=call["id"])
        call_refs.append(ref.uri)

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
        fields=FEEDBACK_QUERY_FIELDS,
        query=query,
    )
    return feedback_query_req


@dataclass(frozen=True)
class AgentFeedbackByTarget:
    """Feedback rows grouped by agent target kind + raw identifier.

    Keys are raw trace_id / conversation_id / span_id strings (not ref URIs)
    so callers can look up by whatever identifier they already have from the
    spans row.
    """

    by_trace_id: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    by_conversation_id: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    by_span_id: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def make_agent_feedback_query_req(
    project_id: str,
    refs: list[str],
) -> tsi.FeedbackQueryReq:
    """Build a FeedbackQueryReq that returns feedback for any of `refs`.

    The refs are unioned (OR'd) into a single `$in` over `weave_ref` so
    the chat-view handler can fetch feedback for a turn plus all of its
    steps (or a conversation plus all its turns) in one round-trip.
    """
    query = tsi.Query(
        **{
            "$expr": {
                "$in": [
                    {"$getField": "weave_ref"},
                    [{"$literal": ref} for ref in refs],
                ]
            }
        }
    )
    return tsi.FeedbackQueryReq(
        project_id=project_id,
        fields=FEEDBACK_QUERY_FIELDS,
        query=query,
    )


def group_agent_feedback_by_target(
    feedback: tsi.FeedbackQueryRes,
) -> AgentFeedbackByTarget:
    """Group feedback rows by agent target kind + raw identifier."""
    by_trace_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_conversation_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_span_id: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for raw in feedback.result:
        # `FeedbackQueryRes.result` is intentionally `dict[str, Any]` because
        # callers can request arbitrary fields; this helper always passes
        # FEEDBACK_QUERY_FIELDS, so the rows match FeedbackDict shape.
        ref = ri.parse_internal_uri(raw.get("weave_ref", ""))
        if isinstance(ref, ri.InternalAgentTurnRef):
            by_trace_id[ref.trace_id].append(raw)
        elif isinstance(ref, ri.InternalAgentConversationRef):
            by_conversation_id[ref.conversation_id].append(raw)
        elif isinstance(ref, ri.InternalAgentSpanRef):
            by_span_id[ref.span_id].append(raw)

    return AgentFeedbackByTarget(
        by_trace_id=by_trace_id,
        by_conversation_id=by_conversation_id,
        by_span_id=by_span_id,
    )


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
    started_at: datetime.datetime | None = None,
    ended_at: datetime.datetime | None = None,
    exception: str | None = None,
    display_name: str | None = None,
) -> tsi.SummaryMap:
    """Make derived summary fields for a call.

    Summary is controlled by the user, but the `weave` summary key is
    used to store derived fields, adhering to the tsi.SummaryMap type.
    """
    weave_summary = summary.pop("weave", {})
    # Server-derived fields are recomputed below — discard any stored values
    # so historically-malformed rows (e.g. a list-shaped `trace_name` written
    # by an earlier rescore-worker bug that copied `summary["weave"]` from a
    # source call into a synthetic child, where `sum_dict_leaves` then bubbled
    # the string up into the parent as a list) don't escape CallSchema
    # validation. These keys are owned by this function alone.
    for derived_key in ("status", "trace_name", "latency_ms", "display_name"):
        weave_summary.pop(derived_key, None)

    status = tsi.TraceStatus.SUCCESS
    if exception:
        status = tsi.TraceStatus.ERROR
    elif ended_at is None:
        status = tsi.TraceStatus.RUNNING
    elif summary.get("status_counts", {}).get(tsi.TraceStatus.ERROR, 0) > 0:
        status = tsi.TraceStatus.DESCENDANT_ERROR
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
    elif ri.string_will_be_interpreted_as_ref(op_name):
        op = ri.parse_internal_uri(op_name)
        if isinstance(op, ri.InternalObjectRef):
            weave_summary["trace_name"] = op.name
    else:
        weave_summary["trace_name"] = op_name

    summary["weave"] = weave_summary
    return cast(tsi.SummaryMap, summary)


def empty_str_to_none(val: str | None) -> str | None:
    return val if val != "" else None


def get_nested_key(d: dict[str, Any], col: str) -> Any | None:
    """Get a nested key from a dict. None if not found.

    Example:
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b.c") -> "d"
    get_nested_key({"a": {"b": {"c": "d"}}}, "a.b") -> {"c": "d"}
    get_nested_key({"a": {"b": {"c": "d"}}}, "foobar") -> None
    """

    def _get(data: Any | None, key: str) -> Any | None:
        if not data or not isinstance(data, dict):
            return None
        return data.get(key)

    keys = col.split(".")
    curr: Any | None = d
    for key in keys[:-1]:
        curr = _get(curr, key)
    return _get(curr, keys[-1])


def set_nested_key(d: dict[str, Any], col: str, val: Any) -> None:
    """Set a nested key in a dict.

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
    """Check if a digest is a version like string.

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


def digest_is_content_hash(digest: str) -> bool:
    """Check if a digest looks like a content-addressed hash.

    Recognizes two formats:
    - Weave digest: 43-char modified base64url (A-Za-z0-9XY), from bytes_digest()
    - Hex SHA-256: 64 hex characters

    Examples:
    >>> digest_is_content_hash("oioZ7zgsCq4K7tfFQZRubx3ZGPXmFyaeoeWHHd8KUl8")
    True
    >>> digest_is_content_hash("a" * 64)
    True
    >>> digest_is_content_hash("production")
    False
    """
    # Weave digest: 43-char modified base64url
    if len(digest) == WEAVE_DIGEST_LENGTH and digest.isalnum():
        return True
    # Hex SHA-256: 64 hex chars
    if len(digest) == HEX_SHA256_DIGEST_LENGTH:
        try:
            int(digest, 16)
        except ValueError:
            return False
        return True
    return False


# Length of a Weave digest (modified base64url encoding of SHA-256)
WEAVE_DIGEST_LENGTH = 43
# Length of a hex-encoded SHA-256 digest
HEX_SHA256_DIGEST_LENGTH = 64

MAX_FILTER_LENGTH = 1000


def assert_parameter_length_less_than_max(
    param_name: str, arr_len: int, max_length: int = MAX_FILTER_LENGTH
) -> None:
    if arr_len > max_length:
        raise ValueError(
            f"Parameter: '{param_name}' request length is greater than max length ({max_length}). Actual length: {arr_len}"
        )


def determine_call_status(call: tsi.CallSchema) -> CallStatus:
    """Determine the status of a call based on its state.

    Args:
        call: The call schema to determine status for.

    Returns:
        The status of the call: "running", "completed", or "failed".
    """
    if call.ended_at is None:
        return "running"
    if call.exception is None:
        return "completed"
    return "failed"


def _str_or_none(v: Any) -> str | None:
    return v if isinstance(v, str) and v else None


def eval_run_refs_from_call(
    call: tsi.CallSchema, attributes: dict[str, Any]
) -> tuple[str, str]:
    """Return (evaluation_ref, model_ref) for an evaluation-run call.

    Both refs are stored in two places: under
    ``attributes.weave.{evaluation,model}`` (set by ``evaluation_run_create``,
    used as a denormalization for filterable list queries) and on
    ``call.inputs`` as ``self``/``model`` (the canonical inputs of every
    ``Evaluation.evaluate`` call). Standard evaluations and imperative
    evaluations (``weave.EvaluationLogger``) bypass ``evaluation_run_create``
    and only populate ``call.inputs``, so we must fall back to inputs to
    return a non-empty pair for those cases. Mirrors the pattern in
    ``eval_results_helpers.py``: ``inputs.get("self") or inputs.get("this")``.
    """
    inputs = call.inputs if isinstance(call.inputs, dict) else {}

    evaluation_ref = (
        _str_or_none(attributes.get(constants.EVALUATION_RUN_EVALUATION_ATTR_KEY))
        or _str_or_none(inputs.get("self"))
        or _str_or_none(inputs.get("this"))
        or ""
    )
    model_ref = (
        _str_or_none(attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY))
        or _str_or_none(inputs.get("model"))
        or ""
    )
    return evaluation_ref, model_ref


def op_name_matches(op_name: str | None, expected_name: str) -> bool:
    """Check if an op_name URI matches the expected op name.

    Args:
        op_name: The op_name from a call, which may be a URI or a plain name
        expected_name: The expected op name to match against

    Returns:
        True if the op_name matches the expected name
    """
    if not op_name:
        return False

    # If it's a URI, parse it to get the name
    if op_name.startswith(ri.WEAVE_INTERNAL_SCHEME):
        try:
            parsed = ri.parse_internal_uri(op_name)
            if isinstance(parsed, ri.InternalOpRef):
                return parsed.name == expected_name
        except ri.InvalidInternalRef:
            pass

    # Fallback to direct string comparison for non-URI op names
    return op_name == expected_name


def scorer_read_res_from_obj(obj: tsi.ObjSchema) -> tsi.ScorerReadRes:
    """Build a ScorerReadRes from an ObjSchema, with safe fallbacks."""
    name = obj.object_id
    description = None
    score_op = ""

    if hasattr(obj, "val") and obj.val and isinstance(obj.val, dict):
        name = obj.val.get("name", obj.object_id)
        description = obj.val.get("description")
        score_op = obj.val.get("score", "")

    return tsi.ScorerReadRes(
        object_id=obj.object_id,
        digest=obj.digest,
        version_index=obj.version_index,
        created_at=obj.created_at,
        name=name,
        description=description,
        score_op=score_op,
    )


def get_prediction_inputs(call_inputs: dict[str, Any] | None) -> dict[str, Any]:
    """Extract prediction inputs from a call's inputs dict, defaulting to {} if missing or None."""
    return (call_inputs or {}).get("inputs") or {}


def try_parse_json(val: Any, default: Any = None) -> Any:
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def apply_tags_and_synth_latest_in_place(
    objs: list[tsi.ObjSchema],
    tags_map: dict[tuple[str, str], list[str]],
    aliases_map: dict[tuple[str, str], list[str]],
) -> None:
    """Apply tags + aliases onto each obj, synthesizing 'latest' when needed.

    Synthesis covers the computed-fallback branch of the hybrid `is_latest`
    projection: when obj_delete tombstones the explicit 'latest' alias row,
    is_latest = 1 is then supplied by the window-function rank over the
    surviving versions. Surface that virtual 'latest' on read so callers
    see a view consistent with obj.is_latest.

    Read-skew guard: the projection query and the aliases-map query are two
    separate reads of the `aliases` table. If a concurrent write moves
    'latest' to a different digest between them, we can see is_latest=1 on
    the old digest while the aliases map already credits 'latest' to the
    new digest. Skip synthesizing 'latest' on any digest whose object_id
    already has an explicit 'latest' alias in the just-fetched map.

    Operates on the tags_map / aliases_map keyed by (object_id, digest)
    returned by the ClickHouse trace server.
    """
    object_ids_with_alias_latest = {
        oid for (oid, _), aliases in aliases_map.items() if "latest" in aliases
    }
    for obj in objs:
        key = (obj.object_id, obj.digest)
        obj.tags = sorted(tags_map.get(key, []))
        aliases = aliases_map.get(key, [])
        if (
            obj.is_latest == 1
            and "latest" not in aliases
            and obj.object_id not in object_ids_with_alias_latest
        ):
            aliases = ["latest", *aliases]
        obj.aliases = aliases
