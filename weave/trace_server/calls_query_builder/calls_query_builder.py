"""This module builds on the orm.py module to provide a more hard-coded optimized
query builder specifically for the "Calls" table (which is the `calls_merged`
underlying table).

The `CallsQuery` class is the main entry point for building a query. These
optimizations are hand-tuned for Clickhouse - and in particular attempt to
perform predicate pushdown where possible and delay loading expensive fields as
much as possible. In testing, Clickhouse performance is dominated by the amount
of data loaded into memory.

Outstanding Optimizations/Work:

* [ ] The CallsQuery API itself is a little clunky with the returning self pattern. Consider revision
* [ ] This code could use more of the orm.py code to reduce logical duplication,
  specifically:

        1. `process_query_to_conditions` is nearly identical to the one in
        orm.py, but differs enough that generalizing a common function was not
        trivial.
        2. We define our own column definitions here, which might be
        able to use the ones in orm.py.

* [ ] Implement column selection at interface level so that it can be used here
* [ ] Consider how we will do latency order/filter

"""

import logging
import re
from collections.abc import Callable, KeysView
from typing import Literal, NamedTuple, cast

from pydantic import BaseModel, Field
from typing_extensions import Self

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.cte import CTECollection
from weave.trace_server.calls_query_builder.object_ref_query_builder import (
    ObjectRefCondition,
    ObjectRefOrderCondition,
    ObjectRefQueryProcessor,
    build_object_ref_ctes,
    get_all_object_ref_conditions,
    has_object_ref_field,
    is_object_ref_operand,
    process_query_for_object_refs,
)
from weave.trace_server.calls_query_builder.optimization_builder import (
    process_query_to_optimization_sql,
)
from weave.trace_server.calls_query_builder.utils import (
    json_dump_field_as_sql,
    param_slot,
    safely_format_sql,
)
from weave.trace_server.clickhouse_trace_server_settings import LOCAL_TABLE_SUFFIX
from weave.trace_server.common_interface import SortBy
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    combine_conditions,
    python_value_to_ch_type,
    split_escaped_field_path,
)
from weave.trace_server.project_version.types import ReadTable, TableConfig
from weave.trace_server.token_costs import build_cost_ctes, get_cost_final_select
from weave.trace_server.trace_server_common import assert_parameter_length_less_than_max
from weave.trace_server.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
)

logger = logging.getLogger(__name__)

CTE_FILTERED_CALLS = "filtered_calls"
CTE_ALL_CALLS = "all_calls"


class FilterConditionsResult(NamedTuple):
    """Result from building filter conditions.

    Attributes:
        filter_sql: SQL filter clause (HAVING for calls_merged, AND for calls_complete)
        needs_feedback: Whether feedback table JOIN is needed
        needs_queue_items: Whether annotation_queue_items JOIN is needed
        queue_id_filter: Optional queue_id value for JOIN optimization
    """

    filter_sql: str
    needs_feedback: bool
    needs_queue_items: bool
    queue_id_filter: str | None


class OrderLimitOffsetResult(NamedTuple):
    """Result from building ORDER BY, LIMIT, and OFFSET clauses.

    Attributes:
        order_by_sql: SQL ORDER BY clause
        limit_sql: SQL LIMIT clause
        offset_sql: SQL OFFSET clause
        needs_feedback: Whether feedback table JOIN is needed for ordering
    """

    order_by_sql: str
    limit_sql: str
    offset_sql: str
    needs_feedback: bool


def maybe_agg(expr: str, use_agg_fn: bool) -> str:
    """Wrap expression in any() aggregate function if needed."""
    return f"any({expr})" if use_agg_fn else expr


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
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        return f"{self.as_sql(pb, table_alias)} AS {self.field}"


class CallsMergedField(QueryBuilderField):
    def is_heavy(self) -> bool:
        return False


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

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        return f"{self.as_sql(pb, table_alias, use_agg_fn=use_agg_fn)} AS {self.field}"


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
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        return (
            f"{super().as_sql(pb, table_alias, use_agg_fn=use_agg_fn)} AS {self.field}"
        )

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
    ) -> str:
        # Look up handler for the requested summary field
        handler = get_summary_field_handler(self.summary_field)
        if handler:
            sql = handler(pb, table_alias, use_agg_fn)
            return clickhouse_cast(sql, cast)
        else:
            supported_fields = ", ".join(SUMMARY_FIELD_HANDLERS.keys())
            raise NotImplementedError(
                f"Summary field '{self.summary_field}' not implemented. "
                f"Supported fields are: {supported_fields}"
            )

    def as_select_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        return f"{self.as_sql(pb, table_alias, use_agg_fn=use_agg_fn)} AS {self.field}"

    def is_heavy(self) -> bool:
        # These are computed from non-heavy fields (status uses exception and ended_at)
        # If we add more summary fields that depend on heavy fields,
        # this would need to be made more sophisticated
        return False


class CallsMergedFeedbackPayloadField(CallsMergedField):
    feedback_type: str
    extra_path: list[str]

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
            return CallsMergedFeedbackPayloadField(
                field="payload_dump",
                feedback_type=feedback_type,
                extra_path=extra_path[1:],
            )
        elif extra_path[0] == "runnable_ref":
            return CallsMergedFeedbackPayloadField(
                field="runnable_ref", feedback_type=feedback_type, extra_path=[]
            )
        elif extra_path[0] == "trigger_ref":
            return CallsMergedFeedbackPayloadField(
                field="trigger_ref", feedback_type=feedback_type, extra_path=[]
            )
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
            # If we are aggregating (calls_merged) use any, non-aggregate uses directly
            res = inner
            if use_agg_fn:
                res = f"any({inner})"
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
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
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
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
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
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        # It doesn't make sense for a non-root call to have a total storage size,
        # even if a value could be computed.
        parent_id_expr = maybe_agg(f"{table_alias}.parent_id", use_agg_fn)
        storage_expr = maybe_agg(
            f"{self.join_table_name}.total_storage_size_bytes", use_agg_fn
        )
        conditional_field = f"""
            CASE
                WHEN {parent_id_expr} IS NULL
                THEN {storage_expr}
                ELSE NULL
            END
            """
        return f"{conditional_field} AS {self.field}"


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
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        return f"{super().as_sql(pb, table_alias)} AS {self.field}"


class WhereFilters(BaseModel):
    """Container for all WHERE clause optimization filters.

    These filters are applied before GROUP BY to reduce the amount of data
    that needs to be aggregated.
    """

    id_mask: str = ""
    id_subquery: str = ""
    sortable_datetime: str = ""
    wb_run_id: str = ""
    trace_roots_only: str = ""
    parent_ids: str = ""
    op_name: str = ""
    trace_id: str = ""
    thread_id: str = ""
    turn_id: str = ""
    heavy_filter: str = ""
    ref_filter: str = ""
    object_refs: str = ""

    def to_sql(self) -> str:
        """Convert all filters to SQL clauses suitable for WHERE clause.

        Returns a string with all non-empty filters, each starting with 'AND'.
        """
        filters = [
            self.id_mask,
            self.id_subquery,
            self.sortable_datetime,
            self.wb_run_id,
            self.trace_roots_only,
            self.parent_ids,
            self.op_name,
            self.trace_id,
            self.thread_id,
            self.turn_id,
            self.heavy_filter,
            self.ref_filter,
            self.object_refs,
        ]
        return "\n        ".join(f for f in filters if f)


class QueryJoins(BaseModel):
    """Container for all JOIN clauses in the query."""

    feedback: str = ""
    queue_items: str = ""
    storage_size: str = ""
    total_storage_size: str = ""
    object_ref: str = ""

    def to_sql(self) -> str:
        """Convert all joins to SQL clauses.

        Returns a string with all non-empty joins, properly formatted.
        """
        joins = [
            self.feedback,
            self.queue_items,
            self.storage_size,
            self.total_storage_size,
            self.object_ref,
        ]
        return "\n        ".join(j for j in joins if j)


