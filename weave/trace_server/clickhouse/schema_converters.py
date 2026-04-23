"""Schema converters between API types and ClickHouse insertable formats.

Handles conversion of calls, objects, and tables between the trace server
interface (API) representations and their ClickHouse storage formats.
"""

import json
from collections.abc import Sequence
from typing import Any, cast

from weave.shared.trace_server_interface_util import extract_refs_from_values
from weave.trace_server import ch_sentinel_values
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.utilities import (
    any_value_to_dump,
    dict_dump_to_dict,
    dict_value_to_dump,
    ensure_datetimes_have_tz,
    nullable_any_dump_to_any,
)
from weave.trace_server.clickhouse_schema import (
    ALL_CALL_COMPLETE_INSERT_COLUMNS,
    ALL_CALL_INSERT_COLUMNS,
    CallCHInsertable,
    CallCompleteCHInsertable,
    CallEndCHInsertable,
    CallStartCHInsertable,
    SelectableCHObjSchema,
)
from weave.trace_server.ids import generate_id
from weave.trace_server.trace_server_common import make_derived_summary_fields
from weave.trace_server.ttl_settings import compute_expire_at

# ---------------------------------------------------------------------------
# Call schema converters
# ---------------------------------------------------------------------------


def ch_call_dict_to_call_schema_dict(ch_call_dict: dict) -> dict:
    summary = nullable_any_dump_to_any(ch_call_dict.get("summary_dump"))
    started_at = ensure_datetimes_have_tz(ch_call_dict.get("started_at"))

    # Convert sentinel values back to None for all sentinel-tracked fields.
    # This handles both the calls_merged Nullable path (returns None) and the
    # calls_complete non-nullable path (returns sentinel -> converted to None).
    sv: dict[str, Any] = {}
    for field in ch_sentinel_values.ALL_SENTINEL_FIELDS:
        raw = ch_call_dict.get(field)
        val = ch_sentinel_values.from_ch_value(field, raw)
        if field in ch_sentinel_values.SENTINEL_DATETIME_FIELDS:
            val = ensure_datetimes_have_tz(val)
        sv[field] = val

    ended_at = sv["ended_at"]
    display_name = sv["display_name"]
    exception = sv["exception"]
    otel_dump = sv["otel_dump"]

    # Load attributes from attributes_dump
    attributes = dict_dump_to_dict(ch_call_dict.get("attributes_dump", "{}"))

    # For backwards/future compatibility: inject otel_dump into attributes if present
    # Legacy trace servers stored all otel info in attributes, clients expect it
    # TODO(gst): consider returning the raw otel column and reconstructing client side
    if otel_dump:
        attributes["otel_span"] = dict_dump_to_dict(otel_dump)

    return {
        "project_id": ch_call_dict.get("project_id"),
        "id": ch_call_dict.get("id"),
        "trace_id": ch_call_dict.get("trace_id"),
        "parent_id": sv["parent_id"],
        "thread_id": sv["thread_id"],
        "turn_id": sv["turn_id"],
        "op_name": ch_call_dict.get("op_name"),
        "started_at": started_at,
        "ended_at": ended_at,
        "attributes": attributes,
        "inputs": dict_dump_to_dict(ch_call_dict.get("inputs_dump", "{}")),
        "output": nullable_any_dump_to_any(ch_call_dict.get("output_dump")),
        "summary": make_derived_summary_fields(
            summary=summary or {},
            op_name=ch_call_dict.get("op_name", ""),
            started_at=started_at,
            ended_at=ended_at,
            exception=exception,
            display_name=display_name,
        ),
        "exception": exception,
        "wb_run_id": sv["wb_run_id"],
        "wb_run_step": ch_call_dict.get("wb_run_step"),
        "wb_run_step_end": ch_call_dict.get("wb_run_step_end"),
        "wb_user_id": sv["wb_user_id"],
        "display_name": display_name,
        "storage_size_bytes": ch_call_dict.get("storage_size_bytes"),
        "total_storage_size_bytes": ch_call_dict.get("total_storage_size_bytes"),
    }


def ch_call_to_row(ch_call: CallCHInsertable) -> list[Any]:
    """Convert a CH insertable call to a row for batch insertion with the correct defaults."""
    call_dict = ch_call.model_dump()
    return [call_dict.get(col) for col in ALL_CALL_INSERT_COLUMNS]


