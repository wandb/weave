"""Field definitions and registry for the calls query builder.

This module defines the field class hierarchy that maps call fields to SQL
expressions, including aggregation, JSON path extraction, feedback payloads,
annotation queue items, and computed summary fields. It also provides the
field registry (ALLOWED_CALL_FIELDS) and lookup function (get_field_by_name).
"""

import logging
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from weave.trace_server import ch_sentinel_values
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.utils import (
    json_dump_field_as_sql,
    param_slot,
    safe_alias,
)
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    split_escaped_field_path,
)
from weave.trace_server.project_version.types import ReadTable, TableConfig

logger = logging.getLogger(__name__)


def maybe_agg(expr: str, use_agg_fn: bool) -> str:
    """Wrap expression in any() aggregate function if needed."""
    return f"any({expr})" if use_agg_fn else expr


# ---------------------------------------------------------------------------
# Field class hierarchy
# ---------------------------------------------------------------------------


class QueryBuilderField(BaseModel):
    field: str

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
    ) -> str:
        return clickhouse_cast(f"{table_alias}.{self.field}", cast)

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True, **kwargs: Any
    ) -> str:
        return f"{self.as_sql(pb, table_alias)} AS {safe_alias(self.field)}"


class CallsMergedField(QueryBuilderField):
    def is_feedback_field(self) -> bool:
        return False

    def is_heavy(self) -> bool:
        return False

    def _resolve_field_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        """Return the SQL expression for this field (use_agg_fn ignored in base class)."""
        return self.as_sql(pb, table_alias)

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True, **kwargs: Any
    ) -> str:
        return f"{self._resolve_field_sql(pb, table_alias, use_agg_fn)} AS {safe_alias(self.field)}"

    def null_check_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        read_table: "ReadTable",
        *,
        use_agg_fn: bool = True,
        negate: bool = False,
    ) -> str:
        """Generate IS [NOT] NULL or sentinel equality check for this field."""
        field_sql = self._resolve_field_sql(pb, table_alias, use_agg_fn)
        return ch_sentinel_values.null_check_sql(
            self.field, field_sql, read_table, pb, negate=negate
        )


class CallsMergedAggField(CallsMergedField):
    agg_fn: str

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        inner = super().as_sql(pb, table_alias)
        if not use_agg_fn:
            return clickhouse_cast(inner, cast)
        return clickhouse_cast(f"{self.agg_fn}({inner})", cast)

    def _resolve_field_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        """Return the SQL expression for this field, honoring use_agg_fn."""
        return self.as_sql(pb, table_alias, use_agg_fn=use_agg_fn)


class AggFieldWithTableOverrides(CallsMergedAggField):
    # This is useful if you know the field must come from a predetemined table alias.

    table_name: str

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        return super().as_sql(pb, self.table_name, cast, use_agg_fn)


class CallsMergedDynamicField(CallsMergedAggField):
    extra_path: list[str] | None = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        res = super().as_sql(pb, table_alias, use_agg_fn=use_agg_fn)
        return json_dump_field_as_sql(pb, table_alias, res, self.extra_path, cast)

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True, **kwargs: Any
    ) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        # Use the parent (CallsMergedAggField) as_sql to get the aggregate
        # expression without the JSON extraction that our own as_sql adds.
        return f"{super().as_sql(pb, table_alias, use_agg_fn=use_agg_fn)} AS {safe_alias(self.field)}"

    def with_path(self, path: list[str]) -> "CallsMergedDynamicField":
        extra_path = [*(self.extra_path or [])]
        extra_path.extend(path)
        return CallsMergedDynamicField(
            field=self.field, agg_fn=self.agg_fn, extra_path=extra_path
        )

    def is_heavy(self) -> bool:
        return True


