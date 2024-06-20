"""
As opposed to the orm.py, this module is responsible for building a hand-tuned
query for the calls table. THis is preferred for now as it is easier to reason
about and ...

The "calls table" actually refers to `calls_merged`.

To query the `calls_merged` table efficiently, there are 4 possible ways to do
it, each with increasing complexity:

Level 1:

* Selected Fields: No "dynamic" fields
* Filter Fields: No "dynamic" fields
* Sort Fields: No "dynamic" fields

Level 2:

* Selected Fields: includes "dynamic" fields
* Filter Fields: No "dynamic" fields
* Sort Fields: No "dynamic" fields & includes a limit

Level 3:

* Selected Fields: includes "dynamic" fields
* Filter Fields/Sort: includes "dynamic" fields

Level 4:

* Filter/Sort Fields: include joined fields (read: ref expansion or
feedback)


For the sake of this document, we will use the following definitions:

Field Categories: * STATIC_FIELDS: Fields that have known, constant size and are
implied to be relatively inexpensive to load into memory
    * INDEXED_FIELDS: Fields that are indexed
        * As of this writing, `project_id` and `id` are indexed
        * Note: all indexed fields are static fields, but not all static fields
          are indexed fields!
        * Note2: when querying, INDEXED_FIELDS are always grouped but all other
          fields need to have aggregation functions
* DYNAMIC_FIELDS: Fields that have user-defined size and are implied to be
  relatively expensive to load into memory
    * As of this writing, `inputs`, `output`, `attributes`, and `summary` are
      dynamic fields
* JOINED_FIELDS: Fields that are joined from another table
    * As of this writing, this refers to:
        * REFERENCED_FIELDS: Fields whose values are the result of at least 1
          reference expansion
            * Note: All referenced fields are dynamic fields, but not all
              dynamic fields are referenced fields! However, we
            * cannot know at query building time if a dynamic field is a
              referenced field or not!
        * FEEDBACK_FIELDS: Fields whose values are stored in the feedback table.
            * Note: we do not yet support these, but we will in the very near
              future

Query Components * SELECT_FIELDS: The fields that are selected in the query.
This set of fields is partitioned into:
    * SELECT_STATIC_FIELDS
    * SELECT_DYNAMIC_FIELDS
* FILTER_FIELDS: The fields that are used to filter the query. This set of
  fields is partitioned into (by reformatting the query as ANDS of clauses):
    * FILTER_STATIC_FIELDS
    * FILTER_DYNAMIC_FIELDS
* SORT_FIELDS: The fields that are used to order the query. This set of fields is
  partitioned into:
    * SORT_STATIC_FIELDS
    * SORT_DYNAMIC_FIELDS

The canonical query is as follows. Note: as a hard rule, we always require a
project_id to be passed in as a filter.

NEVER USE THIS:
```sql
SELECT {SELECT_FIELDS}
FROM calls_merged
GROUP BY (project_id, id)
HAVING
    project_id = {project_id}
    AND isNull(any(deleted_at))
    AND {FILTER_FIELDS}             -- optional
ORDER BY {SORT_FIELDS}              -- optional
LIMIT {limit}                       -- optional
OFFSET {offset}                     -- optional
```

The above query however is quite naive and will be too slow in practice. The first
modification is to move the `project_id` filter to the `WHERE` clause. This way we
avoid bring the entire table into memory and then filtering it. You will see this
is a trend: avoid loading data into memory:

BASE QUERY:
```sql
SELECT {SELECT_FIELDS}
FROM calls_merged
WHERE project_id = {project_id}
GROUP BY (project_id, id)
HAVING
    isNull(any(deleted_at))
    AND {FILTER_FIELDS}             -- optional
ORDER BY {SORT_FIELDS}              -- optional
LIMIT {limit}                       -- optional
OFFSET {offset}                     -- optional
```

This is the base query. While in theory it is good, in practice, we never actually use
this case (but that is just because of current features). You will see why in a moment.

The next modification is to push any STATIC_FILTER_FIELDS into a nested query:

PRE-FILTERED QUERY:
```sql
WITH filtered_calls AS (
    SELECT id
    FROM calls_merged
    WHERE project_id = {project_id}
    GROUP BY (project_id, id)
    HAVING
        isNull(any(deleted_at))
        AND {STATIC_FILTER_FIELDS}
)
SELECT {SELECT_FIELDS}
FROM calls_merged
WHERE id IN (filtered_calls)        -- Consider using an INNER JOIN here
GROUP BY (project_id, id)
HAVING {FILTER_DYNAMIC_FIELDS}      -- optional
ORDER BY {SORT_FIELDS}              -- optional
LIMIT {limit}                       -- optional
OFFSET {offset}                     -- optional
```

Now, under the very specific condition that:
a) we have no `FILTER_DYNAMIC_FIELDS`
b) we have no `SORT_DYNAMIC_FIELDS`
c) we have a limit
Then we can push the order into the inner query:

PRE-ORDERED/FILTERED QUERY:
```sql
WITH ordered_filtered_calls AS (
    SELECT id
    FROM calls_merged
    WHERE project_id = {project_id}
    GROUP BY (project_id, id)
    HAVING
        isNull(any(deleted_at))
        AND {STATIC_FILTER_FIELDS}  -- optional
    ORDER BY {SORT_FIELDS}
    LIMIT {limit}
    OFFSET {offset}                 -- optional
)
SELECT {SELECT_FIELDS}
FROM calls_merged
WHERE id IN (ordered_filtered_calls) -- Consider using an INNER JOIN here
GROUP BY (project_id, id)
ORDER BY {SORT_FIELDS}              -- still required to repeat
```

Now, we can do even better! If the requested columns do not contain any dynamic fields,
can avoid the inner query altogether (notice, this is equivalent to the base query):

STATIC QUERY:
```sql
SELECT {SELECT_FIELDS}
FROM calls_merged
WHERE project_id = {project_id}
GROUP BY (project_id, id)
HAVING
    isNull(any(deleted_at))
    AND {FILTER_FIELDS}             -- optional
ORDER BY {SORT_FIELDS}              -- optional
LIMIT {limit}                       -- optional
OFFSET {offset}                     -- optional
```

Now, we have drilled down to 3 possible queries... now, we have to handle expansions.

EXPANDED QUERY:
```sql
WITH filtered_calls AS (
    SELECT id
    FROM calls_merged
    WHERE project_id = {project_id}
    GROUP BY (project_id, id)
    HAVING
        isNull(any(deleted_at))
        AND {STATIC_FILTER_FIELDS}
),
expanded_calls AS (
    SELECT project_id, id, {FIELDS_TO_FILTER}, {FIELDS_TO_SORT}
    -- RECURSIVE EXPANSION OF `filtered_calls`
)
SELECT {SELECT_FIELDS}
FROM calls_merged
WHERE id IN (expanded_calls)        -- This almost certainly needs to be a JOIN
GROUP BY (project_id, id)
HAVING {FILTER_FIELDS}              -- optional
ORDER BY {SORT_FIELDS}              -- optional
LIMIT {limit}                       -- optional
OFFSET {offset}                     -- optional
```

BASE QUERY -- (if filters contain at least one static field clause) --> PRE-FILTERED QUERY
PRE-FILTERED QUERY -- (if order fields are static and limit is present) --> PRE-ORDERED/FILTERED QUERY
PRE-FILTERED QUERY -- (if all select fields are static) --> STATIC QUERY
PRE-FILTERED QUERY -- (if expansions are present) --> EXPANDED QUERY


Now that all this is written, i think an alternative implementation is:
1. Start with the EXPANDED QUERY.
2. If there are no expansions needed, then move to the PRE-FILTERED QUERY.
3. If order fields are static and limit is present, then move to the PRE-ORDERED/FILTERED QUERY.
4. If all select fields are static, then move to the STATIC QUERY.

"""