def start_call_for_insert_to_ch_insertable(
    start_call: tsi.StartedCallSchemaForInsert,
    retention_days: int,
) -> CallStartCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    call_id = start_call.id or generate_id()
    trace_id = start_call.trace_id or generate_id()
    # Process inputs for base64 content if trace_server is provided
    inputs = start_call.inputs
    input_refs = extract_refs_from_values(inputs)

    otel_dump_str = None
    if start_call.otel_dump is not None:
        otel_dump_str = dict_value_to_dump(start_call.otel_dump)

    return CallStartCHInsertable(
        project_id=start_call.project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=start_call.parent_id,
        thread_id=start_call.thread_id,
        turn_id=start_call.turn_id,
        op_name=start_call.op_name,
        started_at=start_call.started_at,
        attributes_dump=dict_value_to_dump(start_call.attributes),
        inputs_dump=dict_value_to_dump(inputs),
        input_refs=input_refs,
        otel_dump=otel_dump_str,
        wb_run_id=start_call.wb_run_id,
        wb_run_step=start_call.wb_run_step,
        wb_user_id=start_call.wb_user_id,
        display_name=start_call.display_name,
        expire_at=compute_expire_at(retention_days, start_call.started_at),
    )


def start_call_insertable_to_complete_start(
    ch_start: CallStartCHInsertable,
) -> CallCompleteCHInsertable:
    """Convert a start-only call into a calls_complete insertable row.

    Args:
        ch_start: The start-only ClickHouse insertable call.

    Returns:
        CallCompleteCHInsertable: A calls_complete insertable row with an empty end.
    """
    return CallCompleteCHInsertable(
        project_id=ch_start.project_id,
        id=ch_start.id,
        trace_id=ch_start.trace_id,
        parent_id=ch_start.parent_id,
        thread_id=ch_start.thread_id,
        turn_id=ch_start.turn_id,
        op_name=ch_start.op_name,
        display_name=ch_start.display_name,
        started_at=ch_start.started_at,
        ended_at=None,
        exception=None,
        attributes_dump=ch_start.attributes_dump,
        inputs_dump=ch_start.inputs_dump,
        input_refs=ch_start.input_refs,
        output_dump=any_value_to_dump(None),
        summary_dump=dict_value_to_dump({}),
        otel_dump=ch_start.otel_dump,
        output_refs=ch_start.output_refs,
        wb_user_id=ch_start.wb_user_id,
        wb_run_id=ch_start.wb_run_id,
        wb_run_step=ch_start.wb_run_step,
        wb_run_step_end=None,
        expire_at=ch_start.expire_at,
    )


def end_call_for_insert_to_ch_insertable(
    end_call: tsi.EndedCallSchemaForInsert,
    retention_days: int,
) -> CallEndCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    output = end_call.output
    output_refs = extract_refs_from_values(output)

    return CallEndCHInsertable(
        project_id=end_call.project_id,
        id=end_call.id,
        exception=end_call.exception,
        ended_at=end_call.ended_at,
        summary_dump=dict_value_to_dump(dict(end_call.summary)),
        output_dump=any_value_to_dump(output),
        output_refs=output_refs,
        wb_run_step_end=end_call.wb_run_step_end,
        expire_at=compute_expire_at(retention_days, end_call.ended_at),
    )


def start_end_calls_to_ch_complete_insertable(
    start_call: tsi.StartedCallSchemaForInsert,
    end_call: tsi.EndedCallSchemaForInsert,
    retention_days: int,
) -> CallCompleteCHInsertable:
    """Combine start and end call data into a CallCompleteCHInsertable.

    Used by OTel export when writing to the calls_complete table.

    Args:
        start_call: The start call data.
        end_call: The end call data.
        retention_days: The project's retention policy in days (0 = no TTL).

    Returns:
        CallCompleteCHInsertable: A complete call ready for insertion.
    """
    call_id = start_call.id or generate_id()
    trace_id = start_call.trace_id or generate_id()

    inputs = start_call.inputs
    input_refs = extract_refs_from_values(inputs)

    output = end_call.output
    output_refs = extract_refs_from_values(output)

    otel_dump_str = None
    if start_call.otel_dump is not None:
        otel_dump_str = dict_value_to_dump(start_call.otel_dump)

    return CallCompleteCHInsertable(
        project_id=start_call.project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=start_call.parent_id,
        thread_id=start_call.thread_id,
        turn_id=start_call.turn_id,
        op_name=start_call.op_name,
        display_name=start_call.display_name,
        started_at=start_call.started_at,
        ended_at=end_call.ended_at,
        exception=end_call.exception,
        attributes_dump=dict_value_to_dump(start_call.attributes),
        inputs_dump=dict_value_to_dump(inputs),
        input_refs=input_refs,
        output_dump=any_value_to_dump(output),
        summary_dump=dict_value_to_dump(dict(end_call.summary)),
        otel_dump=otel_dump_str,
        output_refs=output_refs,
        wb_user_id=start_call.wb_user_id,
        wb_run_id=start_call.wb_run_id,
        wb_run_step=start_call.wb_run_step,
        wb_run_step_end=end_call.wb_run_step_end,
        expire_at=compute_expire_at(retention_days, start_call.started_at),
    )