class CallsMergedSummaryField(CallsMergedField):
    """Field class for computed summary values."""

    field: str
    summary_field: str

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
        read_table: "ReadTable" = ReadTable.CALLS_MERGED,
    ) -> str:
        # Look up handler for the requested summary field
        handler = get_summary_field_handler(self.summary_field)
        if handler:
            sql = handler(pb, table_alias, use_agg_fn, read_table)
            return clickhouse_cast(sql, cast)
        else:
            supported_fields = ", ".join(SUMMARY_FIELD_HANDLERS.keys())
            raise NotImplementedError(
                f"Summary field '{self.summary_field}' not implemented. "
                f"Supported fields are: {supported_fields}"
            )

    def as_select_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        use_agg_fn: bool = True,
        *,
        read_table: "ReadTable" = ReadTable.CALLS_MERGED,
        **kwargs: Any,
    ) -> str:
        return f"{self.as_sql(pb, table_alias, use_agg_fn=use_agg_fn, read_table=read_table)} AS {safe_alias(self.field)}"

    def is_heavy(self) -> bool:
        # These are computed from non-heavy fields (status uses exception and ended_at)
        # If we add more summary fields that depend on heavy fields,
        # this would need to be made more sophisticated
        return False


class CallsMergedFeedbackPayloadField(CallsMergedField):
    feedback_type: str
    extra_path: list[str]

    def is_feedback_field(self) -> bool:
        return True

    @classmethod
    def from_path(cls, path: str) -> Self:
        """Expected format: `[feedback.type].dot.path`.

        feedback.type can be '*' to select all feedback types.
        """
        regex = re.compile(r"^(\[.+\])\.(.+)$")
        match = regex.match(path)
        if not match:
            raise InvalidFieldError(f"Invalid feedback path: {path}")
        feedback_type, path = match.groups()
        if feedback_type[0] != "[" or feedback_type[-1] != "]":
            raise InvalidFieldError(f"Invalid feedback type: {feedback_type}")
        extra_path = split_escaped_field_path(path)
        feedback_type = feedback_type[1:-1]
        if extra_path[0] == "payload":
            return cls(
                field="payload_dump",
                feedback_type=feedback_type,
                extra_path=extra_path[1:],
            )
        elif extra_path[0] == "runnable_ref":
            return cls(field="runnable_ref", feedback_type=feedback_type, extra_path=[])
        elif extra_path[0] == "trigger_ref":
            return cls(field="trigger_ref", feedback_type=feedback_type, extra_path=[])
        raise InvalidFieldError(f"Invalid feedback path: {path}")

    def is_heavy(self) -> bool:
        return True

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        """Generate SQL for accessing feedback payload fields.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias (unused, always uses 'feedback')
            cast: Optional cast type for the result
            use_agg_fn: Whether to use aggregate functions (anyIf/any).
                When True (calls_merged): uses anyIf() to pick one feedback entry per call
                When False (calls_complete): uses CASE WHEN to conditionally access feedback

        Returns:
            SQL expression for the feedback field
        """
        inner = super().as_sql(pb, "feedback")
        if self.feedback_type == "*":
            res = inner
            if use_agg_fn:
                # Pick any non-empty value from across all feedback rows.
                if self.extra_path:
                    extracted = json_dump_field_as_sql(
                        pb, "feedback", inner, self.extra_path, cast
                    )
                    return f"anyIf({extracted}, {extracted} != '')"
                return f"any({inner})"
        else:
            param_name = pb.add_param(self.feedback_type)
            if use_agg_fn:
                # Use anyIf to aggregate and filter by feedback_type
                res = f"anyIf({inner}, feedback.feedback_type = {param_slot(param_name, 'String')})"
            else:
                # Use CASE WHEN to conditionally access the field without aggregation
                res = f"CASE WHEN feedback.feedback_type = {param_slot(param_name, 'String')} THEN {inner} END"
        # If there is no extra path, then we can just return the inner sql (JSON_VALUE does not like empty extra_path)
        if not self.extra_path:
            return res
        return json_dump_field_as_sql(pb, "feedback", res, self.extra_path, cast)

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True, **kwargs: Any
    ) -> str:
        raise NotImplementedError(
            "Feedback fields cannot be selected directly, yet - implement me!"
        )


class CallsMergedQueueItemField(CallsMergedField):
    """Field class for annotation queue item fields.

    This field type handles queries against the annotation_queue_items table,
    which tracks which calls belong to which annotation queues.
    """

    def is_heavy(self) -> bool:
        return True

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        """Generate SQL for accessing queue item fields.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias (unused, always uses 'annotation_queue_items')
            cast: Optional cast type for the result
            use_agg_fn: Whether to use aggregate functions.
                When True (calls_merged): uses any() to aggregate queue items per call
                When False (calls_complete): directly references the field without aggregation

        Returns:
            SQL expression for the queue item field
        """
        inner = f"annotation_queue_items.{self.field}"
        res = inner if not use_agg_fn else f"any({inner})"
        return clickhouse_cast(res, cast)

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True, **kwargs: Any
    ) -> str:
        raise NotImplementedError(
            "Queue item fields cannot be selected directly, yet - implement me!"
        )


