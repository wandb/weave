"""
This module builds on the orm.py module to provide a more hard-coded optimized
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
* [ ] Consider how we will do feedback fields

"""

import logging
import typing

import sqlparse
from pydantic import BaseModel, Field

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    combine_conditions,
    python_value_to_ch_type,
    quote_json_path_parts,
)
from weave.trace_server.token_costs import cost_query
from weave.trace_server.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
)

logger = logging.getLogger(__name__)


class QueryBuilderField(BaseModel):
    field: str

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: typing.Optional[tsi_query.CastTo] = None,
    ) -> str:
        return clickhouse_cast(f"{table_alias}.{self.field}", cast)

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
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
        cast: typing.Optional[tsi_query.CastTo] = None,
    ) -> str:
        inner = super().as_sql(pb, table_alias)
        return clickhouse_cast(f"{self.agg_fn}({inner})")


class CallsMergedDynamicField(CallsMergedAggField):
    extra_path: typing.Optional[list[str]] = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: typing.Optional[tsi_query.CastTo] = None,
    ) -> str:
        res = super().as_sql(pb, table_alias)
        return json_dump_field_as_sql(pb, table_alias, res, self.extra_path, cast)

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        return f"{super().as_sql(pb, table_alias)} AS {self.field}"

    def with_path(self, path: list[str]) -> "CallsMergedDynamicField":
        extra_path = [*(self.extra_path or [])]
        extra_path.extend(path)
        return CallsMergedDynamicField(
            field=self.field, agg_fn=self.agg_fn, extra_path=extra_path
        )

    def is_heavy(self) -> bool:
        return True


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

    extra_path: typing.Optional[list[str]] = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: typing.Optional[tsi_query.CastTo] = None,
    ) -> str:
        res = super().as_sql(pb, table_alias)
        return json_dump_field_as_sql(pb, table_alias, res, self.extra_path, cast)

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        return f"{super().as_sql(pb, table_alias)} AS {self.field}"


def json_dump_field_as_sql(
    pb: ParamBuilder,
    table_alias: str,
    root_field_sanitized: str,
    extra_path: typing.Optional[list[str]] = None,
    cast: typing.Optional[tsi_query.CastTo] = None,
) -> str:
    if cast != "exists":
        path_str = "'$'"
        if extra_path:
            param_name = pb.add_param(quote_json_path_parts(extra_path))
            path_str = _param_slot(param_name, "String")
        val = f"JSON_VALUE({root_field_sanitized}, {path_str})"
        return clickhouse_cast(val, cast)
    else:
        # Note: ClickHouse has limitations in distinguishing between null, non-existent, empty string, and "null".
        # This workaround helps to handle these cases.
        path_parts = []
        if extra_path:
            for part in extra_path:
                path_parts.append(", " + _param_slot(pb.add_param(part), "String"))
        safe_path = "".join(path_parts)
        return f"(NOT (JSONType({root_field_sanitized}{safe_path}) = 'Null' OR JSONType({root_field_sanitized}{safe_path}) IS NULL))"


class OrderField(BaseModel):
    field: QueryBuilderField
    direction: typing.Literal["ASC", "DESC"]

    def as_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        options: list[typing.Tuple[typing.Optional[tsi_query.CastTo], str]]
        if isinstance(self.field, (QueryBuilderDynamicField, CallsMergedDynamicField)):
            # Prioritize existence, then cast to double, then str
            options = [
                ("exists", "desc"),
                ("double", self.direction),
                ("string", self.direction),
            ]
        else:
            options = [(None, self.direction)]
        res = ""
        for index, (cast, direction) in enumerate(options):
            if index > 0:
                res += ", "
            res += f"{self.field.as_sql(pb, table_alias, cast)} {direction}"
        return res


class Condition(BaseModel):
    operand: "tsi_query.Operand"
    _consumed_fields: typing.Optional[list[CallsMergedField]] = None

    def as_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        conditions = process_query_to_conditions(
            tsi_query.Query.model_validate({"$expr": {"$and": [self.operand]}}),
            pb,
            table_alias,
        )
        if self._consumed_fields is None:
            self._consumed_fields = []
            for field in conditions.fields_used:
                self._consumed_fields.append(get_field_by_name(field))
        return combine_conditions(conditions.conditions, "AND")

    def _get_consumed_fields(self) -> list[CallsMergedField]:
        if self._consumed_fields is None:
            self.as_sql(ParamBuilder(), "calls_merged")
        if self._consumed_fields is None:
            raise ValueError("Consumed fields should not be None")
        return self._consumed_fields

    def is_heavy(self) -> bool:
        for field in self._get_consumed_fields():
            if field.is_heavy():
                return True
        return False


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
            ]
        )

    def as_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        return combine_conditions(
            process_calls_filter_to_conditions(self.filter, pb, table_alias),
            "AND",
        )