def ch_complete_call_to_row(ch_call: CallCompleteCHInsertable) -> list[Any]:
    """Convert a CallCompleteCHInsertable to a row for batch insertion."""
    call_dict = ch_call.model_dump()
    return [
        ch_sentinel_values.to_ch_value(col, call_dict.get(col))
        for col in ALL_CALL_COMPLETE_INSERT_COLUMNS
    ]


def complete_call_to_ch_insertable(
    complete_call: tsi.CompletedCallSchemaForInsert,
    retention_days: int,
) -> CallCompleteCHInsertable:
    """Convert a completed call schema to a ClickHouse insertable format.

    Args:
        complete_call: The completed call schema from the API.
        retention_days: The project's retention policy in days (0 = no TTL).

    Returns:
        CallCompleteCHInsertable: The ClickHouse insertable representation.
    """
    inputs = complete_call.inputs
    input_refs = extract_refs_from_values(inputs)

    output = complete_call.output
    output_refs = extract_refs_from_values(output)

    otel_dump_str = None
    if complete_call.otel_dump is not None:
        otel_dump_str = dict_value_to_dump(complete_call.otel_dump)

    return CallCompleteCHInsertable(
        project_id=complete_call.project_id,
        id=complete_call.id,
        trace_id=complete_call.trace_id,
        parent_id=complete_call.parent_id,
        thread_id=complete_call.thread_id,
        turn_id=complete_call.turn_id,
        op_name=complete_call.op_name,
        display_name=complete_call.display_name,
        started_at=complete_call.started_at,
        ended_at=complete_call.ended_at,
        exception=complete_call.exception,
        attributes_dump=dict_value_to_dump(complete_call.attributes),
        inputs_dump=dict_value_to_dump(inputs),
        input_refs=input_refs,
        output_dump=any_value_to_dump(output),
        summary_dump=dict_value_to_dump(dict(complete_call.summary)),
        otel_dump=otel_dump_str,
        output_refs=output_refs,
        wb_user_id=complete_call.wb_user_id,
        wb_run_id=complete_call.wb_run_id,
        wb_run_step=complete_call.wb_run_step,
        wb_run_step_end=complete_call.wb_run_step_end,
        expire_at=compute_expire_at(retention_days, complete_call.started_at),
    )


# ---------------------------------------------------------------------------
# Object schema converters
# ---------------------------------------------------------------------------


def ch_obj_to_obj_schema(ch_obj: SelectableCHObjSchema) -> tsi.ObjSchema:
    return tsi.ObjSchema(
        project_id=ch_obj.project_id,
        object_id=ch_obj.object_id,
        created_at=ensure_datetimes_have_tz(ch_obj.created_at),
        wb_user_id=ch_obj.wb_user_id,
        version_index=ch_obj.version_index,
        is_latest=ch_obj.is_latest,
        digest=ch_obj.digest,
        kind=ch_obj.kind,
        base_object_class=ch_obj.base_object_class,
        leaf_object_class=ch_obj.leaf_object_class,
        val=json.loads(ch_obj.val_dump),
        size_bytes=ch_obj.size_bytes,
    )


def get_type(val: Any) -> str:
    if val is None:
        return "none"
    elif isinstance(val, dict):
        if "_type" in val:
            if "weave_type" in val:
                return val["weave_type"]["type"]
            return val["_type"]
        return "dict"
    elif isinstance(val, list):
        return "list"
    return "unknown"


def get_kind(val: Any) -> str:
    val_type = get_type(val)
    if val_type == "Op":
        return "op"
    return "object"


# ---------------------------------------------------------------------------
# Table schema converters
# ---------------------------------------------------------------------------


def ch_table_stats_to_table_stats_schema(
    ch_table_stats_row: Sequence[Any],
) -> tsi.TableStatsRow:
    # Unpack the row with a default for the third value if it doesn't exist
    row_tuple = tuple(ch_table_stats_row)
    digest, count = row_tuple[:2]
    storage_size_bytes = row_tuple[2] if len(row_tuple) > 2 else cast(Any, None)

    return tsi.TableStatsRow(
        count=count,
        digest=digest,
        storage_size_bytes=storage_size_bytes,
    )