# PR TODO:
# - [ ] When legacy filters or query conditions are an ID mask, we can further optimize the subquery
# Refactors:
# - [ ] Look for dead code in this file
# - [ ] Reconcile the differences between ORM and these implementations (ideally push them down into there)
#   - [ ] All methods in this file are unique
#           - [ ] quote_json_path_parts -> quote_json_path
#           - [ ] process_query_to_conditions -> _process_query_to_conditions
#           - [ ] transform_external_field_to_internal_field -> _transform_external_field_to_internal_field
#           - [ ] combine_conditions -> _combine_conditions
#           - [ ] _python_value_to_ch_type -> _python_value_to_ch_type
# - [ ] `process_calls_filter_to_conditions` still uses hard coded `calls_merged` columns - bad!
# Considerations:
# - [ ] Consider column selection
# - [ ] Consider how we will do latency order/filter
# - [ ] Consider how we will do feedback fields

import typing

from pydantic import BaseModel, Field

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
)


class CallsMergedField(BaseModel):
    field: str

    def as_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        return f"{table_alias}.{self.field}"

    def as_select_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        return f"{self.as_sql(pb, table_alias)} AS {self.field}"


class CallsMergedAggField(CallsMergedField):
    agg_fn: str

    def as_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        inner = super().as_sql(pb, table_alias)
        return f"{self.agg_fn}({inner})"


