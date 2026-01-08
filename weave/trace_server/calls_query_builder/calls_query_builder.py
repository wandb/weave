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

import datetime
import json
import logging
import re
from collections import defaultdict
from collections.abc import Callable, KeysView
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.cte import CTECollection
from weave.trace_server.calls_query_builder.field_factory import (
    QueryFieldType,
    get_field_by_name_strategy,
)
from weave.trace_server.calls_query_builder.fields import (
    DynamicField,
    FeedbackField,
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
from weave.trace_server.calls_query_builder.table_strategy import (
    TableStrategy,
    get_table_strategy,
)
from weave.trace_server.calls_query_builder.utils import (
    param_slot,
    safely_format_sql,
)
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    combine_conditions,
    python_value_to_ch_type,
)
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.token_costs import build_cost_ctes, get_cost_final_select
from weave.trace_server.trace_server_common import assert_parameter_length_less_than_max
from weave.trace_server.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    extract_refs_from_values,
)

logger = logging.getLogger(__name__)

CTE_FILTERED_CALLS = "filtered_calls"
CTE_ALL_CALLS = "all_calls"
STORAGE_SIZE_TABLE_NAME = "storage_size_tbl"
ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME = "rolled_up_cms"
DISALLOWED_FILTERING_FIELDS = {"storage_size_bytes", "total_storage_size_bytes"}


def build_where_clause(*conditions: str) -> str:
    """Build a WHERE clause from multiple conditions.

    Takes any number of condition strings
    filters out empty ones, joins them with AND, and prepends WHERE.

    Args:
        *conditions: Variable number of condition strings (no AND/WHERE prefix)

    Returns:
        Complete WHERE clause, or empty string if no conditions
    """
    non_empty = [c for c in conditions if c]
    if not non_empty:
        return ""
    if len(non_empty) == 1:
        return f"WHERE {non_empty[0]}"
    return "WHERE " + "\n        AND ".join(non_empty)


def get_field_name(field: QueryFieldType) -> str:
    """Extract the field name from a QueryField.

    Args:
        field: A field object conforming to QueryField interface

    Returns:
        The field name as a string
    """
    return field.field


def field_in_list(field: QueryFieldType, field_list: list[QueryFieldType]) -> bool:
    """Check if a field exists in a list by comparing field names.

    Args:
        field: The field to search for
        field_list: List of fields to search in

    Returns:
        True if a field with the same name exists in the list
    """
    field_name = get_field_name(field)
    return any(get_field_name(f) == field_name for f in field_list)


def separate_conditions_for_query(
    strategy: TableStrategy,
    where_conditions: list[str],
    having_conditions: list[str],
) -> tuple[list[str], list[str]]:
    """Separate conditions into WHERE and HAVING based on grouping needs.

    If no grouping, everything goes in WHERE. If grouping, use both WHERE
    (pre-aggregation) and HAVING (post-aggregation).
    """
    if not strategy.requires_grouping():
        return where_conditions + having_conditions, []
    return where_conditions, having_conditions


def build_group_by_clause(strategy: TableStrategy) -> str:
    """Generate GROUP BY clause based on strategy."""
    if not strategy.requires_grouping():
        return ""
    table_name = strategy.table_name
    return f"GROUP BY ({table_name}.project_id, {table_name}.id)"


def build_having_clause(strategy: TableStrategy, conditions: list[str]) -> str:
    """Generate HAVING clause for post-aggregation filtering."""
    if not strategy.requires_grouping() or not conditions:
        return ""
    return f"HAVING {combine_conditions(conditions, 'AND')}"


