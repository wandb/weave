"""Server-side validation for saved Monitor object queries.

A Monitor carries a `query` over call fields that the scoring worker runs every
cycle. We reject queries referencing disallowed fields or that are structurally
invalid at obj_create time, so a bad monitor fails loudly on save instead of
silently erroring per scoring cycle.
"""

from pydantic import ValidationError

from weave.trace_server.calls_query_builder.calls_query_builder import (
    ALLOWED_CALL_FIELDS,
    CallsMergedDynamicField,
    process_query_to_conditions,
)
from weave.trace_server.errors import InvalidFieldError, InvalidRequest
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder


def validate_monitor_query_fields(
    base_object_class: str | None,
    leaf_object_class: str | None,
    val: object,
) -> None:
    """Reject a saved Monitor whose `query` is malformed or uses a disallowed field."""
    if not _is_monitor_object(base_object_class, leaf_object_class):
        return
    query = _monitor_query(val)
    if query is None:
        return
    validate_calls_query(query)


def validate_calls_query(query: tsi_query.Query) -> None:
    """Reject a calls query referencing a disallowed field or that is structurally invalid.

    Validates by compiling the query to SQL conditions: compilation is what
    surfaces both bad field refs (InvalidFieldError) and malformed structure.
    """
    try:
        process_query_to_conditions(query, ParamBuilder(), "calls_merged")
    except InvalidFieldError as e:
        raise InvalidFieldError(_invalid_field_message(str(e))) from e
    except (ValueError, TypeError) as e:
        raise InvalidRequest(f"Invalid query: {e}") from e


# Serialized `_class_name`/`_bases` values for Monitor objects. Kept as
# server-side strings on purpose: the trace server must not import weave/flow.
MONITOR_OBJECT_CLASSES = frozenset({"Monitor", "ClassifierMonitor"})


def _is_monitor_object(
    base_object_class: str | None, leaf_object_class: str | None
) -> bool:
    """Whether a written object is a Monitor, by its serialized class name."""
    return (
        base_object_class in MONITOR_OBJECT_CLASSES
        or leaf_object_class in MONITOR_OBJECT_CLASSES
    )


def _monitor_query(val: object) -> tsi_query.Query | None:
    """Extract a recognizable calls query from a serialized Monitor, else None.

    None when there is no query or the value is not a query we understand (e.g. a
    non-Monitor object sharing the class name); such writes are left untouched.
    """
    if not isinstance(val, dict):
        return None
    raw_query = val.get("query")
    if raw_query is None:
        return None
    cleaned = _strip_weave_object_keys(raw_query)
    try:
        return tsi_query.Query.model_validate(cleaned)
    except ValidationError:
        return None


_WEAVE_BOOKKEEPING_KEYS = frozenset({"_type", "_class_name", "_bases"})


def _strip_weave_object_keys(value: object) -> object:
    """Drop weave bookkeeping keys (`_type`, `_class_name`, `_bases`) from a serialized query."""
    if isinstance(value, dict):
        return {
            k: _strip_weave_object_keys(v)
            for k, v in value.items()
            if k not in _WEAVE_BOOKKEEPING_KEYS
        }
    if isinstance(value, list):
        return [_strip_weave_object_keys(v) for v in value]
    return value


# Field references get_field_by_name accepts beyond exact ALLOWED_CALL_FIELDS
# keys, used only to build the user-facing error message. The `*_dump` prefixes
# are derived so they can't drift; the special entries must be kept in sync by
# hand with the explicit branches in get_field_by_name
# (`annotation_queue_items.queue_id` is an exact ref, not a prefix).
_DUMP_SUFFIX = "_dump"
_SPECIAL_DYNAMIC_FIELD_PREFIXES = (
    "feedback.*",
    "annotation_queue_items.queue_id",
    "summary.weave.*",
)
ALLOWED_DYNAMIC_FIELD_PREFIXES = _SPECIAL_DYNAMIC_FIELD_PREFIXES + tuple(
    f"{name[: -len(_DUMP_SUFFIX)]}.*"
    for name, field in ALLOWED_CALL_FIELDS.items()
    if isinstance(field, CallsMergedDynamicField) and name.endswith(_DUMP_SUFFIX)
)


def _invalid_field_message(reason: str) -> str:
    """Append the allowed field list and dynamic prefixes to a field rejection."""
    allowed = ", ".join(
        sorted(k for k in ALLOWED_CALL_FIELDS if not k.endswith(_DUMP_SUFFIX))
    )
    prefixes = ", ".join(ALLOWED_DYNAMIC_FIELD_PREFIXES)
    return (
        f"{reason}. Allowed fields: {allowed}. "
        f"Allowed dynamic field prefixes: {prefixes}"
    )