class AggregatedDataSizeField(CallsMergedField):
    join_table_name: str

    def is_heavy(self) -> bool:
        return True

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
    ) -> str:
        # This field is not supposed to be called yet. For now, we just take the parent class's
        # implementation. Consider re-implementation for future use.
        return super().as_sql(pb, table_alias, cast)

    def as_select_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        use_agg_fn: bool = True,
        *,
        read_table: "ReadTable" = ReadTable.CALLS_MERGED,
        **kwargs: Any,
    ) -> str:
        # It doesn't make sense for a non-root call to have a total storage size,
        # even if a value could be computed.
        parent_id_field = get_field_by_name("parent_id")
        parent_null = parent_id_field.null_check_sql(
            pb, table_alias, read_table, use_agg_fn=use_agg_fn
        )
        storage_expr = maybe_agg(
            f"{self.join_table_name}.total_storage_size_bytes", use_agg_fn
        )
        conditional_field = f"""
            CASE
                WHEN {parent_null}
                THEN {storage_expr}
                ELSE NULL
            END
            """
        return f"{conditional_field} AS {safe_alias(self.field)}"


class QueryBuilderDynamicField(QueryBuilderField):
    # This is a temporary solution to address a specific use case.
    # We need to reuse the `CallsMergedDynamicField` mechanics in the table_query,
    # but the table_query is not an aggregating table. Therefore, we
    # can't use `CallsMergedDynamicField` directly because it
    # inherits from `CallsMergedAggField`.
    #
    # To solve this, we've created `QueryBuilderDynamicField`, which is similar to
    # `CallsMergedDynamicField` but doesn't inherit from `CallsMergedAggField`.
    # Both classes use `json_dump_field_as_sql` for the main functionality.
    #
    # While this approach isn't as DRY as we'd like, it allows us to implement
    # the needed functionality with minimal refactoring. In the future, we should
    # consider a more elegant solution that reduces code duplication.

    extra_path: list[str] | None = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
    ) -> str:
        res = super().as_sql(pb, table_alias)
        return json_dump_field_as_sql(pb, table_alias, res, self.extra_path, cast)

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True, **kwargs: Any
    ) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        return super().as_select_sql(pb, table_alias, use_agg_fn=use_agg_fn)


# ---------------------------------------------------------------------------
# Table name helpers & constants
# ---------------------------------------------------------------------------

STORAGE_SIZE_TABLE_NAME = "storage_size_tbl"
ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME = "rolled_up_cms"


def get_calls_table_name(read_table: ReadTable) -> str:
    """Return the base calls table name for a read table."""
    return TableConfig.from_read_table(read_table).table_name


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