class OrderField(BaseModel):
    field: QueryBuilderField
    direction: Literal["ASC", "DESC"]

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        options: list[tuple[tsi_query.CastTo | None, str]]
        if isinstance(
            self.field,
            (
                QueryBuilderDynamicField,
                CallsMergedDynamicField,
                CallsMergedFeedbackPayloadField,
            ),
        ):
            # Prioritize existence, then cast to double, then str
            options = [
                ("exists", "desc"),
                ("double", self.direction),
                ("string", self.direction),
            ]
        else:
            options = [(None, self.direction)]

        # Check if this is an object ref order field
        if (
            expand_columns
            and field_to_object_join_alias_map
            and has_object_ref_field(self.raw_field_path, expand_columns)
        ):
            order_condition = ObjectRefOrderCondition(
                field_path=self.raw_field_path,
                expand_columns=expand_columns,
            )
            cte_alias = field_to_object_join_alias_map.get(order_condition.unique_key)
            if cte_alias:
                return self._build_object_ref_order_sql(cte_alias, options, use_agg_fn)

        # Standard field ordering logic
        return self._build_standard_order_sql(pb, table_alias, options, use_agg_fn)

    def _build_object_ref_order_sql(
        self,
        cte_alias: str,
        options: list[tuple[tsi_query.CastTo | None, str]],
        use_agg_fn: bool,
    ) -> str:
        """Build ORDER BY SQL for object reference fields."""
        base_expr = f"{cte_alias}.object_val_dump"
        base_sql = maybe_agg(base_expr, use_agg_fn)

        parts = []
        for cast_to, direction in options:
            if cast_to == "exists":
                json_expr = maybe_agg(base_expr, use_agg_fn)
                cast_sql = f"(NOT (JSONType({json_expr}) = 'Null' OR JSONType({json_expr}) IS NULL))"
            else:
                cast_sql = clickhouse_cast(base_sql, cast_to)
            parts.append(f"{cast_sql} {direction}")
        return ", ".join(parts)

    def _build_standard_order_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        options: list[tuple[tsi_query.CastTo | None, str]],
        use_agg_fn: bool,
    ) -> str:
        """Build ORDER BY SQL for standard fields."""
        parts = []
        for cast_to, direction in options:
            if isinstance(
                self.field,
                (
                    CallsMergedAggField,
                    CallsMergedFeedbackPayloadField,
                    CallsMergedSummaryField,
                ),
            ):
                field_sql = self.field.as_sql(
                    pb, table_alias, cast_to, use_agg_fn=use_agg_fn
                )
            else:
                field_sql = self.field.as_sql(pb, table_alias, cast_to)
            parts.append(f"{field_sql} {direction}")
        return ", ".join(parts)

    @property
    def raw_field_path(self) -> str:
        """Returns the raw field path as a user would see it, i.e. the field path
        without the _dump suffix and includes the extra path dot separate.

        Example:
            OrderField(field=CallsMergedField(field="inputs_dump", extra_path=["model", "temperature"])).raw_field_path
                -> inputs.model.temperature
        """
        field_path = self.field.field
        if field_path.endswith("_dump"):
            field_path = field_path[:-5]
        if hasattr(self.field, "extra_path") and self.field.extra_path:
            field_path += "." + ".".join(self.field.extra_path)
        return field_path


class Condition(BaseModel):
    operand: "tsi_query.Operand"
    _consumed_fields: list[CallsMergedField] | None = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        # Check if this condition involves object references
        if (
            expand_columns
            and is_object_ref_operand(self.operand, expand_columns)
            and field_to_object_join_alias_map
        ):
            processor = ObjectRefQueryProcessor(
                pb,
                table_alias,
                expand_columns,
                field_to_object_join_alias_map,
                use_agg_fn=use_agg_fn,
            )
            sql = processor.process_operand(self.operand)
            if self._consumed_fields is None:
                self._consumed_fields = []
            for raw_field_path in processor.fields_used:
                self._consumed_fields.append(get_field_by_name(raw_field_path))
            return sql

        conditions = process_query_to_conditions(
            tsi_query.Query.model_validate({"$expr": {"$and": [self.operand]}}),
            pb,
            table_alias,
            use_agg_fn=use_agg_fn,
        )
        if self._consumed_fields is None:
            self._consumed_fields = []
            for field in conditions.fields_used:
                self._consumed_fields.append(field)
        return combine_conditions(conditions.conditions, "AND")

    def _get_consumed_fields(
        self, table_alias: str = "calls_merged"
    ) -> list[CallsMergedField]:
        if self._consumed_fields is None:
            self.as_sql(ParamBuilder(), table_alias)
        if self._consumed_fields is None:
            raise ValueError("Consumed fields should not be None")
        return self._consumed_fields

    def is_heavy(self, table_alias: str = "calls_merged") -> bool:
        for field in self._get_consumed_fields(table_alias):
            if field.is_heavy():
                return True
        return False

    def is_feedback(self, table_alias: str = "calls_merged") -> bool:
        for field in self._get_consumed_fields(table_alias):
            if isinstance(field, CallsMergedFeedbackPayloadField):
                return True
        return False

    def is_queue_item(self, table_alias: str = "calls_merged") -> bool:
        for field in self._get_consumed_fields(table_alias):
            if isinstance(field, CallsMergedQueueItemField):
                return True
        return False

    def get_object_ref_conditions(
        self, expand_columns: list[str] | None, table_alias: str
    ) -> list[ObjectRefCondition]:
        """Get any object ref conditions for CTE building."""
        expand_cols = expand_columns or []
        if not expand_cols or not is_object_ref_operand(self.operand, expand_cols):
            return []

        query_for_condition = tsi_query.Query.model_validate({"$expr": self.operand})
        object_ref_conditions = process_query_for_object_refs(
            query_for_condition, ParamBuilder(), table_alias, expand_cols
        )
        return object_ref_conditions


class HardCodedFilter(BaseModel):
    filter: tsi.CallsFilter

    def is_useful(self) -> bool:
        """Returns True if the filter is useful - i.e. it has any non-null fields
        which would affect the query.
        """
        return any(
            [
                self.filter.op_names,
                self.filter.input_refs,
                self.filter.output_refs,
                self.filter.parent_ids,
                self.filter.trace_ids,
                self.filter.call_ids,
                self.filter.trace_roots_only is not None,
                self.filter.wb_user_ids,
                self.filter.wb_run_ids,
                self.filter.turn_ids,
                self.filter.thread_ids is not None,
            ]
        )

    def as_sql(
        self, pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
    ) -> str:
        return combine_conditions(
            process_calls_filter_to_conditions(
                self.filter, pb, table_alias, use_agg_fn=use_agg_fn
            ),
            "AND",
        )