def get_field_sql_for_filter(
    field_name: str,
    strategy: TableStrategy,
    pb: ParamBuilder,
    use_raw_column: bool = True,
) -> str:
    """Get SQL for a field in a filter context.

    Args:
        field_name: Name of field to get
        strategy: Table strategy to use
        pb: Parameter builder
        use_raw_column: If True and field supports aggregation, use raw column
                       (for WHERE clause). If False, use aggregated form.

    Returns:
        SQL expression for the field
    """
    field = get_field_by_name_strategy(field_name, strategy)
    if use_raw_column and field.supports_aggregation():
        return field.as_sql_without_aggregation(pb, strategy.table_name)

    return field.as_sql(pb, strategy.table_name)


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
        """Convert all filters to a single combined condition string.

        Returns all non-empty filters joined with AND (no WHERE keyword).
        Returns empty string if no filters.
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
        non_empty = [f for f in filters if f]
        return "\n        AND ".join(non_empty) if non_empty else ""


class QueryJoins(BaseModel):
    """Container for all JOIN clauses in the query."""

    feedback: str = ""
    storage_size: str = ""
    total_storage_size: str = ""
    object_ref: str = ""

    def to_sql(self) -> str:
        """Convert all joins to SQL clauses.

        Returns a string with all non-empty joins, properly formatted.
        """
        joins = [
            self.feedback,
            self.storage_size,
            self.total_storage_size,
            self.object_ref,
        ]
        return "\n        ".join(j for j in joins if j)


class OrderField(BaseModel):
    field: QueryFieldType
    direction: Literal["ASC", "DESC"]

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
    ) -> str:
        options: list[tuple[tsi_query.CastTo | None, str]]
        if isinstance(
            self.field,
            (
                DynamicField,
                FeedbackField,
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
                res = ""
                base_sql = f"any({cte_alias}.object_val_dump)"
                for index, (cast_to, direction) in enumerate(options):
                    if index > 0:
                        res += ", "
                    # For object refs, we use the base_sql directly with casting
                    if cast_to == "exists":
                        cast_sql = f"(NOT (JSONType(any({cte_alias}.object_val_dump)) = 'Null' OR JSONType(any({cte_alias}.object_val_dump)) IS NULL))"
                    else:
                        cast_sql = clickhouse_cast(base_sql, cast_to)
                    res += f"{cast_sql} {direction}"
                return res

        # Standard field ordering logic
        res = ""
        for index, (cast_to, direction) in enumerate(options):
            if index > 0:
                res += ", "
            res += f"{self.field.as_sql(pb, table_alias, cast_to)} {direction}"
        return res

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
    _consumed_fields: list[QueryFieldType] | None = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        read_table: ReadTable = ReadTable.CALLS_MERGED,
    ) -> str:
        # Check if this condition involves object references
        if (
            expand_columns
            and is_object_ref_operand(self.operand, expand_columns)
            and field_to_object_join_alias_map
        ):
            # For calls_complete, don't use aggregate functions since it's not grouped
            use_agg_fn = read_table != ReadTable.CALLS_COMPLETE
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
                self._consumed_fields.append(
                    get_field_by_name(raw_field_path, read_table)
                )
            return sql

        conditions = process_query_to_conditions(
            tsi_query.Query.model_validate({"$expr": {"$and": [self.operand]}}),
            pb,
            table_alias,
            read_table=read_table,
        )
        if self._consumed_fields is None:
            self._consumed_fields = []
            for field in conditions.fields_used:
                self._consumed_fields.append(field)
        return combine_conditions(conditions.conditions, "AND")

    def _get_consumed_fields(
        self, read_table: ReadTable = ReadTable.CALLS_MERGED
    ) -> list[QueryFieldType]:
        if self._consumed_fields is None:
            self.as_sql(ParamBuilder(), read_table.value, read_table=read_table)
        if self._consumed_fields is None:
            raise ValueError("Consumed fields should not be None")
        return self._consumed_fields

    def is_heavy(self) -> bool:
        for field in self._get_consumed_fields():
            if field.is_heavy():
                return True
        return False

    def is_feedback(self) -> bool:
        for field in self._get_consumed_fields():
            if isinstance(field, FeedbackField):
                return True
        return False

    def get_object_ref_conditions(
        self, expand_columns: list[str] | None = None
    ) -> list[ObjectRefCondition]:
        """Get any object ref conditions for CTE building."""
        expand_cols = expand_columns or []
        if not expand_cols or not is_object_ref_operand(self.operand, expand_cols):
            return []

        query_for_condition = tsi_query.Query.model_validate({"$expr": self.operand})
        object_ref_conditions = process_query_for_object_refs(
            query_for_condition, ParamBuilder(), "calls_merged", expand_cols
        )
        return object_ref_conditions


class HardCodedFilter(BaseModel):
    filter: tsi.CallsFilter
    read_table: ReadTable = ReadTable.CALLS_MERGED

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
            ]
        )

    def as_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        return combine_conditions(
            process_calls_filter_to_conditions(
                self.filter, pb, table_alias, read_table=self.read_table
            ),
            "AND",
        )


class CallsQuery(BaseModel):
    """Critical to be injection safe!"""

    project_id: str
    select_fields: list[QueryFieldType] = Field(default_factory=list)
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
    def strategy(self) -> TableStrategy:
        """Get the table strategy for this query."""
        return get_table_strategy(self.read_table)

    def add_field(self, field: str) -> "CallsQuery":
        field_obj = get_field_by_name(field, self.read_table)
        if field_in_list(field_obj, self.select_fields):
            return self
        self.select_fields.append(field_obj)
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
            OrderField(
                field=get_field_by_name(field, self.read_table),
                direction=direction,
            )
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

    def _should_optimize(self) -> bool:
        """Determines if query optimization should be performed.

        Returns True if the query has heavy fields and predicate pushdown is possible.
        Heavy fields are expensive to load into memory (inputs, output, attributes, summary).
        Predicate pushdown is possible when there are light filters, light query conditions,
        or light order filters that can be pushed down into a subquery.
        """
        # First, check if the query has any heavy fields
        has_heavy_select = any(field.is_heavy() for field in self.select_fields)
        has_heavy_filter = any(
            condition.is_heavy() for condition in self.query_conditions
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
        if any(not condition.is_heavy() for condition in self.query_conditions):
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
        # Set table_alias based on project version if not provided
        if table_alias is None:
            table_alias = self.read_table.value

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
        if self.read_table == ReadTable.CALLS_MERGED:
            self.add_condition(
                tsi_query.NotOperation.model_validate(
                    {
                        "$not": [
                            {"$eq": [{"$getField": "started_at"}, {"$literal": None}]}
                        ]
                    }
                )
            )

        object_ref_conditions = get_all_object_ref_conditions(
            self.query_conditions, self.order_fields, self.expand_columns
        )

        # If we should not optimize, then just build the base query
        if not should_optimize and not self.include_costs and not object_ref_conditions:
            return self._as_sql_base_format(pb)

        # Build two queries, first filter query CTE, then select the columns
        filter_query = CallsQuery(
            project_id=self.project_id, read_table=self.read_table
        )
        select_query = CallsQuery(
            project_id=self.project_id,
            read_table=self.read_table,
            include_storage_size=self.include_storage_size,
            include_total_storage_size=self.include_total_storage_size,
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
                if isinstance(field_obj, FeedbackField):
                    continue

                if isinstance(field_obj, DynamicField):
                    # we need to add the base field, not the dynamic one
                    base_field = get_field_by_name(field_obj.field, self.read_table)
                    if not field_in_list(base_field, select_query.select_fields):
                        select_query.select_fields.append(base_field)
                else:
                    # For non-dynamic fields (like started_at, op_name, etc.),
                    # add the field directly to ensure it's available in CTEs
                    if not field_in_list(field_obj, select_query.select_fields):
                        select_query.select_fields.append(field_obj)

        filtered_calls_sql = filter_query._as_sql_base_format(
            pb,
            field_to_object_join_alias_map=field_to_object_join_alias_map,
            expand_columns=self.expand_columns,
        )
        ctes.add_cte(CTE_FILTERED_CALLS, filtered_calls_sql)

        base_sql = select_query._as_sql_base_format(
            pb,
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

    def _convert_to_orm_sort_fields(self) -> list[tsi.SortBy]:
        return [
            tsi.SortBy(
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

        strategy = get_table_strategy(self.read_table)
        op_name = process_op_name_filter_to_sql(self.hardcoded_filter, pb, strategy)
        trace_id = process_trace_id_filter_to_sql(self.hardcoded_filter, pb, strategy)
        thread_id = process_thread_id_filter_to_sql(self.hardcoded_filter, pb, strategy)
        turn_id = process_turn_id_filter_to_sql(self.hardcoded_filter, pb, strategy)
        wb_run_id = process_wb_run_ids_filter_to_sql(
            self.hardcoded_filter, pb, strategy
        )
        ref_filter = process_ref_filters_to_sql(self.hardcoded_filter, pb, strategy)
        trace_roots_only = process_trace_roots_only_filter_to_sql(
            self.hardcoded_filter, pb, strategy
        )
        parent_ids = process_parent_ids_filter_to_sql(
            self.hardcoded_filter, pb, strategy
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
            non_object_ref_conditions, pb, table_alias
        )
        sortable_datetime = optimization_conditions.sortable_datetime_filters_sql or ""
        heavy_filter = optimization_conditions.heavy_filter_opt_sql or ""

        object_refs = process_object_refs_filter_to_opt_sql(
            pb, table_alias, object_ref_fields_consumed
        )
        id_subquery = make_id_subquery(table_alias, id_subquery_name)

        # special optimization for call_ids filter
        id_mask = ""
        if self.hardcoded_filter and self.hardcoded_filter.filter.call_ids:
            id_mask = f"({table_alias}.id IN {param_slot(pb.add_param(self.hardcoded_filter.filter.call_ids), 'Array(String)')})"

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
        expand_columns: list[str] | None,
        field_to_object_join_alias_map: dict[str, str] | None,
    ) -> QueryJoins:
        """Build all JOIN clauses for the query.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL
            project_param: The parameter name for project_id
            needs_feedback: Whether feedback JOIN is needed
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

        # Storage size join
        storage_size_join = ""
        if self.include_storage_size:
            storage_size_join = f"""
            LEFT JOIN (
                SELECT
                    id,
                    sum(COALESCE(attributes_size_bytes,0) + COALESCE(inputs_size_bytes,0) + COALESCE(output_size_bytes,0) + COALESCE(summary_size_bytes,0)) AS storage_size_bytes
                FROM {table_alias}_stats
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
                FROM {table_alias}_stats
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
            storage_size=storage_size_join,
            total_storage_size=total_storage_size_join,
            object_ref="".join(object_ref_joins_parts),
        )

    def _build_having_clause(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None,
        field_to_object_join_alias_map: dict[str, str] | None,
    ) -> tuple[str, bool]:
        """Build the HAVING clause for post-aggregation filtering.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL
            expand_columns: List of columns that should be expanded for object refs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases

        Returns:
            Tuple of (having_clause_sql, needs_feedback_flag)
        """
        needs_feedback = False
        having_conditions_sql: list[str] = []

        if len(self.query_conditions) > 0:
            for query_condition in self.query_conditions:
                query_condition_sql = query_condition.as_sql(
                    pb,
                    table_alias,
                    expand_columns=expand_columns,
                    field_to_object_join_alias_map=field_to_object_join_alias_map,
                    read_table=self.read_table,
                )
                having_conditions_sql.append(query_condition_sql)
                if query_condition.is_feedback():
                    needs_feedback = True

        if self.hardcoded_filter is not None:
            having_conditions_sql.append(self.hardcoded_filter.as_sql(pb, table_alias))

        having_filter_sql = ""
        if len(having_conditions_sql) > 0:
            having_filter_sql = "HAVING " + combine_conditions(
                having_conditions_sql, "AND"
            )

        return having_filter_sql, needs_feedback

    def _build_order_limit_offset(
        self,
        pb: ParamBuilder,
        table_alias: str,
        expand_columns: list[str] | None,
        field_to_object_join_alias_map: dict[str, str] | None,
    ) -> tuple[str, str, str, bool]:
        """Build ORDER BY, LIMIT, and OFFSET clauses.

        Args:
            pb: Parameter builder for query parameterization
            table_alias: The table alias to use in SQL
            expand_columns: List of columns that should be expanded for object refs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases

        Returns:
            Tuple of (order_by_sql, limit_sql, offset_sql, needs_feedback_flag)
        """
        needs_feedback = False
        order_by_sql = ""

        if len(self.order_fields) > 0:
            order_by_sqls = [
                order_field.as_sql(
                    pb, table_alias, expand_columns, field_to_object_join_alias_map
                )
                for order_field in self.order_fields
            ]
            order_by_sql = "ORDER BY " + ", ".join(order_by_sqls)
            for order_field in self.order_fields:
                if isinstance(order_field.field, FeedbackField):
                    needs_feedback = True

        limit_sql = f"LIMIT {self.limit}" if self.limit is not None else ""
        offset_sql = f"OFFSET {self.offset}" if self.offset is not None else ""

        return order_by_sql, limit_sql, offset_sql, needs_feedback

    def _as_sql_base_format(
        self,
        pb: ParamBuilder,
        id_subquery_name: str | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        expand_columns: list[str] | None = None,
    ) -> str:
        """Build the base SQL query format.

        Routes to the appropriate implementation based on project version.
        """
        if self.read_table == ReadTable.CALLS_COMPLETE:
            return self._as_sql_complete_format(
                pb,
                id_subquery_name,
                field_to_object_join_alias_map,
                expand_columns,
            )
        else:
            return self._as_sql_merged_format(
                pb,
                id_subquery_name,
                field_to_object_join_alias_map,
                expand_columns,
            )

    def _as_sql_merged_format(
        self,
        pb: ParamBuilder,
        id_subquery_name: str | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        expand_columns: list[str] | None = None,
    ) -> str:
        """Build SQL query for calls_merged table (with GROUP BY aggregation).

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
        table_alias = "calls_merged"

        select_fields_sql = ", ".join(
            field.as_select_sql(pb, table_alias) for field in self.select_fields
        )
        having_filter_sql, needs_feedback_having = self._build_having_clause(
            pb, table_alias, expand_columns, field_to_object_join_alias_map
        )
        where_filters = self._build_where_clause_optimizations(
            pb, table_alias, expand_columns, id_subquery_name
        )
        order_by_sql, limit_sql, offset_sql, needs_feedback_order = (
            self._build_order_limit_offset(
                pb, table_alias, expand_columns, field_to_object_join_alias_map
            )
        )
        project_param = pb.add_param(self.project_id)
        joins = self._build_joins(
            pb,
            table_alias,
            project_param,
            needs_feedback=needs_feedback_having or needs_feedback_order,
            expand_columns=expand_columns,
            field_to_object_join_alias_map=field_to_object_join_alias_map,
        )

        # Assemble the actual SQL query with GROUP BY for calls_merged
        joins_sql = joins.to_sql()
        joins_sql = f"\n        {joins_sql}" if joins_sql else ""
        raw_sql = f"""
        SELECT {select_fields_sql}
        FROM calls_merged{joins_sql}
        PREWHERE calls_merged.project_id = {param_slot(project_param, "String")}
        {build_where_clause(where_filters.to_sql())}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        {having_filter_sql}
        {order_by_sql}
        {limit_sql}
        {offset_sql}
        """

        return safely_format_sql(raw_sql, logger)

    def _as_sql_complete_format(
        self,
        pb: ParamBuilder,
        id_subquery_name: str | None = None,
        field_to_object_join_alias_map: dict[str, str] | None = None,
        expand_columns: list[str] | None = None,
    ) -> str:
        """Build SQL query for calls_complete table (no GROUP BY needed).

        Similar to _as_sql_merged_format but without GROUP BY/HAVING since
        calls_complete already has one row per call.

        Args:
            pb: Parameter builder for query parameterization
            id_subquery_name: Optional name of a CTE containing filtered IDs
            field_to_object_join_alias_map: Mapping of field paths to CTE aliases for object refs
            expand_columns: List of columns that should be expanded for object refs

        Returns:
            Complete SQL query string
        """
        table_alias = "calls_complete"
        strategy = get_table_strategy(self.read_table)
        select_fields_sql = ", ".join(
            field.as_select_sql(pb, table_alias) for field in self.select_fields
        )
        where_conditions: list[str] = []
        needs_feedback = False

        if len(self.query_conditions) > 0:
            for query_condition in self.query_conditions:
                query_condition_sql = query_condition.as_sql(
                    pb,
                    table_alias,
                    expand_columns=expand_columns,
                    field_to_object_join_alias_map=field_to_object_join_alias_map,
                    read_table=self.read_table,
                )
                where_conditions.append(query_condition_sql)
                if query_condition.is_feedback():
                    needs_feedback = True

        id_subquery_sql = make_id_subquery(table_alias, id_subquery_name)
        op_name_sql = process_op_name_filter_to_sql(self.hardcoded_filter, pb, strategy)
        trace_id_sql = process_trace_id_filter_to_sql(
            self.hardcoded_filter, pb, strategy
        )
        trace_roots_sql = process_trace_roots_only_filter_to_sql(
            self.hardcoded_filter, pb, strategy
        )

        # Add the rest of the hardcoded filters
        if self.hardcoded_filter is not None:
            where_conditions.append(self.hardcoded_filter.as_sql(pb, table_alias))

        where_conditions_sql = ""
        if where_conditions:
            where_conditions_sql = combine_conditions(where_conditions, "AND")
        order_by_sql, limit_sql, offset_sql, needs_feedback_order = (
            self._build_order_limit_offset(
                pb, table_alias, expand_columns, field_to_object_join_alias_map
            )
        )
        project_param = pb.add_param(self.project_id)
        joins = self._build_joins(
            pb,
            table_alias,
            project_param,
            needs_feedback=needs_feedback or needs_feedback_order,
            expand_columns=expand_columns,
            field_to_object_join_alias_map=field_to_object_join_alias_map,
        )

        # Combine all WHERE clause filters
        where_clause = build_where_clause(
            id_subquery_sql,
            trace_id_sql,
            trace_roots_sql,
            op_name_sql,
            where_conditions_sql,
        )

        # Assemble the actual SQL query WITHOUT GROUP BY for calls_complete
        joins_sql = joins.to_sql()
        joins_sql = f"\n        {joins_sql}" if joins_sql else ""
        raw_sql = f"""
        SELECT {select_fields_sql}
        FROM calls_complete{joins_sql}
        PREWHERE calls_complete.project_id = {param_slot(project_param, "String")}
        {where_clause}
        {order_by_sql}
        {limit_sql}
        {offset_sql}
        """

        return safely_format_sql(raw_sql, logger)