ALLOWED_CALL_FIELDS = {
    "project_id": CallsMergedField(field="project_id"),
    "id": CallsMergedField(field="id"),
    "trace_id": CallsMergedAggField(field="trace_id", agg_fn="any"),
    "parent_id": CallsMergedAggField(field="parent_id", agg_fn="any"),
    "thread_id": CallsMergedAggField(field="thread_id", agg_fn="any"),
    "turn_id": CallsMergedAggField(field="turn_id", agg_fn="any"),
    "op_name": CallsMergedAggField(field="op_name", agg_fn="any"),
    "started_at": CallsMergedAggField(field="started_at", agg_fn="any"),
    "attributes_dump": CallsMergedDynamicField(field="attributes_dump", agg_fn="any"),
    "inputs_dump": CallsMergedDynamicField(field="inputs_dump", agg_fn="any"),
    "input_refs": CallsMergedAggField(field="input_refs", agg_fn="array_concat_agg"),
    "ended_at": CallsMergedAggField(field="ended_at", agg_fn="any"),
    "output_dump": CallsMergedDynamicField(field="output_dump", agg_fn="any"),
    "output_refs": CallsMergedAggField(field="output_refs", agg_fn="array_concat_agg"),
    "summary_dump": CallsMergedDynamicField(field="summary_dump", agg_fn="any"),
    "exception": CallsMergedAggField(field="exception", agg_fn="any"),
    "wb_user_id": CallsMergedAggField(field="wb_user_id", agg_fn="any"),
    "wb_run_id": CallsMergedAggField(field="wb_run_id", agg_fn="any"),
    "wb_run_step": CallsMergedAggField(field="wb_run_step", agg_fn="any"),
    "wb_run_step_end": CallsMergedAggField(field="wb_run_step_end", agg_fn="any"),
    "deleted_at": CallsMergedAggField(field="deleted_at", agg_fn="any"),
    "display_name": CallsMergedAggField(field="display_name", agg_fn="argMaxMerge"),
    "storage_size_bytes": AggFieldWithTableOverrides(
        field="storage_size_bytes",
        agg_fn="any",
        table_name=STORAGE_SIZE_TABLE_NAME,
    ),
    "total_storage_size_bytes": AggregatedDataSizeField(
        field="total_storage_size_bytes",
        join_table_name=ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME,
    ),
    "otel_dump": CallsMergedAggField(field="otel_dump", agg_fn="any"),
}

DISALLOWED_FILTERING_FIELDS = {"storage_size_bytes", "total_storage_size_bytes"}

# Fields that are stored as DateTime64 columns in ClickHouse. When comparing
# these fields with numeric unix timestamps, the value must be converted to a
# datetime string so ClickHouse can properly use primary key / ORDER BY indexes.
DATETIME_COLUMN_FIELDS = {"started_at", "ended_at", "deleted_at"}


def get_field_by_name(name: str) -> CallsMergedField:
    if name not in ALLOWED_CALL_FIELDS:
        if name.startswith("feedback."):
            return CallsMergedFeedbackPayloadField.from_path(name[len("feedback.") :])
        elif name.startswith("annotation_queue_items."):
            # Handle annotation_queue_items.* fields
            field_name = name[len("annotation_queue_items.") :]
            # Only allow queue_id for now
            if field_name == "queue_id":
                return CallsMergedQueueItemField(field="queue_id")
            raise InvalidFieldError(
                f"Invalid annotation_queue_items field: {field_name}"
            )
        elif name.startswith("summary.weave."):
            # Handle summary.weave.* fields
            summary_field = name[len("summary.weave.") :]
            return CallsMergedSummaryField(field=name, summary_field=summary_field)
        else:
            field_parts = split_escaped_field_path(name)
            start_part = field_parts[0]
            dumped_start_part = start_part + "_dump"
            if dumped_start_part in ALLOWED_CALL_FIELDS:
                field = ALLOWED_CALL_FIELDS[dumped_start_part]
                if isinstance(field, CallsMergedDynamicField) and len(field_parts) > 1:
                    return field.with_path(field_parts[1:])
                return field
            raise InvalidFieldError(f"Field {name} is not allowed")
    return ALLOWED_CALL_FIELDS[name]


def _field_as_sql_maybe_agg(
    field: CallsMergedField,
    pb: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
    cast: tsi_query.CastTo | None = None,
) -> str:
    """Convert a field to SQL, passing use_agg_fn if the field supports it."""
    if isinstance(field, CallsMergedAggField):
        return field.as_sql(pb, table_alias, cast=cast, use_agg_fn=use_agg_fn)
    return field.as_sql(pb, table_alias, cast=cast)


# ---------------------------------------------------------------------------
# Summary field handlers
# ---------------------------------------------------------------------------