class CallsMergedDynamicField(CallsMergedAggField):
    extra_path: typing.Optional[list[str]] = None

    def as_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        res = super().as_sql(pb, table_alias)
        if self.extra_path:
            param_name = pb.add_param(quote_json_path_parts(self.extra_path))
            return f"JSON_VALUE({res}, {_param_slot(param_name, 'String')})"
        return f"JSON_VALUE({res}, '$')"

    def as_select_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        return super().as_sql(pb, table_alias)

    def with_path(self, path: list[str]) -> "CallsMergedDynamicField":
        extra_path = [*(self.extra_path or [])]
        extra_path.extend(path)
        return CallsMergedDynamicField(
            field=self.field, agg_fn=self.agg_fn, extra_path=extra_path
        )


def quote_json_path_parts(parts: list[str]) -> str:
    """Helper function to quote a json path for use in a clickhouse query. Moreover,
    this converts index operations from dot notation (conforms to Mongo) to bracket
    notation (required by clickhouse)

    See comments on `GetFieldOperator` for current limitations
    """

    def quote_part(part: str) -> str:
        if len(part) > 0 and part[0] != 0:
            try:
                int(part)
                return "[" + part + "]"
            except ValueError:
                pass
        return '."' + part + '"'

    return "$" + "".join([quote_part(p) for p in parts])


class SortField(BaseModel):
    field: CallsMergedField
    direction: typing.Literal["ASC", "DESC"]

    def as_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        return f"{self.field.as_sql(pb, table_alias)} {self.direction}"


class Condition(BaseModel):
    operand: "tsi_query.Operand"
    _consumed_fields: typing.Optional[list[CallsMergedField]] = None

    def as_sql(self, pb: ParamBuilder, table_alias: str = "calls_merged") -> str:
        conditions = process_query_to_conditions(
            tsi_query.Query.model_validate({"$expr": {"$and": [self.operand]}}), pb
        )
        if self._consumed_fields is None:
            self._consumed_fields = []
            for field in conditions.raw_fields:
                self._consumed_fields.append(get_field_by_name(field))
        return combine_conditions(conditions.conditions, "AND")

    def get_consumed_fields(self) -> list[CallsMergedField]:
        if self._consumed_fields is None:
            self._consumed_fields = []
            conditions = process_query_to_conditions(
                tsi_query.Query.model_validate({"$expr": {"$and": [self.operand]}}),
                ParamBuilder(),
            )
            for field in conditions.raw_fields:
                self._consumed_fields.append(get_field_by_name(field))

        return self._consumed_fields