def get_field_by_name(
    name: str, read_table: ReadTable = ReadTable.CALLS_MERGED
) -> QueryFieldType:
    """Get field definition by name, version-aware for different storage tables.

    Args:
        name: Field name to look up
        read_table: Read table (MERGED or COMPLETE) to determine field type

    Returns:
        Field definition appropriate for the read table
    """
    strategy = get_table_strategy(read_table)
    return get_field_by_name_strategy(name, strategy)


# Handler function for status summary field
def _handle_status_summary_field(
    pb: ParamBuilder, table_alias: str, read_table: ReadTable = ReadTable.CALLS_MERGED
) -> str:
    # Status logic:
    # - If exception is not null -> ERROR
    # - Else if ended_at is null -> RUNNING
    # - Else -> SUCCESS
    exception_sql = get_field_by_name("exception", read_table).as_sql(pb, table_alias)
    ended_to_sql = get_field_by_name("ended_at", read_table).as_sql(pb, table_alias)
    status_counts_sql = get_field_by_name(
        "summary.status_counts.error", read_table
    ).as_sql(pb, table_alias, cast="int")

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
    pb: ParamBuilder, table_alias: str, read_table: ReadTable = ReadTable.CALLS_MERGED
) -> str:
    # Latency_ms logic:
    # - If ended_at is null or there's an exception, return null
    # - Otherwise calculate milliseconds between started_at and ended_at
    started_at_sql = get_field_by_name("started_at", read_table).as_sql(pb, table_alias)
    ended_at_sql = get_field_by_name("ended_at", read_table).as_sql(pb, table_alias)

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
    pb: ParamBuilder, table_alias: str, read_table: ReadTable = ReadTable.CALLS_MERGED
) -> str:
    # Trace_name logic:
    # - If display_name is available, use that
    # - Else if op_name starts with 'weave-trace-internal:///', extract the name using regex
    # - Otherwise, just use op_name directly

    display_name_sql = get_field_by_name("display_name", read_table).as_sql(
        pb, table_alias
    )
    op_name_sql = get_field_by_name("op_name", read_table).as_sql(pb, table_alias)

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
) -> Callable[[ParamBuilder, str, ReadTable], str] | None:
    """Returns the handler function for a given summary field name."""
    return SUMMARY_FIELD_HANDLERS.get(summary_field)