class CallsQuery(BaseModel):
    """Critical to be injection safe!"""

    project_id: str
    select_fields: list[CallsMergedField] = Field(default_factory=list)
    query_conditions: list[Condition] = Field(default_factory=list)
    hardcoded_filter: typing.Optional[HardCodedFilter] = None
    order_fields: list[OrderField] = Field(default_factory=list)
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None
    include_costs: bool = False

    def add_field(self, field: str) -> "CallsQuery":
        self.select_fields.append(get_field_by_name(field))
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
        direction = direction.upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Direction {direction} is not allowed")
        direction = typing.cast(typing.Literal["ASC", "DESC"], direction)
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
        )

    def set_include_costs(self, include_costs: bool) -> "CallsQuery":
        self.include_costs = include_costs
        return self

    def as_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        """
        This is the main entry point for building the query. This method will
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
        AND id IN (filtered_calls)
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

        # Determine if the query `has_heavy_fields` by checking
        # if it `has_heavy_select or has_heavy_filter or has_heavy_order`
        has_heavy_select = any(field.is_heavy() for field in self.select_fields)

        has_heavy_filter = any(
            condition.is_heavy() for condition in self.query_conditions
        )

        has_heavy_order = any(
            order_field.field.is_heavy() for order_field in self.order_fields
        )

        has_heavy_fields = has_heavy_select or has_heavy_filter or has_heavy_order

        # Determine if `predicate_pushdown_possible` which is
        # if it `has_light_filter or has_light_query or has_light_order_filter`
        has_light_filter = self.hardcoded_filter and self.hardcoded_filter.is_useful()

        has_light_query = any(
            not condition.is_heavy() for condition in self.query_conditions
        )

        has_light_order_filter = (
            self.order_fields
            and self.limit
            and not has_heavy_filter
            and not has_heavy_order
        )

        predicate_pushdown_possible = (
            has_light_filter or has_light_query or has_light_order_filter
        )

        # Determine if we should optimize!
        should_optimize = has_heavy_fields and predicate_pushdown_possible

        # Important: Always inject deleted_at into the query.
        # Note: it might be better to make this configurable.
        self.add_condition(
            tsi_query.EqOperation.model_validate(
                {"$eq": [{"$getField": "deleted_at"}, {"$literal": None}]}
            )
        )

        # Important: We must always filter out calls that have not been started
        # This can occur when there is an out of order call part insertion or worse,
        # when such occurance happens and the client terminates early.
        self.add_condition(
            tsi_query.NotOperation.model_validate(
                {"$not": [{"$eq": [{"$getField": "started_at"}, {"$literal": None}]}]}
            )
        )

        # If we should not optimize, then just build the base query
        if not should_optimize and not self.include_costs:
            return self._as_sql_base_format(pb, table_alias)

        # If so, build the two queries
        filter_query = CallsQuery(project_id=self.project_id)
        outer_query = CallsQuery(project_id=self.project_id)

        # Select Fields:
        filter_query.add_field("id")
        for field in self.select_fields:
            outer_query.select_fields.append(field)

        # Query Conditions
        for condition in self.query_conditions:
            if condition.is_heavy():
                outer_query.query_conditions.append(condition)
            else:
                filter_query.query_conditions.append(condition)

        # Hardcoded Filter - always light
        filter_query.hardcoded_filter = self.hardcoded_filter

        # Order Fields:
        if has_light_order_filter:
            filter_query.order_fields = self.order_fields
            filter_query.limit = self.limit
            filter_query.offset = self.offset
            # SUPER IMPORTANT: still need to re-sort the final query
            outer_query.order_fields = self.order_fields
        else:
            outer_query.order_fields = self.order_fields
            outer_query.limit = self.limit
            outer_query.offset = self.offset

        raw_sql = f"""
        WITH filtered_calls AS ({filter_query._as_sql_base_format(pb, table_alias)})
        """

        if self.include_costs:
            # TODO: We should unify the calls query order by fields to be orm sort by fields
            order_by_fields = [
                tsi.SortBy(
                    field=sort_by.field.field, direction=sort_by.direction.lower()
                )
                for sort_by in self.order_fields
            ]
            raw_sql += f""",
            all_calls AS ({outer_query._as_sql_base_format(pb, table_alias, id_subquery_name="filtered_calls")}),
            {cost_query(pb, "all_calls", self.project_id, [field.field for field in self.select_fields], order_by_fields)}
            """

        else:
            raw_sql += f"""
            {outer_query._as_sql_base_format(pb, table_alias, id_subquery_name="filtered_calls")}
            """

        return _safely_format_sql(raw_sql)

    def _as_sql_base_format(
        self,
        pb: ParamBuilder,
        table_alias: str,
        id_subquery_name: typing.Optional[str] = None,
    ) -> str:
        select_fields_sql = ", ".join(
            field.as_select_sql(pb, table_alias) for field in self.select_fields
        )

        having_filter_sql = ""
        having_conditions_sql: list[str] = []
        if len(self.query_conditions) > 0:
            having_conditions_sql.extend(
                c.as_sql(pb, table_alias) for c in self.query_conditions
            )
        if self.hardcoded_filter is not None:
            having_conditions_sql.append(self.hardcoded_filter.as_sql(pb, table_alias))

        if len(having_conditions_sql) > 0:
            having_filter_sql = "HAVING " + combine_conditions(
                having_conditions_sql, "AND"
            )

        order_by_sql = ""
        if len(self.order_fields) > 0:
            order_by_sql = "ORDER BY " + ", ".join(
                [
                    order_field.as_sql(pb, table_alias)
                    for order_field in self.order_fields
                ]
            )

        limit_sql = ""
        if self.limit is not None:
            limit_sql = f"LIMIT {self.limit}"

        offset_sql = ""
        if self.offset is not None:
            offset_sql = f"OFFSET {self.offset}"

        id_subquery_sql = ""
        if id_subquery_name is not None:
            id_subquery_sql = f"AND (id IN {id_subquery_name})"

        project_param = pb.add_param(self.project_id)

        # Special Optimization
        id_mask_sql = ""
        if self.hardcoded_filter and self.hardcoded_filter.filter.call_ids:
            id_mask_sql = f"AND (id IN {_param_slot(pb.add_param(self.hardcoded_filter.filter.call_ids), 'Array(String)')})"
        # TODO: We should also pull out id-masks from the dynamic query

        raw_sql = f"""
        SELECT {select_fields_sql}
        FROM calls_merged
        WHERE project_id = {_param_slot(project_param, 'String')}
        {id_mask_sql}
        {id_subquery_sql}
        GROUP BY (project_id, id)
        {having_filter_sql}
        {order_by_sql}
        {limit_sql}
        {offset_sql}
        """

        return _safely_format_sql(raw_sql)


ALLOWED_CALL_FIELDS = {
    "project_id": CallsMergedField(field="project_id"),
    "id": CallsMergedField(field="id"),
    "trace_id": CallsMergedAggField(field="trace_id", agg_fn="any"),
    "parent_id": CallsMergedAggField(field="parent_id", agg_fn="any"),
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
    "deleted_at": CallsMergedAggField(field="deleted_at", agg_fn="any"),
    "display_name": CallsMergedAggField(field="display_name", agg_fn="argMaxMerge"),
}


def get_field_by_name(name: str) -> CallsMergedField:
    if name not in ALLOWED_CALL_FIELDS:
        field_parts = name.split(".")
        start_part = field_parts[0]
        dumped_start_part = start_part + "_dump"
        if dumped_start_part in ALLOWED_CALL_FIELDS:
            field = ALLOWED_CALL_FIELDS[dumped_start_part]
            if isinstance(field, CallsMergedDynamicField):
                if len(field_parts) > 1:
                    return field.with_path(field_parts[1:])
            return field
        raise InvalidFieldError(f"Field {name} is not allowed")
    return ALLOWED_CALL_FIELDS[name]


class FilterToConditions(BaseModel):
    conditions: list[str]
    fields_used: set[str]


def process_query_to_conditions(
    query: tsi.Query,
    param_builder: ParamBuilder,
    table_alias: str,
) -> FilterToConditions:
    """Converts a Query to a list of conditions for a clickhouse query."""
    conditions = []
    raw_fields_used = set()

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
            raise ValueError(f"Unknown operation type: {operation}")

        return cond

    def process_operand(operand: "tsi_query.Operand") -> str:
        if isinstance(operand, tsi_query.LiteralOperation):
            return _param_slot(
                param_builder.add_param(operand.literal_),  # type: ignore
                python_value_to_ch_type(operand.literal_),
            )
        elif isinstance(operand, tsi_query.GetFieldOperator):
            structured_field = get_field_by_name(operand.get_field_)
            field = structured_field.as_sql(param_builder, table_alias)
            raw_fields_used.add(structured_field.field)
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
            raise ValueError(f"Unknown operand type: {operand}")

    filter_cond = process_operation(query.expr_)

    conditions.append(filter_cond)

    return FilterToConditions(conditions=conditions, fields_used=raw_fields_used)


def process_calls_filter_to_conditions(
    filter: tsi.CallsFilter,
    param_builder: ParamBuilder,
    table_alias: str,
) -> list[str]:
    """Converts a CallsFilter to a list of conditions for a clickhouse query."""
    conditions: list[str] = []

    if filter.op_names:
        # We will build up (0 or 1) + N conditions for the op_version_refs
        # If there are any non-wildcarded names, then we at least have an IN condition
        # If there are any wildcarded names, then we have a LIKE condition for each

        or_conditions: typing.List[str] = []

        non_wildcarded_names: typing.List[str] = []
        wildcarded_names: typing.List[str] = []
        for name in filter.op_names:
            if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
                wildcarded_names.append(name)
            else:
                non_wildcarded_names.append(name)

        if non_wildcarded_names:
            or_conditions.append(
                f"{get_field_by_name('op_name').as_sql(param_builder, table_alias)} IN {_param_slot(param_builder.add_param(non_wildcarded_names), 'Array(String)')}"
            )

        for name in wildcarded_names:
            like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + ":%"
            or_conditions.append(
                f"{get_field_by_name('op_name').as_sql(param_builder, table_alias)} LIKE {_param_slot(param_builder.add_param(like_name), 'String')}"
            )

        if or_conditions:
            conditions.append(combine_conditions(or_conditions, "OR"))

    if filter.input_refs:
        conditions.append(
            f"hasAny({get_field_by_name('input_refs').as_sql(param_builder, table_alias)}, {_param_slot(param_builder.add_param(filter.input_refs), 'Array(String)')})"
        )

    if filter.output_refs:
        conditions.append(
            f"hasAny({get_field_by_name('output_refs').as_sql(param_builder, table_alias)}, {_param_slot(param_builder.add_param(filter.output_refs), 'Array(String)')})"
        )

    if filter.parent_ids:
        conditions.append(
            f"{get_field_by_name('parent_id').as_sql(param_builder, table_alias)} IN {_param_slot(param_builder.add_param(filter.parent_ids), 'Array(String)')}"
        )

    if filter.trace_ids:
        conditions.append(
            f"{get_field_by_name('trace_id').as_sql(param_builder, table_alias)} IN {_param_slot(param_builder.add_param(filter.trace_ids), 'Array(String)')}"
        )

    if filter.call_ids:
        conditions.append(
            f"{get_field_by_name('id').as_sql(param_builder, table_alias)} IN {_param_slot(param_builder.add_param(filter.call_ids), 'Array(String)')}"
        )

    if filter.trace_roots_only:
        conditions.append(
            f"{get_field_by_name('parent_id').as_sql(param_builder, table_alias)} IS NULL"
        )

    if filter.wb_user_ids:
        conditions.append(
            f"{get_field_by_name('wb_user_id').as_sql(param_builder, table_alias)} IN {_param_slot(param_builder.add_param(filter.wb_user_ids), 'Array(String)')})"
        )

    if filter.wb_run_ids:
        conditions.append(
            f"{get_field_by_name('wb_run_id').as_sql(param_builder, table_alias)} IN {_param_slot(param_builder.add_param(filter.wb_run_ids), 'Array(String)')})"
        )

    return conditions


def _param_slot(param_name: str, param_type: str) -> str:
    """Helper function to create a parameter slot for a clickhouse query."""
    return f"{{{param_name}:{param_type}}}"


def _safely_format_sql(
    sql: str,
) -> str:
    """Safely format a SQL string with parameters."""
    try:
        return sqlparse.format(sql, reindent=True)
    except:
        logger.info(f"Failed to format SQL: {sql}")
        return sql