class CallsQuery(BaseModel):
    """Critical to be injection safe!"""

    project_id: str
    select_fields: list[CallsMergedField] = Field(default_factory=list)
    query_conditions: list[Condition] = Field(default_factory=list)
    hardcoded_filter: HardCodedFilter | None = None
    order_fields: list[OrderField] = Field(default_factory=list)
    limit: int | None = None
    offset: int | None = None
    expand_columns: list[str] = Field(default_factory=list)
    include_costs: bool = False
    include_storage_size: bool = False
    include_total_storage_size: bool = False
    read_table: ReadTable = ReadTable.CALLS_MERGED

    @property
    def use_agg_fn(self) -> bool:
        """Whether to use aggregate functions in SQL generation."""
        return self.read_table != ReadTable.CALLS_COMPLETE

    @property
    def table_name(self) -> str:
        """The table name to query from, derived from read_table."""
        return self.read_table.value

    def add_field(self, field: str) -> "CallsQuery":
        name = get_field_by_name(field)
        if name in self.select_fields:
            return self
        self.select_fields.append(name)
        return self

    def add_condition(self, operand: "tsi_query.Operand") -> "CallsQuery":
        if isinstance(operand, tsi_query.AndOperation):
            if len(operand.and_) == 0:
                raise ValueError("Empty AND operation")
            for op in operand.and_:
                self.add_condition(op)
        else:
            self.query_conditions.append(Condition(operand=operand))
        return self

    def set_hardcoded_filter(self, filter: HardCodedFilter) -> "CallsQuery":
        if filter.is_useful():
            self.hardcoded_filter = filter
        return self

    def add_order(self, field: str, direction: str) -> "CallsQuery":
        if field in DISALLOWED_FILTERING_FIELDS:
            raise ValueError(f"Field {field} is not allowed in ORDER BY")
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Direction {direction} is not allowed")
        direction = cast(Literal["ASC", "DESC"], direction)
        self.order_fields.append(
            OrderField(field=get_field_by_name(field), direction=direction)
        )
        return self

    def set_limit(self, limit: int) -> "CallsQuery":
        if limit < 0:
            raise ValueError("Limit must be a positive integer")
        if self.limit is not None:
            raise ValueError("Limit can only be set once")
        self.limit = limit
        return self

    def set_offset(self, offset: int) -> "CallsQuery":
        if offset < 0:
            raise ValueError("Offset must be a positive integer")
        if self.offset is not None:
            raise ValueError("Offset can only be set once")
        self.offset = offset
        return self

    def clone(self) -> "CallsQuery":
        return CallsQuery(
            project_id=self.project_id,
            select_fields=self.select_fields.copy(),
            query_conditions=self.query_conditions.copy(),
            order_fields=self.order_fields.copy(),
            hardcoded_filter=self.hardcoded_filter,
            limit=self.limit,
            offset=self.offset,
            read_table=self.read_table,
        )

    def set_include_costs(self, include_costs: bool) -> "CallsQuery":
        self.include_costs = include_costs
        return self

    def set_expand_columns(self, expand_columns: list[str]) -> "CallsQuery":
        self.expand_columns = expand_columns
        return self

    def _extract_queue_id_from_operand(
        self, operand: "tsi_query.Operand"
    ) -> str | None:
        """Recursively extract queue_id from an operand tree."""
        if isinstance(operand, tsi_query.EqOperation):
            # Check if this is annotation_queue_items.queue_id = <value>
            if len(operand.eq_) == 2:
                lhs, rhs = operand.eq_[0], operand.eq_[1]
                if (
                    isinstance(lhs, tsi_query.GetFieldOperator)
                    and lhs.get_field_ == "annotation_queue_items.queue_id"
                    and isinstance(rhs, tsi_query.LiteralOperation)
                    and isinstance(rhs.literal_, str)
                ):
                    return rhs.literal_
        elif isinstance(operand, tsi_query.AndOperation):
            # Recursively check AND branches
            for op in operand.and_:
                queue_id = self._extract_queue_id_from_operand(op)
                if queue_id:
                    return queue_id
        return None

    def _should_optimize(self) -> bool:
        """Determines if query optimization should be performed.

        Returns True if the query has heavy fields and predicate pushdown is possible.
        Heavy fields are expensive to load into memory (inputs, output, attributes, summary).
        Predicate pushdown is possible when there are light filters, light query conditions,
        or light order filters that can be pushed down into a subquery.
        """
        # First, check if the query has any heavy fields
        table_name = get_calls_table_name(self.read_table)
        has_heavy_select = any(field.is_heavy() for field in self.select_fields)
        has_heavy_filter = any(
            condition.is_heavy(table_name) for condition in self.query_conditions
        )
        has_heavy_order = any(
            order_field.field.is_heavy() for order_field in self.order_fields
        )

        # If no heavy fields, no need to optimize
        if not (has_heavy_select or has_heavy_filter or has_heavy_order):
            return False

        # If filtering by actual data, do predicate pushdown, should optimize
        if self.hardcoded_filter and self.hardcoded_filter.is_useful():
            return True

        # If any light conditions exist, use them to filter rows before loading heavy fields
        if any(
            not condition.is_heavy(table_name) for condition in self.query_conditions
        ):
            return True

        # Check for light order filter
        if (
            self.order_fields
            and self.limit
            and not has_heavy_filter
            and not has_heavy_order
        ):
            return True

        # No predicate pushdown possible
        return False

    def as_sql(self, pb: ParamBuilder, table_alias: str | None = None) -> str:
        """This is the main entry point for building the query. This method will
        determine the optimal query to build based on the fields and conditions
        that have been set.

        Note 1: `LIGHT` fields are those that are relatively inexpensive to load into
        memory, while `HEAVY` fields are those that are expensive to load into memory.
        Practically, `HEAVY` fields are the free-form user-defined fields: `inputs`,
        `output`, `attributes`, and `summary`.

        Note 2: `FILTER_CONDITIONS` are assumed to be "anded" together.

        Now, everything starts with the `BASE QUERY`:

        ```sql
        SELECT {SELECT_FIELDS}
        FROM calls_merged
        WHERE project_id = {PROJECT_ID}
        AND id IN {ID_MASK}                     -- optional
        GROUP BY (project_id, id)
        HAVING {FILTER_CONDITIONS}              -- optional
        ORDER BY {ORDER_FIELDS}                 -- optional
        LIMIT {LIMIT}                           -- optional
        OFFSET {OFFSET}                         -- optional
        ```

        From here, we need to answer 2 questions:

        1. Does this query involve any `HEAVY` fields (across `SELECT_FIELDS`,
        `FILTER_CONDITIONS`, and `ORDER_FIELDS`)?
        2. Is it possible to push down predicates into a subquery? This is true if any
        of the following are true:

            a. There is an `ID_MASK`
            b. The `FILTER_CONDITIONS` have at least one "and" condition composed
            entirely of `LIGHT` fields that is not the `deleted_at` clause
            c. The ORDER BY clause can be transformed into a "light filter". Requires:

                1. No `HEAVY` fields in the ORDER BY clause
                2. No `HEAVY` fields in the FILTER_CONDITIONS
                3. A `LIMIT` clause.

        If any of the above are true, then we can push down the predicates into a subquery. This
        results in the following query:

        ```sql
        WITH filtered_calls AS (
            SELECT id
            FROM calls_merged
            WHERE project_id = {PROJECT_ID}
            AND id IN {ID_MASK}                 -- optional
            GROUP BY (project_id, id)
            HAVING {LIGHT_FILTER_CONDITIONS}    -- optional
            --- IF ORDER BY CAN BE PUSHED DOWN ---
            ORDER BY {ORDER_FIELDS}                 -- optional
            LIMIT {LIMIT}                           -- optional
            OFFSET {OFFSET}                         -- optional
        )
        SELECT {SELECT_FIELDS}
        FROM calls_merged
        WHERE project_id = {PROJECT_ID}
        AND id IN filtered_calls
        GROUP BY (project_id, id)
        --- IF ORDER BY CANNOT BE PUSHED DOWN ---
        HAVING {HEAVY_FILTER_CONDITIONS}        -- optional <-- yes, this is inside the conditional
        ORDER BY {ORDER_FIELDS}                 -- optional
        LIMIT {LIMIT}                           -- optional
        OFFSET {OFFSET}                         -- optional
        ```

        """
        if not self.select_fields:
            raise ValueError("Missing select columns")

        # Determine if we should optimize!
        should_optimize = self._should_optimize()

        # Important: Always inject deleted_at into the query.
        # Note: it might be better to make this configurable.
        self.add_condition(
            tsi_query.EqOperation.model_validate(
                {"$eq": [{"$getField": "deleted_at"}, {"$literal": None}]}
            )
        )

        # Important: We must always filter out calls that have not been started
        # This can occur when there is an out of order call part insertion or worse,
        # when such occurrence happens and the client terminates early.
        # Additionally: This condition is also REQUIRED for proper functioning
        # when using pre-group by (WHERE) optimizations
        self.add_condition(
            tsi_query.NotOperation.model_validate(
                {"$not": [{"$eq": [{"$getField": "started_at"}, {"$literal": None}]}]}
            )
        )

        table_alias_resolved = table_alias or get_calls_table_name(self.read_table)

        object_ref_conditions = get_all_object_ref_conditions(
            self.query_conditions,
            self.order_fields,
            self.expand_columns,
            table_alias_resolved,
        )

        # If we should not optimize, then just build the base query
        if not should_optimize and not self.include_costs and not object_ref_conditions:
            return self._as_sql_base_format(pb, table_alias_resolved)

        # Build two queries, first filter query CTE, then select the columns
        filter_query = CallsQuery(
            project_id=self.project_id, read_table=self.read_table
        )
        select_query = CallsQuery(
            project_id=self.project_id,
            include_storage_size=self.include_storage_size,
            include_total_storage_size=self.include_total_storage_size,
            read_table=self.read_table,
        )

        # Select Fields:
        filter_query.add_field("id")
        for field in self.select_fields:
            select_query.select_fields.append(field)

        ctes, field_to_object_join_alias_map = build_object_ref_ctes(
            pb, self.project_id, object_ref_conditions
        )

        for condition in self.query_conditions:
            filter_query.query_conditions.append(condition)

        filter_query.hardcoded_filter = self.hardcoded_filter

        # Order Fields:
        filter_query.order_fields = self.order_fields
        filter_query.limit = self.limit
        filter_query.offset = self.offset
        # SUPER IMPORTANT: still need to re-sort the final query
        select_query.order_fields = self.order_fields

        # When using the CTE pattern, ensure all fields used in ordering
        # are selected in select_query so they're available in the final query's ORDER BY.
        if self.include_costs:
            for order_field in self.order_fields:
                field_obj = order_field.field
                # Skip feedback fields - they're handled via LEFT JOIN and don't need to be selected
                if isinstance(field_obj, CallsMergedFeedbackPayloadField):
                    continue

                if isinstance(
                    field_obj, (CallsMergedDynamicField, QueryBuilderDynamicField)
                ):
                    # we need to add the base field, not the dynamic one
                    base_field = get_field_by_name(field_obj.field)
                    if base_field not in select_query.select_fields:
                        select_query.select_fields.append(base_field)
                else:
                    # For non-dynamic fields (like started_at, op_name, etc.),
                    # add the field directly to ensure it's available in CTEs
                    if field_obj not in select_query.select_fields:
                        assert isinstance(field_obj, CallsMergedField), (
                            "Field must be a CallsMergedField"
                        )
                        select_query.select_fields.append(field_obj)

        filtered_calls_sql = filter_query._as_sql_base_format(
            pb,
            table_alias_resolved,
            field_to_object_join_alias_map=field_to_object_join_alias_map,
            expand_columns=self.expand_columns,
        )
        ctes.add_cte(CTE_FILTERED_CALLS, filtered_calls_sql)

        base_sql = select_query._as_sql_base_format(
            pb,
            table_alias_resolved,
            id_subquery_name=CTE_FILTERED_CALLS,
            field_to_object_join_alias_map=field_to_object_join_alias_map,
            expand_columns=self.expand_columns,
        )

        if not self.include_costs:
            raw_sql = ctes.to_sql() + "\n" + base_sql
            return safely_format_sql(raw_sql, logger)

        ctes.add_cte(CTE_ALL_CALLS, base_sql)
        self._add_cost_ctes_to_builder(ctes, pb)

        select_fields = [field.field for field in self.select_fields]
        final_select = get_cost_final_select(
            pb, select_fields, self.order_fields, self.project_id
        )

        raw_sql = ctes.to_sql() + "\n" + final_select
        return safely_format_sql(raw_sql, logger)

    def _add_cost_ctes_to_builder(self, ctes: CTECollection, pb: ParamBuilder) -> None:
        cost_cte_list = build_cost_ctes(pb, CTE_ALL_CALLS, self.project_id)
        for cte in cost_cte_list:
            ctes.add_cte(cte.name, cte.sql)

    def _convert_to_orm_sort_fields(self) -> list[SortBy]:
        return [
            SortBy(
                field=sort_by.field.field,
                direction=cast(Literal["asc", "desc"], sort_by.direction.lower()),
            )
            for sort_by in self.order_fields
        ]

    def _build_where_clause_optimizations(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None,
        id_subquery_name: str | None = None,
    ) -> WhereFilters:
        """Build all WHERE clause optimization filters.

        These filters are applied before GROUP BY to reduce the amount of data
        that needs to be aggregated.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL
            expand_columns: List of columns that should be expanded for object refs
            id_subquery_name: Optional name of a CTE containing filtered IDs

        Returns:
            WhereFilters object containing all filter SQL strings
        """
        # The op_name, trace_id, trace_roots, wb_run_id conditions REQUIRE conditioning
        # on the started_at field after grouping in the HAVING clause. These filters
        # remove call starts before grouping, creating orphan call ends. By conditioning
        # on `NOT any(started_at) is NULL`, we filter out orphaned call ends, ensuring
        # all rows returned at least have a call start.

        op_name = process_op_name_filter_to_sql(self.hardcoded_filter, pb, table_alias)
        trace_id = process_trace_id_filter_to_sql(
            self.hardcoded_filter, pb, table_alias
        )
        thread_id = process_thread_id_filter_to_sql(
            self.hardcoded_filter, pb, table_alias
        )
        turn_id = process_turn_id_filter_to_sql(self.hardcoded_filter, pb, table_alias)
        wb_run_id = process_wb_run_ids_filter_to_sql(
            self.hardcoded_filter, pb, table_alias
        )
        ref_filter = process_ref_filters_to_sql(self.hardcoded_filter, pb, table_alias)
        trace_roots_only = process_trace_roots_only_filter_to_sql(
            self.hardcoded_filter, pb, table_alias
        )
        parent_ids = process_parent_ids_filter_to_sql(
            self.hardcoded_filter, pb, table_alias
        )

        # Filter out object ref conditions from optimization since they're handled via CTEs
        non_object_ref_conditions = []
        object_ref_fields_consumed: set[str] = set()
        for condition in self.query_conditions:
            if not (
                expand_columns
                and is_object_ref_operand(condition.operand, expand_columns)
            ):
                non_object_ref_conditions.append(condition)
            else:
                if condition._consumed_fields is not None:
                    object_ref_fields_consumed.update(
                        f.field for f in condition._consumed_fields
                    )

        optimization_conditions = process_query_to_optimization_sql(
            non_object_ref_conditions, pb, table_alias, self.read_table
        )
        sortable_datetime = optimization_conditions.sortable_datetime_filters_sql or ""
        heavy_filter = optimization_conditions.heavy_filter_opt_sql or ""

        object_refs = process_object_refs_filter_to_opt_sql(
            pb, table_alias, object_ref_fields_consumed
        )

        id_subquery = ""
        if id_subquery_name is not None:
            id_subquery = f"AND ({table_alias}.id IN {id_subquery_name})"

        # special optimization for call_ids filter
        id_mask = ""
        if self.hardcoded_filter and self.hardcoded_filter.filter.call_ids:
            id_mask = f"AND ({table_alias}.id IN {param_slot(pb.add_param(self.hardcoded_filter.filter.call_ids), 'Array(String)')})"

        return WhereFilters(
            id_mask=id_mask,
            id_subquery=id_subquery,
            op_name=op_name,
            trace_id=trace_id,
            thread_id=thread_id,
            turn_id=turn_id,
            wb_run_id=wb_run_id,
            ref_filter=ref_filter,
            trace_roots_only=trace_roots_only,
            parent_ids=parent_ids,
            object_refs=object_refs,
            sortable_datetime=sortable_datetime,
            heavy_filter=heavy_filter,
        )

    def _build_joins(
        self,
        pb: ParamBuilder,
        table_alias: str,
        project_param: str,
        needs_feedback: bool,
        needs_queue_items: bool,
        queue_id_filter: str | None,
        expand_columns: list[str] | None,
        field_to_object_join_alias_map: dict[str, str] | None,
    ) -> QueryJoins:
        """Build all JOIN clauses for the query.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL
            project_param: The parameter name for project_id
            needs_feedback: Whether feedback JOIN is needed
            needs_queue_items: Whether annotation_queue_items JOIN is needed
            queue_id_filter: Optional queue_id value to filter the JOIN (optimization)
            expand_columns: List of columns that should be expanded for object refs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases

        Returns:
            QueryJoins object containing all join SQL strings
        """
        # Feedback join
        feedback_join = ""
        if needs_feedback:
            feedback_join = f"""
            LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {param_slot(project_param, "String")}
            ) AS feedback ON (
                feedback.weave_ref = concat('weave-trace-internal:///', {param_slot(project_param, "String")}, '/call/', {table_alias}.id))
            """

        # Queue items join
        # Uses INNER JOIN because we only add this join when filtering by queue,
        # and we always want to exclude calls not in the queue (no need for LEFT JOIN + HAVING)
        queue_items_join = ""
        if needs_queue_items:
            # Build WHERE clause for the subquery
            queue_where_clauses = [
                f"annotation_queue_items.project_id = {param_slot(project_param, 'String')}",
                "annotation_queue_items.deleted_at IS NULL",
            ]
            queue_id_param = pb.add_param(queue_id_filter)
            queue_where_clauses.append(
                f"annotation_queue_items.queue_id = {param_slot(queue_id_param, 'String')}"
            )

            queue_items_join = f"""
            INNER JOIN (
                SELECT * FROM annotation_queue_items
                WHERE {" AND ".join(queue_where_clauses)}
            ) AS annotation_queue_items ON (
                annotation_queue_items.project_id = {table_alias}.project_id
                AND annotation_queue_items.call_id = {table_alias}.id)
            """

        # Storage size join
        storage_size_join = ""
        config = TableConfig.from_read_table(self.read_table)
        if self.include_storage_size:
            storage_size_join = f"""
            LEFT JOIN (
                SELECT
                    id,
                    sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) AS storage_size_bytes
                FROM {config.stats_table_name}
                WHERE project_id = {param_slot(project_param, "String")}
                GROUP BY id
            ) AS {STORAGE_SIZE_TABLE_NAME}
            ON {table_alias}.id = {STORAGE_SIZE_TABLE_NAME}.id
            """

        # Total storage size join
        total_storage_size_join = ""
        if self.include_total_storage_size:
            total_storage_size_join = f"""
            LEFT JOIN (
                SELECT
                    trace_id,
                    sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) AS total_storage_size_bytes
                FROM {config.stats_table_name}
                WHERE project_id = {param_slot(project_param, "String")}
                GROUP BY trace_id
            ) AS {ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME}
            ON {table_alias}.trace_id = {ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME}.trace_id
            """

        # Object reference joins for ordering
        object_ref_joins_parts = []
        if expand_columns and field_to_object_join_alias_map:
            for order_field in self.order_fields:
                field_path = order_field.raw_field_path
                if not has_object_ref_field(field_path, expand_columns):
                    continue
                order_condition = ObjectRefOrderCondition(
                    field_path=field_path,
                    expand_columns=expand_columns,
                )
                join_condition_sql = order_condition.as_sql_condition(
                    pb,
                    table_alias,
                    field_to_object_join_alias_map,
                    is_order_join=True,
                    use_agg_fn=False,
                )
                object_ref_joins_parts.append(join_condition_sql)

        return QueryJoins(
            feedback=feedback_join,
            queue_items=queue_items_join,
            storage_size=storage_size_join,
            total_storage_size=total_storage_size_join,
            object_ref="".join(object_ref_joins_parts),
        )

    def _build_filter_conditions(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None,
        field_to_object_join_alias_map: dict[str, str] | None,
    ) -> FilterConditionsResult:
        """Build filter conditions for the query.

        For calls_merged (use_agg_fn=True), returns a HAVING clause for post-GROUP BY filtering.
        For calls_complete (use_agg_fn=False), returns AND conditions for WHERE clause filtering.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL
            expand_columns: List of columns that should be expanded for object refs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases

        Returns:
            FilterConditionsResult with filter SQL and dependency flags
        """
        needs_feedback = False
        needs_queue_items = False
        queue_id_filter = None
        filter_conditions_sql: list[str] = []

        if len(self.query_conditions) > 0:
            for query_condition in self.query_conditions:
                query_condition_sql = query_condition.as_sql(
                    pb,
                    table_alias,
                    expand_columns=expand_columns,
                    field_to_object_join_alias_map=field_to_object_join_alias_map,
                    use_agg_fn=self.use_agg_fn,
                )
                filter_conditions_sql.append(query_condition_sql)
                if query_condition.is_feedback(table_alias):
                    needs_feedback = True
                if query_condition.is_queue_item(table_alias):
                    needs_queue_items = True
                    # Extract queue_id for JOIN optimization while we're here
                    if queue_id_filter is None:
                        queue_id_filter = self._extract_queue_id_from_operand(
                            query_condition.operand
                        )

        if self.hardcoded_filter is not None:
            filter_conditions_sql.append(
                self.hardcoded_filter.as_sql(
                    pb, table_alias, use_agg_fn=self.use_agg_fn
                )
            )

        filter_sql = ""
        if len(filter_conditions_sql) > 0:
            # For calls_complete, these become WHERE conditions (no GROUP BY)
            # For calls_merged, these are HAVING conditions (after GROUP BY)
            prefix = "HAVING " if self.use_agg_fn else "AND "
            filter_sql = prefix + combine_conditions(filter_conditions_sql, "AND")

        return FilterConditionsResult(
            filter_sql=filter_sql,
            needs_feedback=needs_feedback,
            needs_queue_items=needs_queue_items,
            queue_id_filter=queue_id_filter,
        )

    def _build_order_limit_offset(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None,
        field_to_object_join_alias_map: dict[str, str] | None,
    ) -> OrderLimitOffsetResult:
        """Build ORDER BY, LIMIT, and OFFSET clauses.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL
            expand_columns: List of columns that should be expanded for object refs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases

        Returns:
            OrderLimitOffsetResult with ORDER BY, LIMIT, OFFSET SQL and feedback flag
        """
        needs_feedback = False
        order_by_sql = ""

        if len(self.order_fields) > 0:
            order_by_sqls = [
                order_field.as_sql(
                    pb,
                    table_alias,
                    expand_columns,
                    field_to_object_join_alias_map,
                    use_agg_fn=self.use_agg_fn,
                )
                for order_field in self.order_fields
            ]
            order_by_sql = "ORDER BY " + ", ".join(order_by_sqls)
            for order_field in self.order_fields:
                if isinstance(order_field.field, CallsMergedFeedbackPayloadField):
                    needs_feedback = True

        limit_sql = f"LIMIT {self.limit}" if self.limit is not None else ""
        offset_sql = f"OFFSET {self.offset}" if self.offset is not None else ""

        return OrderLimitOffsetResult(
            order_by_sql=order_by_sql,
            limit_sql=limit_sql,
            offset_sql=offset_sql,
            needs_feedback=needs_feedback,
        )

    def _as_sql_base_format(
        self,
        pb: ParamBuilder,
        table_alias: str,
        id_subquery_name: str | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        expand_columns: list[str] | None = None,
    ) -> str:
        """Build the base SQL query format.

        This method orchestrates the building of a complete SQL query by delegating
        to specialized helper methods for different query components.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL (typically "calls_merged")
            id_subquery_name: Optional name of a CTE containing filtered IDs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases for object refs
            expand_columns: List of columns that should be expanded for object refs

        Returns:
            Complete SQL query string
        """
        select_fields_sql = ", ".join(
            field.as_select_sql(pb, table_alias, use_agg_fn=self.use_agg_fn)
            for field in self.select_fields
        )
        filter_result = self._build_filter_conditions(
            pb, table_alias, expand_columns, field_to_object_join_alias_map
        )
        where_filters = self._build_where_clause_optimizations(
            pb, table_alias, expand_columns, id_subquery_name
        )
        order_result = self._build_order_limit_offset(
            pb, table_alias, expand_columns, field_to_object_join_alias_map
        )
        project_param = pb.add_param(self.project_id)

        joins = self._build_joins(
            pb,
            table_alias,
            project_param,
            needs_feedback=filter_result.needs_feedback or order_result.needs_feedback,
            needs_queue_items=filter_result.needs_queue_items,
            queue_id_filter=filter_result.queue_id_filter,
            expand_columns=expand_columns,
            field_to_object_join_alias_map=field_to_object_join_alias_map,
        )
        group_by_sql = ""
        if self.use_agg_fn:
            group_by_sql = f"GROUP BY ({table_alias}.project_id, {table_alias}.id)"

        # Assemble the actual SQL query
        # Use PREWHERE for project_id to filter data before reading from disk
        # This is a ClickHouse optimization for high-selectivity filters
        where_filters_sql = where_filters.to_sql()
        # Strip leading "AND " from where_filters since PREWHERE handles the first condition
        where_filters_stripped = re.sub(r"^\s*AND\s+", "", where_filters_sql)
        where_clause = (
            f"WHERE {where_filters_stripped}" if where_filters_stripped else ""
        )

        # Fix where_clause when empty but we have filter_sql
        # For calls_complete (use_agg_fn=False), filter_sql starts with "AND "
        # If where_clause is empty, set it to "WHERE 1" so filter_sql can append naturally
        # TODO: optimize it further to make this condition builder smarter
        if not where_clause and filter_result.filter_sql and not self.use_agg_fn:
            where_clause = "WHERE 1"

        raw_sql = f"""
        SELECT {select_fields_sql}
        FROM {table_alias}
        {joins.to_sql()}
        PREWHERE {table_alias}.project_id = {param_slot(project_param, "String")}
        {where_clause}
        {group_by_sql}
        {filter_result.filter_sql}
        {order_result.order_by_sql}
        {order_result.limit_sql}
        {order_result.offset_sql}
        """

        return safely_format_sql(raw_sql, logger)