class FilterToConditions(BaseModel):
    conditions: list[str]
    fields_used: list[QueryFieldType]


def process_query_to_conditions(
    query: tsi.Query,
    param_builder: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> FilterToConditions:
    """Converts a Query to a list of conditions for a clickhouse query."""
    conditions = []
    raw_fields_used: dict[str, QueryFieldType] = {}

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
        elif isinstance(operation, tsi_query.GteOperation):
            lhs_part = process_operand(operation.gte_[0])
            rhs_part = process_operand(operation.gte_[1])
            cond = f"({lhs_part} >= {rhs_part})"
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

            structured_field = get_field_by_name(operand.get_field_, read_table)
            if (
                isinstance(structured_field, DynamicField)
                and structured_field.supports_aggregation()
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
                tsi_query.GteOperation,
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
    strategy: TableStrategy,
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

    op_field_sql = get_field_sql_for_filter("op_name", strategy, param_builder)
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

    return combine_conditions(or_conditions, "OR")


def process_trace_id_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    strategy: TableStrategy,
) -> str:
    """Pulls out the trace_id and returns a sql string if there are any trace_ids."""
    if hardcoded_filter is None or not hardcoded_filter.filter.trace_ids:
        return ""

    trace_ids = hardcoded_filter.filter.trace_ids

    assert_parameter_length_less_than_max("trace_ids", len(trace_ids))

    trace_id_field_sql = get_field_sql_for_filter("trace_id", strategy, param_builder)

    # If there's only one trace_id, use an equality condition for performance
    if len(trace_ids) == 1:
        trace_cond = f"{trace_id_field_sql} = {param_slot(param_builder.add_param(trace_ids[0]), 'String')}"
    elif len(trace_ids) > 1:
        trace_cond = f"{trace_id_field_sql} IN {param_slot(param_builder.add_param(trace_ids), 'Array(String)')}"
    else:
        return ""

    return f"({trace_cond} OR {trace_id_field_sql} IS NULL)"


def process_thread_id_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    strategy: TableStrategy,
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

    thread_id_field_sql = get_field_sql_for_filter("thread_id", strategy, param_builder)

    # If there's only one thread_id, use an equality condition for performance
    if len(thread_ids) == 1:
        thread_cond = f"{thread_id_field_sql} = {param_slot(param_builder.add_param(thread_ids[0]), 'String')}"
    elif len(thread_ids) > 1:
        thread_cond = f"{thread_id_field_sql} IN {param_slot(param_builder.add_param(thread_ids), 'Array(String)')}"
    else:
        return ""

    return f"({thread_cond} OR {thread_id_field_sql} IS NULL)"


def process_turn_id_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    strategy: TableStrategy,
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

    turn_id_field_sql = get_field_sql_for_filter("turn_id", strategy, param_builder)

    # If there's only one turn_id, use an equality condition for performance
    if len(turn_ids) == 1:
        turn_cond = f"{turn_id_field_sql} = {param_slot(param_builder.add_param(turn_ids[0]), 'String')}"
    elif len(turn_ids) > 1:
        turn_cond = f"{turn_id_field_sql} IN {param_slot(param_builder.add_param(turn_ids), 'Array(String)')}"
    else:
        return ""

    return f"({turn_cond} OR {turn_id_field_sql} IS NULL)"


def process_trace_roots_only_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    strategy: TableStrategy,
) -> str:
    """Pulls out the trace_roots_only and returns a sql string if there are any trace_roots_only."""
    if hardcoded_filter is None or not hardcoded_filter.filter.trace_roots_only:
        return ""

    parent_id_field_sql = get_field_sql_for_filter("parent_id", strategy, param_builder)

    return f"({parent_id_field_sql} IS NULL)"