def _handle_status_summary_field(
    pb: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
    read_table: "ReadTable" = ReadTable.CALLS_MERGED,
) -> str:
    # Status logic:
    # - If exception is not null -> ERROR
    # - Else if ended_at is null -> RUNNING
    # - Else -> SUCCESS
    exception_field = get_field_by_name("exception")
    ended_at_field = get_field_by_name("ended_at")
    status_counts_field = get_field_by_name("summary.status_counts.error")

    exception_sql = _field_as_sql_maybe_agg(
        exception_field, pb, table_alias, use_agg_fn
    )
    ended_to_sql = _field_as_sql_maybe_agg(ended_at_field, pb, table_alias, use_agg_fn)
    status_counts_sql = _field_as_sql_maybe_agg(
        status_counts_field, pb, table_alias, use_agg_fn, cast="int"
    )

    error_param = pb.add_param(tsi.TraceStatus.ERROR.value)
    running_param = pb.add_param(tsi.TraceStatus.RUNNING.value)
    success_param = pb.add_param(tsi.TraceStatus.SUCCESS.value)
    descendant_error_param = pb.add_param(tsi.TraceStatus.DESCENDANT_ERROR.value)

    exception_check = exception_field.null_check_sql(
        pb, table_alias, read_table, use_agg_fn=use_agg_fn, negate=True
    )
    ended_at_null = ended_at_field.null_check_sql(
        pb, table_alias, read_table, use_agg_fn=use_agg_fn
    )

    return f"""CASE
        WHEN {exception_check} THEN {param_slot(error_param, "String")}
        WHEN IFNULL({status_counts_sql}, 0) > 0 THEN {param_slot(descendant_error_param, "String")}
        WHEN {ended_at_null} THEN {param_slot(running_param, "String")}
        ELSE {param_slot(success_param, "String")}
    END"""


def _handle_latency_ms_summary_field(
    pb: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
    read_table: "ReadTable" = ReadTable.CALLS_MERGED,
) -> str:
    # Latency_ms logic:
    # - If ended_at is null, return null
    # - Otherwise calculate milliseconds between started_at and ended_at
    started_at_field = get_field_by_name("started_at")
    ended_at_field = get_field_by_name("ended_at")

    started_at_sql = _field_as_sql_maybe_agg(
        started_at_field, pb, table_alias, use_agg_fn
    )
    ended_at_sql = _field_as_sql_maybe_agg(ended_at_field, pb, table_alias, use_agg_fn)
    ended_at_null = ended_at_field.null_check_sql(
        pb, table_alias, read_table, use_agg_fn=use_agg_fn
    )

    return f"""CASE
        WHEN {ended_at_null} THEN NULL
        ELSE (
            toUnixTimestamp64Milli({ended_at_sql}) - toUnixTimestamp64Milli({started_at_sql})
        )
    END"""


def _handle_trace_name_summary_field(
    pb: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
    read_table: "ReadTable" = ReadTable.CALLS_MERGED,
) -> str:
    # Trace_name logic:
    # - If display_name is available, use that
    # - Else if op_name starts with 'weave-trace-internal:///', extract the name using regex
    # - Otherwise, just use op_name directly
    display_name_field = get_field_by_name("display_name")
    op_name_field = get_field_by_name("op_name")

    display_name_sql = _field_as_sql_maybe_agg(
        display_name_field, pb, table_alias, use_agg_fn
    )
    op_name_sql = _field_as_sql_maybe_agg(op_name_field, pb, table_alias, use_agg_fn)

    display_name_set = display_name_field.null_check_sql(
        pb, table_alias, read_table, use_agg_fn=use_agg_fn, negate=True
    )
    # For calls_merged, display_name is Nullable(String) so an empty string
    # is distinct from NULL.  Exclude both to preserve pre-sentinel behavior.
    if read_table == ReadTable.CALLS_MERGED:
        display_name_set = f"{display_name_set} AND {display_name_sql} != ''"

    return f"""CASE
        WHEN {display_name_set} THEN {display_name_sql}
        WHEN {op_name_sql} IS NOT NULL AND {op_name_sql} LIKE 'weave-trace-internal:///%' THEN
            regexpExtract(toString({op_name_sql}), '/([^/:]*):', 1)
        ELSE {op_name_sql}
    END"""


# Map of summary fields to their handler functions
SUMMARY_FIELD_HANDLERS: dict[
    str, Callable[[ParamBuilder, str, bool, "ReadTable"], str]
] = {
    "status": _handle_status_summary_field,
    "latency_ms": _handle_latency_ms_summary_field,
    "trace_name": _handle_trace_name_summary_field,
}


def get_summary_field_handler(
    summary_field: str,
) -> Callable[[ParamBuilder, str, bool, "ReadTable"], str] | None:
    """Returns the handler function for a given summary field name."""
    return SUMMARY_FIELD_HANDLERS.get(summary_field)