class CallsQuery(BaseModel):
    """Critical to be injection safe!"""

    project_id: str
    select_fields: list[CallsMergedField] = Field(default_factory=list)
    query_conditions: list[Condition] = Field(default_factory=list)
    legacy_filter: typing.Optional[tsi._CallsFilter] = None
    order_fields: list[SortField] = Field(default_factory=list)
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None

    def add_field(self, field: str) -> "CallsQuery":
        self.select_fields.append(get_field_by_name(field))
        return self

    def add_condition(self, operand: "tsi_query.Operand") -> "CallsQuery":
        if isinstance(operand, tsi_query.AndOperation):
            if len(operand.and_) == 0:
                raise ValueError("Empty AND operation")
            else:
                for op in operand.and_:
                    self.add_condition(op)
        else:
            self.query_conditions.append(Condition(operand=operand))
        return self

    def set_legacy_filter(self, filter: tsi._CallsFilter) -> "CallsQuery":
        self.legacy_filter = filter
        return self

    def add_order(self, field: str, direction: str) -> "CallsQuery":
        direction = direction.upper()
        if direction not in ["ASC", "DESC"]:
            raise ValueError(f"Direction {direction} is not allowed")
        direction = typing.cast(typing.Literal["ASC", "DESC"], direction)
        self.order_fields.append(
            SortField(field=get_field_by_name(field), direction=direction)
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
            legacy_filter=self.legacy_filter,
            limit=self.limit,
            offset=self.offset,
        )

    def as_sql(self, pb: ParamBuilder) -> str:
        """
        This is the main entry point for building the query. This method will
        determine the optimal query to build based on the fields and conditions
        that have been set.
        """

        # TODO: Really be sure of and test this query optimizer
        outer_query = self.clone()
        outer_query.query_conditions = []
        not_deleted = tsi_query.EqOperation.model_validate(
            {"$eq": [{"$getField": "deleted_at"}, {"$literal": None}]}
        )
        filtered_calls_query = (
            CallsQuery(project_id=self.project_id)
            .add_field("id")
            .add_condition(not_deleted)
        )
        for cond in self.query_conditions:
            consumed_fields = cond.get_consumed_fields()
            if not any(
                [
                    isinstance(field, CallsMergedDynamicField)
                    for field in consumed_fields
                ]
            ):
                filtered_calls_query.add_condition(cond.operand)
            else:
                outer_query.add_condition(cond.operand)

        # All legacy filters are non-dynamic
        if self.legacy_filter is not None:
            filtered_calls_query.set_legacy_filter(self.legacy_filter)
            outer_query.legacy_filter = None

        dynamic_order_fields = [
            field
            for field in self.order_fields
            if isinstance(field.field, CallsMergedDynamicField)
        ]
        if (
            len(dynamic_order_fields) == 0
            and self.limit is not None
            and len(outer_query.query_conditions) == 0
        ):
            filtered_calls_query.set_limit(self.limit)
            if self.offset is not None:
                filtered_calls_query.set_offset(self.offset)
            filtered_calls_query.order_fields = self.order_fields
            outer_query.offset = None
            outer_query.limit = None

        dynamic_select_fields = [
            field
            for field in self.select_fields
            if isinstance(field, CallsMergedDynamicField)
        ]
        if len(dynamic_select_fields) == 0:
            filtered_calls_query.select_fields = self.select_fields
            return filtered_calls_query._as_sql_base_format(pb)

        # TODO: What was i thinking here?
        # assert filtered_calls_query.limit is None
        # assert filtered_calls_query.offset is None
        # assert len(filtered_calls_query.order_fields) == 0

        return f"""
        WITH filtered_calls AS ({filtered_calls_query._as_sql_base_format(pb)})
        {outer_query._as_sql_base_format(pb, id_subquery_name="filtered_calls")}
        """

    def _as_sql_base_format(
        self, pb: ParamBuilder, id_subquery_name: typing.Optional[str] = None
    ) -> str:
        select_fields_sql = ", ".join(
            [field.as_select_sql(pb) for field in self.select_fields]
        )

        having_filter_sql = ""
        query_conditions = []
        if len(self.query_conditions) > 0:
            query_conditions.extend([c.as_sql(pb) for c in self.query_conditions])
        if self.legacy_filter is not None:
            # TODO: `process_calls_filter_to_conditions` should not be used here, move into the correct class
            filter_conditions = process_calls_filter_to_conditions(
                self.legacy_filter, pb
            )
            query_conditions.extend(filter_conditions.conditions)

        if len(query_conditions) > 0:
            having_filter_sql = "HAVING " + " AND ".join(
                [condition for condition in query_conditions]
            )

        order_by_sql = ""
        if len(self.order_fields) > 0:
            order_by_sql = "ORDER BY " + ", ".join(
                [order_field.as_sql(pb) for order_field in self.order_fields]
            )

        limit_sql = ""
        if self.limit is not None:
            limit_sql = f"LIMIT {self.limit}"

        offset_sql = ""
        if self.offset is not None:
            offset_sql = f"OFFSET {self.offset}"

        id_subquery_sql = ""
        if id_subquery_name is not None:
            id_subquery_sql = f"AND id IN (SELECT id FROM {id_subquery_name})"

        project_param = pb.add_param(self.project_id)

        return f"""
        SELECT {select_fields_sql}
        FROM calls_merged
        WHERE project_id = {_param_slot(project_param, 'String')}
        {id_subquery_sql}
        GROUP BY (project_id, id)
        {having_filter_sql}
        {order_by_sql}
        {limit_sql}
        {offset_sql}
        """