def process_parent_ids_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    strategy: TableStrategy,
) -> str:
    """Pulls out the parent_id and returns a sql string if there are any parent_ids."""
    if hardcoded_filter is None or not hardcoded_filter.filter.parent_ids:
        return ""

    parent_id_field_sql = get_field_sql_for_filter("parent_id", strategy, param_builder)

    parent_ids_sql = f"{parent_id_field_sql} IN {param_slot(param_builder.add_param(hardcoded_filter.filter.parent_ids), 'Array(String)')}"

    return f"({parent_ids_sql} OR {parent_id_field_sql} IS NULL)"


def process_ref_filters_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    strategy: TableStrategy,
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
        field_sql = get_field_sql_for_filter(field_name, strategy, param_builder)
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

    return "(" + combine_conditions(ref_filters, "AND") + ")"


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
    conditions = []
    if "inputs_dump" in object_ref_fields_consumed:
        conditions.append(
            f"(length({table_alias}.input_refs) > 0 OR {table_alias}.started_at IS NULL)"
        )
    # If we are conditioning on output refs, filter down calls to those with non-zero
    # output refs, or they are a naked call start.
    if "output_dump" in object_ref_fields_consumed:
        conditions.append(
            f"(length({table_alias}.output_refs) > 0 OR {table_alias}.ended_at IS NULL)"
        )

    return " AND ".join(conditions) if conditions else ""


def process_wb_run_ids_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    strategy: TableStrategy,
) -> str:
    """Pulls out the wb_run_id and returns a sql string if there are any wb_run_ids."""
    if hardcoded_filter is None or not hardcoded_filter.filter.wb_run_ids:
        return ""

    wb_run_ids = hardcoded_filter.filter.wb_run_ids
    assert_parameter_length_less_than_max("wb_run_ids", len(wb_run_ids))
    wb_run_id_field_sql = get_field_sql_for_filter("wb_run_id", strategy, param_builder)
    wb_run_id_filter_sql = f"{wb_run_id_field_sql} IN {param_slot(param_builder.add_param(wb_run_ids), 'Array(String)')}"

    return f"({wb_run_id_filter_sql} OR {wb_run_id_field_sql} IS NULL)"