STORAGE_SIZE_TABLE_NAME = "storage_size_tbl"
ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME = "rolled_up_cms"


def get_calls_table_name(read_table: ReadTable) -> str:
    """Return the base calls table name for a read table."""
    return TableConfig.from_read_table(read_table).table_name


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


# Handler function for status summary field
def _handle_status_summary_field(
    pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
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

    return f"""CASE
        WHEN {exception_sql} IS NOT NULL THEN {param_slot(error_param, "String")}
        WHEN IFNULL({status_counts_sql}, 0) > 0 THEN {param_slot(descendant_error_param, "String")}
        WHEN {ended_to_sql} IS NULL THEN {param_slot(running_param, "String")}
        ELSE {param_slot(success_param, "String")}
    END"""


# Handler function for latency_ms summary field
def _handle_latency_ms_summary_field(
    pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
) -> str:
    # Latency_ms logic:
    # - If ended_at is null or there's an exception, return null
    # - Otherwise calculate milliseconds between started_at and ended_at
    started_at_field = get_field_by_name("started_at")
    ended_at_field = get_field_by_name("ended_at")

    started_at_sql = _field_as_sql_maybe_agg(
        started_at_field, pb, table_alias, use_agg_fn
    )
    ended_at_sql = _field_as_sql_maybe_agg(ended_at_field, pb, table_alias, use_agg_fn)

    # Convert time difference to milliseconds
    # Use toUnixTimestamp64Milli for direct and precise millisecond difference
    return f"""CASE
        WHEN {ended_at_sql} IS NULL THEN NULL
        ELSE (
            toUnixTimestamp64Milli({ended_at_sql}) - toUnixTimestamp64Milli({started_at_sql})
        )
    END"""


# Handler function for trace_name summary field
def _handle_trace_name_summary_field(
    pb: ParamBuilder, table_alias: str, use_agg_fn: bool = True
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

    return f"""CASE
        WHEN {display_name_sql} IS NOT NULL AND {display_name_sql} != '' THEN {display_name_sql}
        WHEN {op_name_sql} IS NOT NULL AND {op_name_sql} LIKE 'weave-trace-internal:///%' THEN
            regexpExtract(toString({op_name_sql}), '/([^/:]*):', 1)
        ELSE {op_name_sql}
    END"""


# Map of summary fields to their handler functions
SUMMARY_FIELD_HANDLERS = {
    "status": _handle_status_summary_field,
    "latency_ms": _handle_latency_ms_summary_field,
    "trace_name": _handle_trace_name_summary_field,
}


# Helper function to get a summary field handler by name
def get_summary_field_handler(
    summary_field: str,
) -> Callable[[ParamBuilder, str, bool], str] | None:
    """Returns the handler function for a given summary field name."""
    return SUMMARY_FIELD_HANDLERS.get(summary_field)


class FilterToConditions(BaseModel):
    conditions: list[str]
    fields_used: list[CallsMergedField]


def process_query_to_conditions(
    query: tsi.Query,
    param_builder: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
) -> FilterToConditions:
    """Converts a Query to a list of conditions for a clickhouse query."""
    conditions = []
    raw_fields_used: dict[str, CallsMergedField] = {}

    # This is the mongo-style query
    def process_operation(operation: tsi_query.Operation) -> str:
        cond = None

        if isinstance(operation, tsi_query.AndOperation):
            if len(operation.and_) == 0:
                raise ValueError("Empty AND operation")
            elif len(operation.and_) == 1:
                return process_operand(operation.and_[0])
            parts = [process_operand(op) for op in operation.and_]
            cond = f"({' AND '.join(parts)})"
        elif isinstance(operation, tsi_query.OrOperation):
            if len(operation.or_) == 0:
                raise ValueError("Empty OR operation")
            elif len(operation.or_) == 1:
                return process_operand(operation.or_[0])
            parts = [process_operand(op) for op in operation.or_]
            cond = f"({' OR '.join(parts)})"
        elif isinstance(operation, tsi_query.NotOperation):
            operand_part = process_operand(operation.not_[0])
            cond = f"(NOT ({operand_part}))"
        elif isinstance(operation, tsi_query.EqOperation):
            lhs_part = process_operand(operation.eq_[0])
            if (
                isinstance(operation.eq_[1], tsi_query.LiteralOperation)
                and operation.eq_[1].literal_ is None
            ):
                cond = f"({lhs_part} IS NULL)"
            else:
                rhs_part = process_operand(operation.eq_[1])
                cond = f"({lhs_part} = {rhs_part})"
        elif isinstance(operation, tsi_query.GtOperation):
            lhs_part = process_operand(operation.gt_[0])
            rhs_part = process_operand(operation.gt_[1])
            cond = f"({lhs_part} > {rhs_part})"
        elif isinstance(operation, tsi_query.LtOperation):
            lhs_part = process_operand(operation.lt_[0])
            rhs_part = process_operand(operation.lt_[1])
            cond = f"({lhs_part} < {rhs_part})"
        elif isinstance(operation, tsi_query.GteOperation):
            lhs_part = process_operand(operation.gte_[0])
            rhs_part = process_operand(operation.gte_[1])
            cond = f"({lhs_part} >= {rhs_part})"
        elif isinstance(operation, tsi_query.LteOperation):
            lhs_part = process_operand(operation.lte_[0])
            rhs_part = process_operand(operation.lte_[1])
            cond = f"({lhs_part} <= {rhs_part})"
        elif isinstance(operation, tsi_query.InOperation):
            lhs_part = process_operand(operation.in_[0])
            rhs_part = ",".join(process_operand(op) for op in operation.in_[1])
            cond = f"({lhs_part} IN ({rhs_part}))"
        elif isinstance(operation, tsi_query.ContainsOperation):
            lhs_part = process_operand(operation.contains_.input)
            rhs_part = process_operand(operation.contains_.substr)
            position_operation = "position"
            if operation.contains_.case_insensitive:
                position_operation = "positionCaseInsensitive"
            cond = f"{position_operation}({lhs_part}, {rhs_part}) > 0"
        else:
            raise TypeError(f"Unknown operation type: {operation}")

        return cond

    def process_operand(operand: "tsi_query.Operand") -> str:
        if isinstance(operand, tsi_query.LiteralOperation):
            return param_slot(
                param_builder.add_param(operand.literal_),  # type: ignore
                python_value_to_ch_type(operand.literal_),
            )
        elif isinstance(operand, tsi_query.GetFieldOperator):
            if operand.get_field_ in DISALLOWED_FILTERING_FIELDS:
                raise InvalidFieldError(f"Field {operand.get_field_} is not allowed")

            structured_field = get_field_by_name(operand.get_field_)

            if isinstance(
                structured_field,
                (
                    CallsMergedDynamicField,
                    CallsMergedAggField,
                    CallsMergedFeedbackPayloadField,
                    CallsMergedSummaryField,
                    CallsMergedQueueItemField,
                ),
            ):
                field = structured_field.as_sql(
                    param_builder, table_alias, use_agg_fn=use_agg_fn
                )
            else:
                field = structured_field.as_sql(param_builder, table_alias)
            raw_fields_used[structured_field.field] = structured_field
            return field
        elif isinstance(operand, tsi_query.ConvertOperation):
            field = process_operand(operand.convert_.input)
            return clickhouse_cast(field, operand.convert_.to)
        elif isinstance(
            operand,
            (
                tsi_query.AndOperation,
                tsi_query.OrOperation,
                tsi_query.NotOperation,
                tsi_query.EqOperation,
                tsi_query.GtOperation,
                tsi_query.LtOperation,
                tsi_query.GteOperation,
                tsi_query.LteOperation,
                tsi_query.InOperation,
                tsi_query.ContainsOperation,
            ),
        ):
            return process_operation(operand)
        else:
            raise TypeError(f"Unknown operand type: {operand}")

    filter_cond = process_operation(query.expr_)

    conditions.append(filter_cond)

    return FilterToConditions(
        conditions=conditions, fields_used=list(raw_fields_used.values())
    )


def process_op_name_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Pulls out the op_name and returns a sql string if there are any op_names."""
    if hardcoded_filter is None or not hardcoded_filter.filter.op_names:
        return ""

    op_names = hardcoded_filter.filter.op_names

    assert_parameter_length_less_than_max("op_names", len(op_names))

    # We will build up (0 or 1) + N conditions for the op_version_refs
    # If there are any non-wildcarded names, then we at least have an IN condition
    # If there are any wildcarded names, then we have a LIKE condition for each
    or_conditions: list[str] = []
    non_wildcarded_names: list[str] = []
    wildcarded_names: list[str] = []

    op_field = get_field_by_name("op_name")
    if not isinstance(op_field, CallsMergedAggField):
        raise TypeError("op_name is not an aggregate field")

    op_field_sql = op_field.as_sql(param_builder, table_alias, use_agg_fn=False)
    for name in op_names:
        if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
            wildcarded_names.append(name)
        else:
            non_wildcarded_names.append(name)

    if non_wildcarded_names:
        or_conditions.append(
            f"{op_field_sql} IN {param_slot(param_builder.add_param(non_wildcarded_names), 'Array(String)')}"
        )

    for name in wildcarded_names:
        like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + ":%"
        or_conditions.append(
            f"{op_field_sql} LIKE {param_slot(param_builder.add_param(like_name), 'String')}"
        )

    if not or_conditions:
        return ""

    # Account for unmerged call parts by including null op_name (call ends)
    or_conditions += [f"{op_field_sql} IS NULL"]

    return " AND " + combine_conditions(or_conditions, "OR")


def process_trace_id_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Pulls out the trace_id and returns a sql string if there are any trace_ids."""
    if hardcoded_filter is None or not hardcoded_filter.filter.trace_ids:
        return ""

    trace_ids = hardcoded_filter.filter.trace_ids

    assert_parameter_length_less_than_max("trace_ids", len(trace_ids))

    trace_id_field = get_field_by_name("trace_id")
    if not isinstance(trace_id_field, CallsMergedAggField):
        raise TypeError("trace_id is not an aggregate field")
    trace_id_field_sql = trace_id_field.as_sql(
        param_builder, table_alias, use_agg_fn=False
    )

    # If there's only one trace_id, use an equality condition for performance
    if len(trace_ids) == 1:
        trace_cond = f"{trace_id_field_sql} = {param_slot(param_builder.add_param(trace_ids[0]), 'String')}"
    elif len(trace_ids) > 1:
        trace_cond = f"{trace_id_field_sql} IN {param_slot(param_builder.add_param(trace_ids), 'Array(String)')}"
    else:
        return ""

    return f" AND ({trace_cond} OR {trace_id_field_sql} IS NULL)"


def process_thread_id_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Pulls out the thread_id and returns a sql string if there are any thread_ids."""
    if (
        hardcoded_filter is None
        or hardcoded_filter.filter.thread_ids is None
        or len(hardcoded_filter.filter.thread_ids) == 0
    ):
        return ""

    thread_ids = hardcoded_filter.filter.thread_ids

    assert_parameter_length_less_than_max("thread_ids", len(thread_ids))

    thread_id_field = get_field_by_name("thread_id")
    if not isinstance(thread_id_field, CallsMergedAggField):
        raise TypeError("thread_id is not an aggregate field")
    thread_id_field_sql = thread_id_field.as_sql(
        param_builder, table_alias, use_agg_fn=False
    )

    # If there's only one thread_id, use an equality condition for performance
    if len(thread_ids) == 1:
        thread_cond = f"{thread_id_field_sql} = {param_slot(param_builder.add_param(thread_ids[0]), 'String')}"
    elif len(thread_ids) > 1:
        thread_cond = f"{thread_id_field_sql} IN {param_slot(param_builder.add_param(thread_ids), 'Array(String)')}"
    else:
        return ""

    return f" AND ({thread_cond} OR {thread_id_field_sql} IS NULL)"


def process_turn_id_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Pulls out the turn_id and returns a sql string if there are any turn_ids."""
    if (
        hardcoded_filter is None
        or hardcoded_filter.filter.turn_ids is None
        or len(hardcoded_filter.filter.turn_ids) == 0
    ):
        return ""

    turn_ids = hardcoded_filter.filter.turn_ids

    assert_parameter_length_less_than_max("turn_ids", len(turn_ids))

    turn_id_field = get_field_by_name("turn_id")
    if not isinstance(turn_id_field, CallsMergedAggField):
        raise TypeError("turn_id is not an aggregate field")
    turn_id_field_sql = turn_id_field.as_sql(
        param_builder, table_alias, use_agg_fn=False
    )

    # If there's only one turn_id, use an equality condition for performance
    if len(turn_ids) == 1:
        turn_cond = f"{turn_id_field_sql} = {param_slot(param_builder.add_param(turn_ids[0]), 'String')}"
    elif len(turn_ids) > 1:
        turn_cond = f"{turn_id_field_sql} IN {param_slot(param_builder.add_param(turn_ids), 'Array(String)')}"
    else:
        return ""

    return f" AND ({turn_cond} OR {turn_id_field_sql} IS NULL)"


def process_trace_roots_only_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Pulls out the trace_roots_only and returns a sql string if there are any trace_roots_only."""
    if hardcoded_filter is None or not hardcoded_filter.filter.trace_roots_only:
        return ""

    parent_id_field = get_field_by_name("parent_id")
    if not isinstance(parent_id_field, CallsMergedAggField):
        raise TypeError("parent_id is not an aggregate field")

    parent_id_field_sql = parent_id_field.as_sql(
        param_builder, table_alias, use_agg_fn=False
    )

    return f"AND ({parent_id_field_sql} IS NULL)"


def process_parent_ids_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Pulls out the parent_id and returns a sql string if there are any parent_ids."""
    if hardcoded_filter is None or not hardcoded_filter.filter.parent_ids:
        return ""

    parent_id_field = get_field_by_name("parent_id")
    if not isinstance(parent_id_field, CallsMergedAggField):
        raise TypeError("parent_id is not an aggregate field")

    parent_id_field_sql = parent_id_field.as_sql(
        param_builder, table_alias, use_agg_fn=False
    )

    parent_ids_sql = f"{parent_id_field_sql} IN {param_slot(param_builder.add_param(hardcoded_filter.filter.parent_ids), 'Array(String)')}"

    return f"AND ({parent_ids_sql} OR {parent_id_field_sql} IS NULL)"


def process_ref_filters_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Adds a ref filter optimization to the query.

    To be used before group by. This filter is NOT guaranteed to return
    the correct results, as it can operate on call ends (output_refs) so it
    should be used in addition to the existing ref filters after group by
    generated in process_calls_filter_to_conditions.
    """
    if hardcoded_filter is None or (
        not hardcoded_filter.filter.output_refs
        and not hardcoded_filter.filter.input_refs
    ):
        return ""

    def process_ref_filter(field_name: str, refs: list[str]) -> str:
        field = get_field_by_name(field_name)
        if not isinstance(field, CallsMergedAggField):
            raise TypeError(f"{field_name} is not an aggregate field")

        field_sql = field.as_sql(param_builder, table_alias, use_agg_fn=False)
        param = param_builder.add_param(refs)
        ref_filter_sql = f"hasAny({field_sql}, {param_slot(param, 'Array(String)')})"
        return f"{ref_filter_sql} OR length({field_sql}) = 0"

    ref_filters = []
    if hardcoded_filter.filter.input_refs:
        ref_filters.append(
            process_ref_filter("input_refs", hardcoded_filter.filter.input_refs)
        )
    if hardcoded_filter.filter.output_refs:
        ref_filters.append(
            process_ref_filter("output_refs", hardcoded_filter.filter.output_refs)
        )

    if not ref_filters:
        return ""

    return " AND (" + combine_conditions(ref_filters, "AND") + ")"


def process_object_refs_filter_to_opt_sql(
    param_builder: ParamBuilder,
    table_alias: str,
    object_ref_fields_consumed: set[str],
) -> str:
    """Processes object ref fields to an optimization sql string."""
    if not object_ref_fields_consumed:
        return ""

    # Optimization for filtering with refs, only include calls that have non-zero
    # input refs when we are conditioning on refs in inputs, or is a naked call end.
    refs_filter_opt_sql = ""
    if "inputs_dump" in object_ref_fields_consumed:
        refs_filter_opt_sql += f"AND (length({table_alias}.input_refs) > 0 OR {table_alias}.started_at IS NULL)"
    # If we are conditioning on output refs, filter down calls to those with non-zero
    # output refs, or they are a naked call start.
    if "output_dump" in object_ref_fields_consumed:
        refs_filter_opt_sql += f"AND (length({table_alias}.output_refs) > 0 OR {table_alias}.ended_at IS NULL)"

    return refs_filter_opt_sql


def process_wb_run_ids_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
) -> str:
    """Pulls out the wb_run_id and returns a sql string if there are any wb_run_ids."""
    if hardcoded_filter is None or not hardcoded_filter.filter.wb_run_ids:
        return ""

    wb_run_ids = hardcoded_filter.filter.wb_run_ids
    assert_parameter_length_less_than_max("wb_run_ids", len(wb_run_ids))
    wb_run_id_field = get_field_by_name("wb_run_id")
    if not isinstance(wb_run_id_field, CallsMergedAggField):
        raise TypeError("wb_run_id is not an aggregate field")

    wb_run_id_field_sql = wb_run_id_field.as_sql(
        param_builder, table_alias, use_agg_fn=False
    )
    wb_run_id_filter_sql = f"{wb_run_id_field_sql} IN {param_slot(param_builder.add_param(wb_run_ids), 'Array(String)')}"

    return f"AND ({wb_run_id_filter_sql} OR {wb_run_id_field_sql} IS NULL)"


def process_calls_filter_to_conditions(
    filter: tsi.CallsFilter,
    param_builder: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
) -> list[str]:
    """Converts a CallsFilter to a list of conditions for a clickhouse query.

    Excludes the op_name, which is handled separately.

    Args:
        filter: The CallsFilter to convert
        param_builder: Parameter builder for query parameterization
        table_alias: The table alias to use in SQL
        use_agg_fn: Whether to wrap fields in aggregate functions (True for calls_merged)
    """
    conditions: list[str] = []

    def get_field_sql(field_name: str) -> str:
        """Get SQL for a field, conditionally applying aggregation."""
        field = get_field_by_name(field_name)
        if isinstance(field, CallsMergedAggField):
            return field.as_sql(param_builder, table_alias, use_agg_fn=use_agg_fn)
        return field.as_sql(param_builder, table_alias)

    # technically not required, as we are now doing a pre-groupby optimization
    # that should filter out 100% of non-matching rows. However, we can't remove
    # the output_refs, so lets keep both for clarity
    if filter.input_refs:
        assert_parameter_length_less_than_max("input_refs", len(filter.input_refs))
        conditions.append(
            f"hasAny({get_field_sql('input_refs')}, {param_slot(param_builder.add_param(filter.input_refs), 'Array(String)')})"
        )

    if filter.output_refs:
        assert_parameter_length_less_than_max("output_refs", len(filter.output_refs))
        conditions.append(
            f"hasAny({get_field_sql('output_refs')}, {param_slot(param_builder.add_param(filter.output_refs), 'Array(String)')})"
        )

    if filter.parent_ids:
        assert_parameter_length_less_than_max("parent_ids", len(filter.parent_ids))
        conditions.append(
            f"{get_field_sql('parent_id')} IN {param_slot(param_builder.add_param(filter.parent_ids), 'Array(String)')}"
        )

    if filter.call_ids:
        assert_parameter_length_less_than_max("call_ids", len(filter.call_ids))
        conditions.append(
            f"{get_field_sql('id')} IN {param_slot(param_builder.add_param(filter.call_ids), 'Array(String)')}"
        )

    if filter.thread_ids is not None:
        assert_parameter_length_less_than_max("thread_ids", len(filter.thread_ids))
        conditions.append(
            f"{get_field_sql('thread_id')} IN {param_slot(param_builder.add_param(filter.thread_ids), 'Array(String)')}"
        )

    if filter.turn_ids is not None:
        assert_parameter_length_less_than_max("turn_ids", len(filter.turn_ids))
        conditions.append(
            f"{get_field_sql('turn_id')} IN {param_slot(param_builder.add_param(filter.turn_ids), 'Array(String)')}"
        )

    if filter.wb_user_ids:
        conditions.append(
            f"{get_field_sql('wb_user_id')} IN {param_slot(param_builder.add_param(filter.wb_user_ids), 'Array(String)')}"
        )

    if filter.wb_run_ids:
        conditions.append(
            f"{get_field_sql('wb_run_id')} IN {param_slot(param_builder.add_param(filter.wb_run_ids), 'Array(String)')}"
        )

    return conditions


######### STATS QUERY HANDLING ##########


def build_calls_stats_query(
    req: tsi.CallsQueryStatsReq,
    param_builder: ParamBuilder,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> tuple[str, KeysView[str]]:
    """Build a stats query for calls, automatically using optimized queries when possible.

    This function handles both optimized special-case queries and the general case.
    Returns a tuple of (query_sql, column_names).

    Args:
        req: The stats query request
        param_builder: Parameter builder for query parameterization
        read_table: Which calls table to read from

    Returns:
        Tuple of (SQL query string, column names in the result)
    """
    aggregated_columns = {"count": "count()"}

    # Try optimized special case queries first
    if opt_query := _try_optimized_stats_query(req, param_builder, read_table):
        return (opt_query, aggregated_columns.keys())

    # Fall back to general query builder
    cq = CallsQuery(
        project_id=req.project_id,
        include_total_storage_size=req.include_total_storage_size or False,
        read_table=read_table,
    )

    cq.add_field("id")
    if req.filter is not None:
        cq.set_hardcoded_filter(HardCodedFilter(filter=req.filter))
    if req.query is not None:
        cq.add_condition(req.query.expr_)
    if req.limit is not None:
        cq.set_limit(req.limit)
    if req.expand_columns is not None:
        cq.set_expand_columns(req.expand_columns)

    if req.include_total_storage_size:
        aggregated_columns["total_storage_size_bytes"] = (
            "sum(coalesce(total_storage_size_bytes, 0))"
        )
        cq.add_field("total_storage_size_bytes")

    inner_query = cq.as_sql(param_builder)
    calls_query_sql = f"SELECT {', '.join(aggregated_columns[k] for k in aggregated_columns)} FROM ({inner_query})"

    return (calls_query_sql, aggregated_columns.keys())


def _try_optimized_stats_query(
    req: tsi.CallsQueryStatsReq,
    param_builder: ParamBuilder,
    read_table: ReadTable,
) -> str | None:
    """Try to match request to an optimized special-case query.

    Returns optimized query string if a pattern matches, None otherwise.
    Add new patterns here for common hot-path queries.
    """
    # Pattern 1: Simple existence check (limit=1, no filters)
    if (
        req.limit == 1
        and req.filter is None
        and req.query is None
        and not req.include_total_storage_size
    ):
        return _optimized_project_contains_call_query(
            req.project_id, param_builder, read_table
        )

    # Pattern 2: Query with wb_run_id check (limit=1, query present, minimal filter)
    # Covers common case: checking for runs with wb_run_id not null
    if (
        req.limit == 1
        and req.query is not None
        and not req.include_total_storage_size
        and _is_minimal_filter(req.filter)
    ):
        return _optimized_wb_run_id_not_null_query(
            req.project_id, param_builder, read_table
        )

    return None


def _optimized_project_contains_call_query(
    project_id: str,
    param_builder: ParamBuilder,
    read_table: ReadTable,
) -> str:
    """Returns a query that checks if the project contains any calls."""
    table_name = get_calls_table_name(read_table)
    return safely_format_sql(
        f"""SELECT
    toUInt8(count()) AS has_any
    FROM
    (
        SELECT 1
        FROM {table_name}
        WHERE project_id = {param_slot(param_builder.add_param(project_id), "String")}
        LIMIT 1
    )
    """,
        logger,
    )


def _optimized_wb_run_id_not_null_query(
    project_id: str,
    param_builder: ParamBuilder,
    read_table: ReadTable,
) -> str:
    """Optimized query for checking existence of calls with wb_run_id not null.

    Uses WHERE clause instead of HAVING to avoid expensive aggregation.
    """
    project_id_param = param_builder.add_param(project_id)
    table_name = get_calls_table_name(read_table)
    return f"""
        SELECT count() FROM (
            SELECT {table_name}.id AS id
            FROM {table_name}
            WHERE {table_name}.project_id = {param_slot(project_id_param, "String")}
                AND {table_name}.wb_run_id IS NOT NULL
                AND {table_name}.deleted_at IS NULL
            LIMIT 1
        )
    """


def _is_minimal_filter(filter: tsi.CallsFilter | None) -> bool:
    """Check if filter has no specific filtering criteria set."""
    if filter is None:
        return True
    return (
        filter.wb_run_ids is None
        and filter.wb_user_ids is None
        and filter.op_names is None
        and filter.call_ids is None
        and filter.trace_ids is None
        and filter.parent_ids is None
        and filter.trace_roots_only is None
        and filter.input_refs is None
        and filter.output_refs is None
        and filter.thread_ids is None
        and filter.turn_ids is None
    )


def _format_table_name_with_cluster(table_name: str, cluster_name: str | None) -> str:
    """Format a table name with ON CLUSTER clause if cluster_name is provided.

    In distributed mode, mutations (UPDATE, DELETE, etc.) must target the local
    table with the ON CLUSTER clause to execute across all cluster nodes.
    """
    if cluster_name:
        return f"{table_name}{LOCAL_TABLE_SUFFIX} ON CLUSTER {cluster_name}"
    return table_name


def build_calls_complete_update_end_query(
    table_name: str,
    project_id_param: str,
    id_param: str,
    ended_at_param: str,
    exception_param: str,
    output_dump_param: str,
    summary_dump_param: str,
    output_refs_param: str,
    wb_run_step_end_param: str,
    started_at_param: str | None = None,
    cluster_name: str | None = None,
) -> str:
    """Build the calls_complete UPDATE query for call end data.

    Args:
        table_name (str): The calls_complete table name.
        project_id_param (str): Param slot key for project_id.
        id_param (str): Param slot key for call id.
        ended_at_param (str): Param slot key for ended_at (Int64 microseconds).
        exception_param (str): Param slot key for exception.
        output_dump_param (str): Param slot key for output_dump.
        summary_dump_param (str): Param slot key for summary_dump.
        output_refs_param (str): Param slot key for output_refs.
        wb_run_step_end_param (str): Param slot key for wb_run_step_end.
        started_at_param (str | None): Optional param slot key for started_at
            (Int64 microseconds). When provided, enables more efficient queries
            by utilizing the ClickHouse primary key (project_id, started_at, id).
        cluster_name (str | None): Optional ClickHouse cluster name for ON CLUSTER
            clause in distributed mode. When provided, the UPDATE will be executed
            across all cluster nodes.

    Returns:
        str: The formatted ClickHouse UPDATE statement.

    Note:
        started_at and ended_at params are passed as Int64 microseconds since epoch
        because clickhouse-connect truncates datetime objects to whole seconds.
        We use fromUnixTimestamp64Micro() to convert back to DateTime64(6).
    """
    # Build WHERE clause - include started_at if provided for better primary key usage
    where_clauses = [f"project_id = {{{project_id_param}:String}}"]
    if started_at_param is not None:
        where_clauses.append(
            f"started_at = fromUnixTimestamp64Micro({{{started_at_param}:Int64}}, 'UTC')"
        )
    else:
        # TODO: try to optimistically parse uuidv7, grabbing timestamps from the ID
        # then use that to narrow the granules we need to search.
        pass

    where_clauses.append(f"id = {{{id_param}:String}}")
    where_clause = " AND ".join(where_clauses)

    # Format table name with ON CLUSTER if cluster_name is provided
    formatted_table = _format_table_name_with_cluster(table_name, cluster_name)

    # Use fromUnixTimestamp64Micro to convert Int64 microseconds to DateTime64(6)
    # This preserves full microsecond precision that would be lost with datetime params
    return f"""
        UPDATE {formatted_table}
        SET
            ended_at = fromUnixTimestamp64Micro({{{ended_at_param}:Int64}}, 'UTC'),
            exception = {{{exception_param}:Nullable(String)}},
            output_dump = {{{output_dump_param}:String}},
            summary_dump = {{{summary_dump_param}:String}},
            output_refs = {{{output_refs_param}:Array(String)}},
            wb_run_step_end = {{{wb_run_step_end_param}:Nullable(UInt64)}},
            updated_at = now64(3)
        WHERE {where_clause}
        """


def build_calls_complete_delete_query(
    table_name: str,
    project_id_param: str,
    call_ids_param: str,
    cluster_name: str | None = None,
) -> str:
    """Build the calls_complete DELETE query for call end data."""
    formatted_table = _format_table_name_with_cluster(table_name, cluster_name)
    raw_sql = f"""
        DELETE FROM {formatted_table}
        WHERE project_id = {{{project_id_param}:String}} AND id IN {{{call_ids_param}:Array(String)}}
        """
    return safely_format_sql(raw_sql, logger)


def build_calls_complete_update_query(
    table_name: str,
    project_id_param: str,
    id_param: str,
    display_name_param: str,
    cluster_name: str | None = None,
) -> str:
    """Build the calls_complete UPDATE query for call end data."""
    formatted_table = _format_table_name_with_cluster(table_name, cluster_name)
    raw_sql = f"""
        UPDATE {formatted_table}
        SET display_name = {{{display_name_param}:String}}
        WHERE project_id = {{{project_id_param}:String}} AND id = {{{id_param}:String}}
        """
    return safely_format_sql(raw_sql, logger)