allowed_fields = {
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
    if name not in allowed_fields:
        field_parts = name.split(".")
        start_part = field_parts[0]
        dumped_start_part = start_part + "_dump"
        if dumped_start_part in allowed_fields:
            field = allowed_fields[dumped_start_part]
            if isinstance(field, CallsMergedDynamicField):
                if len(field_parts) > 1:
                    return field.with_path(field_parts[1:])
            return field
        raise ValueError(f"Field {name} is not allowed")
    return allowed_fields[name]


# ----- Below this line is old implementation ----
class FilterToConditions(BaseModel):
    conditions: list[str]
    fields_used: set[str]


def process_query_to_conditions(
    query: tsi.Query,
    param_builder: ParamBuilder,
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
                _python_value_to_ch_type(operand.literal_),
            )
        elif isinstance(operand, tsi_query.GetFieldOperator):
            (
                field,
                _,
                fields_used,
            ) = transform_external_field_to_internal_field(
                operand.get_field_, None, param_builder
            )
            raw_fields_used.update(fields_used)
            return field
        elif isinstance(operand, tsi_query.ConvertOperation):
            field = process_operand(operand.convert_.input)
            convert_to = operand.convert_.to
            if convert_to == "int":
                method = "toInt64OrNull"
            elif convert_to == "double":
                method = "toFloat64OrNull"
            elif convert_to == "bool":
                method = "toUInt8OrNull"
            elif convert_to == "string":
                method = "toString"
            else:
                raise ValueError(f"Unknown cast: {convert_to}")
            return f"{method}({field})"
        elif isinstance(
            operand,
            (
                tsi_query.AndOperation,
                tsi_query.OrOperation,
                tsi_query.NotOperation,
                tsi_query.EqOperation,
                tsi_query.GtOperation,
                tsi_query.GteOperation,
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
    filter: tsi._CallsFilter, param_builder: ParamBuilder
) -> FilterToConditions:
    """Converts a CallsFilter to a list of conditions for a clickhouse query."""
    conditions: list[str] = []
    raw_fields_used = set()

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
                f"any(calls_merged.op_name) IN {_param_slot(param_builder.add_param(non_wildcarded_names), 'Array(String)')}"
            )
            raw_fields_used.add("op_name")

        for name in wildcarded_names:
            like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + ":%"
            or_conditions.append(
                f"any(calls_merged.op_name) LIKE {_param_slot(param_builder.add_param(like_name), 'String')}"
            )
            raw_fields_used.add("op_name")

        if or_conditions:
            conditions.append(combine_conditions(or_conditions, "OR"))

    if filter.input_refs:
        conditions.append(
            f"hasAny(any(calls_merged.input_refs), {_param_slot(param_builder.add_param(filter.input_refs), 'Array(String)')})"
        )
        raw_fields_used.add("input_refs")

    if filter.output_refs:
        conditions.append(
            f"hasAny(any(calls_merged.output_refs), {_param_slot(param_builder.add_param(filter.output_refs), 'Array(String)')})"
        )
        raw_fields_used.add("output_refs")

    if filter.parent_ids:
        conditions.append(
            f"any(calls_merged.parent_id) IN {_param_slot(param_builder.add_param(filter.parent_ids), 'Array(String)')}"
        )
        raw_fields_used.add("parent_id")

    if filter.trace_ids:
        conditions.append(
            f"any(calls_merged.trace_id) IN {_param_slot(param_builder.add_param(filter.trace_ids), 'Array(String)')}"
        )
        raw_fields_used.add("trace_id")

    if filter.call_ids:
        conditions.append(
            f"any(calls_merged.id) IN {_param_slot(param_builder.add_param(filter.call_ids), 'Array(String)')}"
        )
        raw_fields_used.add("id")

    if filter.trace_roots_only:
        conditions.append("any(calls_merged.parent_id) IS NULL")
        raw_fields_used.add("parent_id")

    if filter.wb_user_ids:
        conditions.append(
            f"any(calls_merged.wb_user_id) IN {_param_slot(param_builder.add_param(filter.wb_user_ids), 'Array(String)')})"
        )
        raw_fields_used.add("wb_user_id")

    if filter.wb_run_ids:
        conditions.append(
            f"any(calls_merged.wb_run_id) IN {_param_slot(param_builder.add_param(filter.wb_run_ids), 'Array(String)')})"
        )
        raw_fields_used.add("wb_run_id")

    return FilterToConditions(
        conditions=conditions,
        fields_used=raw_fields_used,
    )


def transform_external_field_to_internal_field(
    field: str,
    cast: typing.Optional[str] = None,
    param_builder: typing.Optional[ParamBuilder] = None,
) -> tuple[str, ParamBuilder, set[str]]:
    """Transforms a request for a dot-notation field to a clickhouse field."""
    param_builder = param_builder or ParamBuilder()
    structured_field = get_field_by_name(field)
    raw_fields_used = set([structured_field.field])

    if isinstance(structured_field, CallsMergedDynamicField):
        if cast == "exists":
            raise ValueError("Cannot cast to exists")
            # field = (
            #     "(JSON_EXISTS(" + field + ", {" + json_path_param_name + ":String}))"
            # )
        else:
            method = "toString"
            if cast is not None:
                if cast == "int":
                    method = "toInt64OrNull"
                elif cast == "float":
                    method = "toFloat64OrNull"
                elif cast == "bool":
                    method = "toUInt8OrNull"
                elif cast == "str":
                    method = "toString"
                else:
                    raise ValueError(f"Unknown cast: {cast}")
            field = f"{method}({structured_field.as_sql(param_builder)})"
    else:
        field = structured_field.as_sql(param_builder)

    return field, param_builder, raw_fields_used


def combine_conditions(conditions: typing.List[str], operator: str) -> str:
    if operator not in ("AND", "OR"):
        raise ValueError(f"Invalid operator: {operator}")
    if len(conditions) == 1:
        return conditions[0]
    combined = f" {operator} ".join(f"({c})" for c in conditions)
    return f"({combined})"


def _param_slot(param_name: str, param_type: str) -> str:
    """Helper function to create a parameter slot for a clickhouse query."""
    return f"{{{param_name}:{param_type}}}"


def _python_value_to_ch_type(value: typing.Any) -> str:
    """Helper function to convert python types to clickhouse types."""
    if isinstance(value, str):
        return "String"
    elif isinstance(value, int):
        return "UInt64"
    elif isinstance(value, float):
        return "Float64"
    elif isinstance(value, bool):
        return "UInt8"
    elif value is None:
        return "Nullable(String)"
    else:
        raise ValueError(f"Unknown value type: {value}")