def process_calls_filter_to_conditions(
    filter: tsi.CallsFilter,
    param_builder: ParamBuilder,
    table_alias: str,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> list[str]:
    """Converts a CallsFilter to a list of conditions for a clickhouse query.

    Excludes the op_name, which is handled separately.
    """
    conditions: list[str] = []

    # technically not required, as we are now doing a pre-groupby optimization
    # that should filter out 100% of non-matching rows. However, we can't remove
    # the output_refs, so lets keep both for clarity
    if filter.input_refs:
        assert_parameter_length_less_than_max("input_refs", len(filter.input_refs))
        conditions.append(
            f"hasAny({get_field_by_name('input_refs', read_table).as_sql(param_builder, table_alias)}, {param_slot(param_builder.add_param(filter.input_refs), 'Array(String)')})"
        )

    if filter.output_refs:
        assert_parameter_length_less_than_max("output_refs", len(filter.output_refs))
        conditions.append(
            f"hasAny({get_field_by_name('output_refs', read_table).as_sql(param_builder, table_alias)}, {param_slot(param_builder.add_param(filter.output_refs), 'Array(String)')})"
        )

    if filter.parent_ids:
        assert_parameter_length_less_than_max("parent_ids", len(filter.parent_ids))
        conditions.append(
            f"{get_field_by_name('parent_id', read_table).as_sql(param_builder, table_alias)} IN {param_slot(param_builder.add_param(filter.parent_ids), 'Array(String)')}"
        )

    if filter.call_ids:
        assert_parameter_length_less_than_max("call_ids", len(filter.call_ids))
        conditions.append(
            f"{get_field_by_name('id', read_table).as_sql(param_builder, table_alias)} IN {param_slot(param_builder.add_param(filter.call_ids), 'Array(String)')}"
        )

    if filter.thread_ids is not None:
        assert_parameter_length_less_than_max("thread_ids", len(filter.thread_ids))
        conditions.append(
            f"{get_field_by_name('thread_id', read_table).as_sql(param_builder, table_alias)} IN {param_slot(param_builder.add_param(filter.thread_ids), 'Array(String)')}"
        )

    if filter.turn_ids is not None:
        assert_parameter_length_less_than_max("turn_ids", len(filter.turn_ids))
        conditions.append(
            f"{get_field_by_name('turn_id', read_table).as_sql(param_builder, table_alias)} IN {param_slot(param_builder.add_param(filter.turn_ids), 'Array(String)')}"
        )

    if filter.wb_user_ids:
        conditions.append(
            f"{get_field_by_name('wb_user_id', read_table).as_sql(param_builder, table_alias)} IN {param_slot(param_builder.add_param(filter.wb_user_ids), 'Array(String)')}"
        )

    if filter.wb_run_ids:
        conditions.append(
            f"{get_field_by_name('wb_run_id', read_table).as_sql(param_builder, table_alias)} IN {param_slot(param_builder.add_param(filter.wb_run_ids), 'Array(String)')}"
        )

    return conditions


def make_id_subquery(
    table_alias: str,
    id_subquery_name: str | None,
) -> str:
    if id_subquery_name is None:
        return ""
    return f"({table_alias}.id IN {id_subquery_name})"


######### STATS QUERY HANDLING ##########


def build_calls_stats_query(
    req: tsi.CallsQueryStatsReq,
    param_builder: ParamBuilder,
    read_table: ReadTable,
) -> tuple[str, KeysView[str]]:
    """Build a stats query for calls, automatically using optimized queries when possible.

    This function handles both optimized special-case queries and the general case.
    Returns a tuple of (query_sql, column_names).

    Args:
        req: The stats query request
        param_builder: Parameter builder for query parameterization
        read_table: Read table (CALLS_MERGED or CALLS_COMPLETE) to use

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
        cq.set_hardcoded_filter(
            HardCodedFilter(filter=req.filter, read_table=read_table)
        )
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
    read_table: ReadTable = ReadTable.CALLS_MERGED,
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
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> str:
    """Returns a query that checks if the project contains any calls."""
    return safely_format_sql(
        f"""SELECT
    toUInt8(count()) AS has_any
    FROM
    (
        SELECT 1
        FROM {read_table.value}
        WHERE project_id = {param_slot(param_builder.add_param(project_id), "String")}
        LIMIT 1
    )
    """,
        logger,
    )


def _optimized_wb_run_id_not_null_query(
    project_id: str,
    param_builder: ParamBuilder,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> str:
    """Optimized query for checking existence of calls with wb_run_id not null.

    Uses WHERE clause instead of HAVING to avoid expensive aggregation.
    """
    project_id_param = param_builder.add_param(project_id)
    table_name = read_table.value
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
        and filter.op_names is None
        and filter.call_ids is None
        and filter.trace_ids is None
        and filter.parent_ids is None
        and filter.trace_roots_only is None
        and filter.input_refs is None
        and filter.output_refs is None
    )


######### BATCH UPDATE QUERY HANDLING ##########


def _build_grouped_case_statements(
    call_values: list[tuple[str, Any]],
    clickhouse_type: str,
    pb: ParamBuilder,
    is_nullable: bool = False,
    is_array: bool = False,
    array_element_type: str | None = None,
) -> list[str]:
    """Build optimized CASE WHEN clauses by grouping calls with identical values.

    This reduces query size and parameter count when multiple calls share the same value.

    Args:
        call_values: List of (call_id, value) tuples
        clickhouse_type: ClickHouse type string (e.g., 'String', 'DateTime64(6)')
        pb: Parameter builder for query parameterization
        is_nullable: Whether NULL is allowed for this field
        is_array: Whether this is an array field
        array_element_type: ClickHouse type for array elements (required if is_array=True)

    Returns:
        List of CASE WHEN clause strings, optimized by grouping identical values

    Examples:
        >>> pb = ParamBuilder()
        >>> # Three calls, two with same exception
        >>> calls = [("id1", "Error"), ("id2", "Error"), ("id3", None)]
        >>> _build_grouped_case_statements(calls, "String", pb, is_nullable=True)
        ['WHEN id IN ({id1:String}, {id2:String}) THEN {val:String}',
         'WHEN id = {id3:String} THEN NULL']
    """
    if not call_values:
        return []

    # Group calls by their value
    value_to_ids = _group_calls_by_value(call_values, is_array)

    # Build CASE clauses for each unique value
    cases = []
    for group_key, call_ids in value_to_ids.items():
        value = _convert_group_key_to_value(group_key, is_array)
        id_clause = _build_id_clause(call_ids, pb)
        value_clause = _build_value_clause(
            value, clickhouse_type, array_element_type, is_nullable, is_array, pb
        )
        cases.append(f"WHEN {id_clause} THEN {value_clause}")

    return cases


def _group_calls_by_value(
    call_values: list[tuple[str, Any]], is_array: bool
) -> dict[Any, list[str]]:
    """Group call IDs by their field value.

    For arrays, converts to tuples for hashability.
    """
    value_to_ids: dict[Any, list[str]] = defaultdict(list)
    for call_id, value in call_values:
        group_key = (
            tuple(value) if is_array and value else (value if not is_array else ())
        )
        value_to_ids[group_key].append(call_id)
    return value_to_ids


def _convert_group_key_to_value(group_key: Any, is_array: bool) -> Any:
    """Convert a group key back to its original value type."""
    if is_array and group_key:
        return list(group_key)
    elif is_array:
        return []
    else:
        return group_key


def _build_id_clause(call_ids: list[str], pb: ParamBuilder) -> str:
    """Build the ID matching clause (= for single, IN for multiple)."""
    if len(call_ids) == 1:
        id_param = pb.add_param(call_ids[0])
        return f"id = {param_slot(id_param, 'String')}"
    else:
        id_params = [param_slot(pb.add_param(cid), "String") for cid in call_ids]
        return f"id IN ({', '.join(id_params)})"


def _build_value_clause(
    value: Any,
    clickhouse_type: str,
    array_element_type: str | None,
    is_nullable: bool,
    is_array: bool,
    pb: ParamBuilder,
) -> str:
    """Build the value clause for a CASE WHEN statement.

    For nullable fields, we explicitly cast ALL values (both NULL and non-NULL)
    to Nullable(type) to ensure consistent block structure during ClickHouse
    lightweight update patch-part merging. Without explicit casting, different
    CASE branches may have mismatched types (String vs Nullable(String)), causing
    block structure mismatches in distributed/replicated environments during
    concurrent patch-part merges.
    """
    if is_array:
        if array_element_type is None:
            raise ValueError("array_element_type must be provided for array fields")
        return _build_array_value_clause(value, array_element_type, pb)

    if is_nullable:
        if value is None:
            # Explicitly cast NULL to ensure consistent type inference across
            # all patch parts during distributed lightweight updates
            return f"CAST(NULL AS Nullable({clickhouse_type}))"
        else:
            # Cast non-NULL values to Nullable(type) as well to ensure all
            # CASE branches have identical return types
            value_param = pb.add_param(value)
            return f"CAST({param_slot(value_param, clickhouse_type)} AS Nullable({clickhouse_type}))"

    value_param = pb.add_param(value)
    return param_slot(value_param, clickhouse_type)


def _build_array_value_clause(
    value: list, array_element_type: str, pb: ParamBuilder
) -> str:
    """Build the value clause for an array field."""
    if value:
        params = [param_slot(pb.add_param(val), array_element_type) for val in value]
        return f"[{', '.join(params)}]"
    else:
        return f"CAST([], 'Array({array_element_type})')"


def _add_on_cluster_to_update(sql_query: str, cluster_name: str | None) -> str:
    """Add ON CLUSTER clause to UPDATE statement if cluster_name is provided.

    Args:
        sql_query: The UPDATE SQL query
        cluster_name: The cluster name to use (if None, returns query unchanged)

    Returns:
        SQL query with ON CLUSTER added if applicable
    """
    if not cluster_name:
        return sql_query

    # Check if this is an UPDATE statement and doesn't already have ON CLUSTER
    if not re.search(r"\bUPDATE\b", sql_query, flags=re.IGNORECASE):
        return sql_query

    if re.search(r"\bON\s+CLUSTER\b", sql_query, flags=re.IGNORECASE):
        return sql_query

    # Match "UPDATE table_name" and add ON CLUSTER after table name
    # Pattern matches: UPDATE [optional whitespace] table_name [whitespace or newline]
    pattern = r"(\bUPDATE\s+)([a-zA-Z0-9_]+)(\s)"

    def add_cluster(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)} ON CLUSTER {cluster_name}{match.group(3)}"

    return re.sub(pattern, add_cluster, sql_query, flags=re.IGNORECASE)


def build_calls_complete_single_update_query(
    end_call: "tsi.EndedCallSchemaForInsert",
    pb: ParamBuilder,
    table_name: str = "calls_complete",
    cluster_name: str | None = None,
) -> str:
    """Build a parameterized UPDATE query for a single call in calls_complete table.

    This creates a lightweight UPDATE that only includes columns with non-default values,
    avoiding CASE/WHEN/ELSE constructs. Columns that would be set to their default values
    are omitted entirely:
    - exception: omitted if None (NULL is the default from INSERT)
    - output_refs: omitted if empty ([] is the default from INSERT)
    - wb_run_step_end: omitted if None (NULL is the default from INSERT)

    This approach ensures consistent patch part column structure within each "type"
    of update, preventing block structure mismatch errors during ClickHouse merge
    operations in distributed/sharded environments.

    ClickHouse patch parts are partitioned by a hash of the column names being updated,
    so updates with different column sets go to different partitions and can be merged
    independently without conflicts.

    The columns are ordered to match the table schema exactly.

    Args:
        end_call: Single ended call schema to update
        pb: Parameter builder for query parameterization
        table_name: Name of the table to update (defaults to "calls_complete")
        cluster_name: Optional cluster name for ON CLUSTER clause

    Returns:
        Formatted SQL UPDATE command string

    Examples:
        >>> pb = ParamBuilder()
        >>> query = build_calls_complete_single_update_query(end_call, pb)
    """
    project_id = end_call.project_id
    call_id = end_call.id

    # Build SET clauses only for fields that are actually being updated.
    # Order matches table schema to ensure consistent column structure.
    set_clauses: list[str] = []

    # ended_at is always present (required field)
    ended_at_param = pb.add_param(end_call.ended_at)
    set_clauses.append(f"ended_at = {param_slot(ended_at_param, 'DateTime64(6)')}")

    # updated_at is always set
    set_clauses.append("updated_at = now64(3)")

    # output_dump - serialize output (can be None, which becomes "null" JSON)
    output_dump = json.dumps(end_call.output)
    output_dump_param = pb.add_param(output_dump)
    set_clauses.append(f"output_dump = {param_slot(output_dump_param, 'String')}")

    # summary_dump is always present (required field)
    summary_dump = json.dumps(dict(end_call.summary))
    summary_dump_param = pb.add_param(summary_dump)
    set_clauses.append(f"summary_dump = {param_slot(summary_dump_param, 'String')}")

    # exception - only include if there's an actual exception string
    # NULL is the default value from INSERT, no need to update if None
    if end_call.exception is not None:
        exception_param = pb.add_param(end_call.exception)
        set_clauses.append(
            f"exception = {param_slot(exception_param, 'Nullable(String)')}"
        )

    # output_refs - only include if there are actual refs
    # Empty array is the default value from INSERT, no need to update if empty
    output_refs = extract_refs_from_values(end_call.output)
    if output_refs:
        ref_params = [param_slot(pb.add_param(ref), "String") for ref in output_refs]
        set_clauses.append(f"output_refs = [{', '.join(ref_params)}]")

    # wb_run_step_end - only include if actually provided (not None)
    # NULL is the default value from INSERT, no need to update if None
    if end_call.wb_run_step_end is not None:
        wb_run_step_end_param = pb.add_param(end_call.wb_run_step_end)
        set_clauses.append(
            f"wb_run_step_end = {param_slot(wb_run_step_end_param, 'Nullable(UInt64)')}"
        )

    # Build WHERE clause
    project_id_param = param_slot(pb.add_param(project_id), "String")
    call_id_param = param_slot(pb.add_param(call_id), "String")

    # Construct the final UPDATE command
    set_sql = ",\n        ".join(set_clauses)
    raw_sql = f"""
    UPDATE {table_name}
    SET
        {set_sql}
    WHERE project_id = {project_id_param}
      AND id = {call_id_param}
    """

    formatted_sql = safely_format_sql(raw_sql, logger)
    return _add_on_cluster_to_update(formatted_sql, cluster_name)


def build_calls_complete_batch_update_query(
    end_calls: list["tsi.EndedCallSchemaForInsert"],
    pb: ParamBuilder,
    table_name: str = "calls_complete",
    cluster_name: str | None = None,
) -> str:
    """Build a parameterized batch UPDATE query for calls_complete table.

    This uses ClickHouse's lightweight UPDATE with CASE expressions to update
    multiple calls in a single query, creating only one patch part instead of N.

    Optimizes by grouping calls with identical values to reduce query size.

    Args:
        end_calls: List of ended call schemas to update
        pb: Parameter builder for query parameterization
        table_name: Name of the table to update (defaults to "calls_complete")
        cluster_name: Optional cluster name for ON CLUSTER clause

    Returns:
        Formatted SQL UPDATE command string

    Examples:
        >>> pb = ParamBuilder()
        >>> end_calls = [ended_call1, ended_call2]
        >>> query = build_calls_complete_batch_update_query(end_calls, pb)
    """
    if not end_calls:
        return ""

    # All calls should be from the same project
    project_id = end_calls[0].project_id
    call_ids = []

    # Collect values for each field across all calls
    field_values: dict[str, list[Any]] = {
        "ended_at": [],
        "output_dump": [],
        "output_refs": [],
        "summary_dump": [],
        "exception": [],
        "wb_run_step_end": [],
    }

    for call in end_calls:
        call_ids.append(call.id)
        field_values["ended_at"].append((call.id, call.ended_at))
        field_values["output_dump"].append((call.id, json.dumps(call.output)))
        field_values["output_refs"].append(
            (call.id, extract_refs_from_values(call.output))
        )
        field_values["summary_dump"].append((call.id, json.dumps(dict(call.summary))))
        field_values["exception"].append((call.id, call.exception))
        field_values["wb_run_step_end"].append((call.id, call.wb_run_step_end))

    # Build optimized CASE statements (groups calls with identical values)
    field_cases = {
        "ended_at": _build_grouped_case_statements(
            field_values["ended_at"], "DateTime64(6)", pb
        ),
        "output_dump": _build_grouped_case_statements(
            field_values["output_dump"], "String", pb
        ),
        "output_refs": _build_grouped_case_statements(
            field_values["output_refs"],
            "Array(String)",
            pb,
            is_array=True,
            array_element_type="String",
        ),
        "summary_dump": _build_grouped_case_statements(
            field_values["summary_dump"], "String", pb
        ),
        "exception": _build_grouped_case_statements(
            field_values["exception"], "String", pb, is_nullable=True
        ),
        "wb_run_step_end": _build_grouped_case_statements(
            field_values["wb_run_step_end"], "UInt64", pb, is_nullable=True
        ),
    }

    # Format CASE expressions with proper indentation
    def format_cases(cases: list[str]) -> str:
        """Format a list of CASE conditions into a multi-line string."""
        return "\n".join(cases)

    # Build WHERE clause with parameterized IN clause
    where_params = [param_slot(pb.add_param(cid), "String") for cid in call_ids]
    project_id_param = param_slot(pb.add_param(project_id), "String")

    # Construct the final UPDATE command
    raw_sql = f"""
    UPDATE {table_name}
    SET
        ended_at = CASE {format_cases(field_cases["ended_at"])} ELSE ended_at END,
        updated_at = now64(3),
        output_dump = CASE {format_cases(field_cases["output_dump"])} ELSE output_dump END,
        summary_dump = CASE {format_cases(field_cases["summary_dump"])} ELSE summary_dump END,
        exception = CASE {format_cases(field_cases["exception"])} ELSE exception END,
        output_refs = CASE {format_cases(field_cases["output_refs"])} ELSE output_refs END,
        wb_run_step_end = CASE {format_cases(field_cases["wb_run_step_end"])} ELSE wb_run_step_end END
    WHERE project_id = {project_id_param}
      AND id IN ({", ".join(where_params)})
    """

    formatted_sql = safely_format_sql(raw_sql, logger)
    return _add_on_cluster_to_update(formatted_sql, cluster_name)


def _build_calls_complete_update_query(
    project_id: str,
    call_ids: list[str],
    update_fields: dict[str, tuple[Any, str]],
    wb_user_id: str,
    updated_at: datetime.datetime,
    pb: ParamBuilder,
    table_name: str = "calls_complete",
    cluster_name: str | None = None,
) -> str | None:
    """Build a parameterized UPDATE query for calls_complete table.

    Args:
        project_id: The project ID to filter by
        call_ids: List of call IDs to update
        update_fields: Dictionary mapping field names to (value, clickhouse_type) tuples
        wb_user_id: User ID performing the update
        updated_at: Timestamp of the update
        pb: ParamBuilder for parameterized queries
        table_name: Name of the table to update (defaults to "calls_complete")
        cluster_name: Optional cluster name for ON CLUSTER clause

    Returns:
        Formatted SQL query string or None if no call_ids provided
    """
    # Handle empty list case
    if not call_ids:
        return None

    # Build parameters
    project_id_param = pb.add_param(project_id)
    call_ids_param = pb.add_param(call_ids)
    updated_at_param = pb.add_param(updated_at)
    wb_user_id_param = pb.add_param(wb_user_id)

    # Build SET clause with custom fields + standard audit fields
    set_clauses = []
    for field_name, (value, clickhouse_type) in update_fields.items():
        param = pb.add_param(value)
        set_clauses.append(f"{field_name} = {param_slot(param, clickhouse_type)}")

    # Add standard audit fields
    set_clauses.append(f"updated_at = {param_slot(updated_at_param, 'DateTime64(3)')}")
    set_clauses.append(f"wb_user_id = {param_slot(wb_user_id_param, 'String')}")
    set_sql = ", ".join(set_clauses)

    raw_sql = f"""
        UPDATE {table_name}
        SET
            {set_sql}
        WHERE project_id = {param_slot(project_id_param, "String")}
            AND id IN {param_slot(call_ids_param, "Array(String)")}
    """
    formatted_sql = safely_format_sql(raw_sql, logger)
    return _add_on_cluster_to_update(formatted_sql, cluster_name)


def build_calls_complete_update_display_name_query(
    project_id: str,
    call_id: str,
    display_name: str,
    wb_user_id: str,
    updated_at: datetime.datetime,
    pb: ParamBuilder,
    table_name: str = "calls_complete",
    cluster_name: str | None = None,
) -> str | None:
    """Build a parameterized UPDATE query for calls_complete table to update the display_name field."""
    update_fields = {"display_name": (display_name, "String")}
    return _build_calls_complete_update_query(
        project_id=project_id,
        call_ids=[call_id],
        update_fields=update_fields,
        wb_user_id=wb_user_id,
        updated_at=updated_at,
        pb=pb,
        table_name=table_name,
        cluster_name=cluster_name,
    )


def build_calls_complete_batch_delete_query(
    project_id: str,
    call_ids: list[str],
    deleted_at: datetime.datetime,
    wb_user_id: str,
    updated_at: datetime.datetime,
    pb: ParamBuilder,
    table_name: str = "calls_complete",
    cluster_name: str | None = None,
) -> str | None:
    """Build a parameterized DELETE query for calls_complete table.
    This uses ClickHouse's lightweight DELETE with parameterized IN clause.
    """
    update_fields = {"deleted_at": (deleted_at, "DateTime64(3)")}
    return _build_calls_complete_update_query(
        project_id=project_id,
        call_ids=call_ids,
        update_fields=update_fields,
        wb_user_id=wb_user_id,
        updated_at=updated_at,
        pb=pb,
        table_name=table_name,
        cluster_name=cluster_name,
    )
