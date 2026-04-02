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
from typing import Literal, NamedTuple, cast

from pydantic import BaseModel, Field

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.conditions import (
    process_query_to_conditions,
)
from weave.trace_server.calls_query_builder.cte import CTECollection
from weave.trace_server.calls_query_builder.fields import (
    DISALLOWED_FILTERING_FIELDS,
    ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME,
    STORAGE_SIZE_TABLE_NAME,
    CallsMergedAggField,
    CallsMergedDynamicField,
    CallsMergedFeedbackPayloadField,
    CallsMergedField,
    CallsMergedQueueItemField,
    CallsMergedSummaryField,
    QueryBuilderDynamicField,
    QueryBuilderField,
    get_calls_table_name,
    get_field_by_name,
    maybe_agg,
)
from weave.trace_server.calls_query_builder.hardcoded_filters import (
    HardCodedFilter,
    process_object_refs_filter_to_opt_sql,
    process_op_name_filter_to_sql,
    process_parent_ids_filter_to_sql,
    process_ref_filters_to_sql,
    process_thread_id_filter_to_sql,
    process_trace_id_filter_to_sql,
    process_trace_roots_only_filter_to_sql,
    process_turn_id_filter_to_sql,
    process_wb_run_ids_filter_to_sql,
)
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
    param_slot,
    safely_format_sql,
)
from weave.trace_server.common_interface import SortBy
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    combine_conditions,
)
from weave.trace_server.project_version.types import ReadTable, TableConfig
from weave.trace_server.token_costs import build_cost_ctes, get_cost_final_select
from weave.trace_server.trace_server_common import assert_parameter_length_less_than_max

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
    children_of_eval_ids: str = ""
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
            self.children_of_eval_ids,
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
        read_table: "ReadTable" = ReadTable.CALLS_MERGED,
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
        return self._build_standard_order_sql(
            pb, table_alias, options, use_agg_fn, read_table
        )

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
        read_table: "ReadTable" = ReadTable.CALLS_MERGED,
    ) -> str:
        """Build ORDER BY SQL for standard fields."""
        parts = []
        for cast_to, direction in options:
            if isinstance(self.field, CallsMergedSummaryField):
                field_sql = self.field.as_sql(
                    pb,
                    table_alias,
                    cast_to,
                    use_agg_fn=use_agg_fn,
                    read_table=read_table,
                )
            elif isinstance(
                self.field,
                (
                    CallsMergedAggField,
                    CallsMergedFeedbackPayloadField,
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
        read_table: "ReadTable" = ReadTable.CALLS_MERGED,
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
            read_table=read_table,
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
    eval_root_ids: list[str] | None = None

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
        if direction not in {"ASC", "DESC"}:
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

    def _ensure_order_fields_selected(
        self, select_fields: list["CallsMergedField"]
    ) -> None:
        """Ensure all order-by fields are in select_fields for cost queries.

        When costs are included, the final cost SELECT/GROUP BY/ORDER BY
        references column aliases from the all_calls CTE. If an order field
        isn't selected there, ClickHouse raises UNKNOWN_IDENTIFIER.
        """
        for order_field in self.order_fields:
            field_obj = order_field.field
            # Skip feedback fields - they're handled via LEFT JOIN
            if isinstance(field_obj, CallsMergedFeedbackPayloadField):
                continue

            if isinstance(
                field_obj,
                (CallsMergedDynamicField, QueryBuilderDynamicField),
            ):
                # Add the base field, not the dynamic path.
                base_field = get_field_by_name(field_obj.field)
                if base_field not in select_fields:
                    select_fields.append(base_field)
            elif field_obj not in select_fields:
                assert isinstance(field_obj, CallsMergedField), (
                    "Field must be a CallsMergedField"
                )
                select_fields.append(field_obj)

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

        # Determine if we should use the two-step filtered_calls CTE pattern.
        # Only relevant for calls_merged (where GROUP BY makes the two-pass
        # approach worthwhile). For calls_complete, we always use single-pass.
        should_optimize = self._should_optimize()

        # Important: Always inject deleted_at into the query.
        # We use None as the literal for both table types. The sentinel handling
        # in process_operation converts None to the correct sentinel value with
        # proper DateTime64(3) typing for calls_complete, or IS NULL for calls_merged.
        self.add_condition(
            tsi_query.EqOperation.model_validate(
                {"$eq": [{"$getField": "deleted_at"}, {"$literal": None}]}
            )
        )

        # For calls_merged: filter out orphaned call ends (started_at IS NULL).
        # This can occur with out-of-order call part insertion or early client
        # termination.  Also REQUIRED for proper pre-GROUP BY (WHERE) optimizations.
        # For calls_complete: every row has a non-nullable started_at, so this
        # condition is always true -- skip it to avoid dead SQL.
        if self.read_table == ReadTable.CALLS_MERGED:
            self.add_condition(
                tsi_query.NotOperation.model_validate(
                    {
                        "$not": [
                            {
                                "$eq": [
                                    {"$getField": "started_at"},
                                    {"$literal": None},
                                ]
                            }
                        ]
                    }
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

        # Use the filtered_calls CTE (two-pass) pattern only for calls_merged
        # where it reduces rows before expensive GROUP BY aggregation.
        # For calls_complete (one row per call, no GROUP BY), always use a
        # single-pass query — it's both simpler and significantly faster.
        use_filter_cte = self.read_table != ReadTable.CALLS_COMPLETE and (
            should_optimize or self.include_costs or bool(object_ref_conditions)
        )

        ctes, field_to_object_join_alias_map = build_object_ref_ctes(
            pb, self.project_id, object_ref_conditions
        )

        if use_filter_cte:
            # Build two queries: a filter CTE that narrows rows by light
            # conditions first, then a select query that loads heavy columns
            # only for the matched ids.
            filter_query = CallsQuery(
                project_id=self.project_id, read_table=self.read_table
            )
            select_query = CallsQuery(
                project_id=self.project_id,
                include_storage_size=self.include_storage_size,
                include_total_storage_size=self.include_total_storage_size,
                read_table=self.read_table,
            )

            filter_query.add_field("id")
            for field in self.select_fields:
                select_query.select_fields.append(field)

            for condition in self.query_conditions:
                filter_query.query_conditions.append(condition)

            filter_query.hardcoded_filter = self.hardcoded_filter
            filter_query.order_fields = self.order_fields
            filter_query.limit = self.limit
            filter_query.offset = self.offset
            # SUPER IMPORTANT: still need to re-sort the final query
            select_query.order_fields = self.order_fields

            # When using the CTE pattern with costs, ensure all fields used in
            # ordering are selected in select_query so they're available in the
            # final query's ORDER BY.
            if self.include_costs:
                self._ensure_order_fields_selected(select_query.select_fields)

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
        else:
            # Single-pass: the full query (with all filters, ordering, and
            # limit) is built directly — no filtered_calls CTE needed.
            #
            # When costs are included, ensure all fields used in ordering are
            # selected so they're available in the cost query's final
            # SELECT/GROUP BY/ORDER BY (same logic as the filter-CTE branch).
            if self.include_costs:
                self._ensure_order_fields_selected(self.select_fields)

            base_sql = self._as_sql_base_format(
                pb,
                table_alias_resolved,
                field_to_object_join_alias_map=field_to_object_join_alias_map,
                expand_columns=self.expand_columns,
            )

        if not self.include_costs:
            if ctes.has_ctes():
                raw_sql = ctes.to_sql() + "\n" + base_sql
                return safely_format_sql(raw_sql, logger)
            return base_sql

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
        children_of_eval_ids = process_children_of_eval_ids_to_sql(
            self.eval_root_ids, pb, table_alias, self.project_id, self.read_table
        )
        thread_id = process_thread_id_filter_to_sql(
            self.hardcoded_filter, pb, table_alias, self.read_table
        )
        turn_id = process_turn_id_filter_to_sql(
            self.hardcoded_filter, pb, table_alias, self.read_table
        )
        wb_run_id = process_wb_run_ids_filter_to_sql(
            self.hardcoded_filter, pb, table_alias, self.read_table
        )
        ref_filter = process_ref_filters_to_sql(self.hardcoded_filter, pb, table_alias)
        trace_roots_only = process_trace_roots_only_filter_to_sql(
            self.hardcoded_filter, pb, table_alias, self.read_table
        )
        parent_ids = process_parent_ids_filter_to_sql(
            self.hardcoded_filter, pb, table_alias, self.read_table
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
            elif condition._consumed_fields is not None:
                object_ref_fields_consumed.update(
                    f.field for f in condition._consumed_fields
                )

        optimization_conditions = process_query_to_optimization_sql(
            non_object_ref_conditions, pb, table_alias, self.read_table
        )
        sortable_datetime = optimization_conditions.sortable_datetime_filters_sql or ""
        heavy_filter = optimization_conditions.heavy_filter_opt_sql or ""

        object_refs = process_object_refs_filter_to_opt_sql(
            pb, table_alias, object_ref_fields_consumed, self.read_table
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
            children_of_eval_ids=children_of_eval_ids,
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
        id_subquery_name: str | None = None,
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
            # When we have a filtered set of call IDs, restrict the trace_ids
            # looked up in calls_merged_stats to only those related to the
            # filtered calls. This leverages the primary key index to avoid
            # aggregating over the entire project when only a subset is needed.
            trace_id_filter = ""
            if id_subquery_name is not None:
                trace_id_filter = f"""AND trace_id IN (
                    SELECT trace_id
                    FROM {table_alias}
                    WHERE project_id = {param_slot(project_param, "String")}
                    AND id IN {id_subquery_name}
                )"""
            total_storage_size_join = f"""
            LEFT JOIN (
                SELECT
                    trace_id,
                    sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) AS total_storage_size_bytes
                FROM {config.stats_table_name}
                WHERE project_id = {param_slot(project_param, "String")}
                {trace_id_filter}
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
                    read_table=self.read_table,
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
                    pb,
                    table_alias,
                    use_agg_fn=self.use_agg_fn,
                    read_table=self.read_table,
                )
            )

        filter_sql = ""
        if len(filter_conditions_sql) > 0:
            # For calls_complete, these become WHERE conditions (no GROUP BY)
            # For calls_merged, these are HAVING conditions (after GROUP BY)
            prefix = "HAVING " if self.read_table == ReadTable.CALLS_MERGED else "AND "
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
                    read_table=self.read_table,
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

    def _build_query_body(
        self,
        pb: ParamBuilder,
        table_alias: str,
        id_subquery_name: str | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        expand_columns: list[str] | None = None,
    ) -> str:
        """Build the SQL query body: everything from FROM through OFFSET.

        This method builds filters, JOINs, WHERE/PREWHERE, GROUP BY, ORDER BY,
        LIMIT, and OFFSET — everything except the SELECT clause. Callers compose
        their own SELECT with the returned body to form a complete query.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL (typically "calls_merged")
            id_subquery_name: Optional name of a CTE containing filtered IDs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases for object refs
            expand_columns: List of columns that should be expanded for object refs

        Returns:
            SQL query body string (FROM through OFFSET, not formatted)
        """
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
            id_subquery_name=id_subquery_name,
        )
        group_by_sql = ""
        if self.read_table == ReadTable.CALLS_MERGED:
            group_by_sql = f"GROUP BY ({table_alias}.project_id, {table_alias}.id)"

        # Use PREWHERE for project_id to filter data before reading from disk
        # This is a ClickHouse optimization for high-selectivity filters
        where_filters_sql = where_filters.to_sql()
        # Strip leading "AND " from where_filters since PREWHERE handles the first condition
        where_filters_stripped = re.sub(r"^\s*AND\s+", "", where_filters_sql)
        where_clause = (
            f"WHERE {where_filters_stripped}" if where_filters_stripped else ""
        )

        # Fix where_clause when empty but we have filter_sql
        # For calls_complete, filter_sql starts with "AND "
        # If where_clause is empty, set it to "WHERE 1" so filter_sql can append naturally
        # TODO: optimize it further to make this condition builder smarter
        if (
            not where_clause
            and filter_result.filter_sql
            and self.read_table == ReadTable.CALLS_COMPLETE
        ):
            where_clause = "WHERE 1"

        return f"""FROM {table_alias}
        {joins.to_sql()}
        PREWHERE {table_alias}.project_id = {param_slot(project_param, "String")}
        {where_clause}
        {group_by_sql}
        {filter_result.filter_sql}
        {order_result.order_by_sql}
        {order_result.limit_sql}
        {order_result.offset_sql}"""

    def _as_sql_base_format(
        self,
        pb: ParamBuilder,
        table_alias: str,
        id_subquery_name: str | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        expand_columns: list[str] | None = None,
    ) -> str:
        """Build the base SQL query format.

        Computes the SELECT clause from select_fields and combines it with
        the query body built by _build_query_body.

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
            field.as_select_sql(
                pb, table_alias, use_agg_fn=self.use_agg_fn, read_table=self.read_table
            )
            for field in self.select_fields
        )
        body = self._build_query_body(
            pb,
            table_alias,
            id_subquery_name,
            field_to_object_join_alias_map,
            expand_columns,
        )
        raw_sql = f"""
        SELECT {select_fields_sql}
        {body}
        """
        return safely_format_sql(raw_sql, logger)


def process_children_of_eval_ids_to_sql(
    eval_root_ids: list[str] | None,
    param_builder: ParamBuilder,
    table_alias: str,
    project_id: str = "",
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> str:
    """Fetch direct children of eval root IDs and their children for the eval results dataset."""
    if not eval_root_ids:
        return ""
    assert_parameter_length_less_than_max("eval_root_ids", len(eval_root_ids))

    parent_id_field = get_field_by_name("parent_id")
    if not isinstance(parent_id_field, CallsMergedAggField):
        raise TypeError("parent_id is not an aggregate field")
    parent_id_field_sql = parent_id_field.as_sql(
        param_builder, table_alias, use_agg_fn=False
    )

    eval_root_ids_param = param_slot(
        param_builder.add_param(eval_root_ids), "Array(String)"
    )

    # we generate a nested CallsQuery to find all instances of the PredictandScore calls
    # that are children of the eval root IDs. this is then used as a WHERE clause
    # in the outer query to return both the PredictandScore calls and their children (scorers/predict calls).
    eval_root_children_cq = CallsQuery(project_id=project_id, read_table=read_table)
    eval_root_children_cq.add_field("id")
    eval_root_children_cq.set_hardcoded_filter(
        HardCodedFilter(filter=tsi.CallsFilter(parent_ids=eval_root_ids))
    )
    eval_root_children_subquery = eval_root_children_cq.as_sql(param_builder)

    # for the calls-merged table, each call is stored as split start/end rows.
    # end-rows have parent_id as NULL, so we need to do this.
    parent_id_conditions = (
        f"{parent_id_field_sql} IN {eval_root_ids_param}"
        f" OR {parent_id_field_sql} IN ({eval_root_children_subquery})"
    )
    if read_table == ReadTable.CALLS_MERGED:
        parent_null = parent_id_field.null_check_sql(
            param_builder, table_alias, read_table, use_agg_fn=False
        )
        parent_id_conditions += f" OR {parent_null}"

    return (
        f" AND ({parent_id_conditions})"
        f" AND {table_alias}.id NOT IN {eval_root_ids_param}"
    )
