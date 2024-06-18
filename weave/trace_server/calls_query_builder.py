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

# TODO: Consider latency ordering

class CallsMergedField(BaseModel):
    field: str

    def as_sql(self, table_alias: str = "calls_merged", pb: ParamBuilder) -> str:
        return f"{table_alias}.{self.field}"
    
    def as_select_sql(self, table_alias: str = "calls_merged") -> str:
        return f"{self.as_sql(table_alias)} AS {self.field}"

class CallsMergedAggField(CallsMergedField):
    agg_fn: str

    def as_sql(self, table_alias: str = "calls_merged", pb: ParamBuilder) -> str:
        inner = super().as_sql(table_alias)
        return f"{self.agg_fn}({inner})"

class CallsMergedDynamicField(CallsMergedAggField):
    extra_path: Optional[list[str]] = None

    def as_sql(self, table_alias: str = "calls_merged", pb: ParamBuilder) -> str:
        res = super().as_sql(table_alias)
        if self.extra_path:
            param_name = pb.add_param(_quote_json_path(json_path))
            return f"JSON_VALUE({res}, '$.{{{json_path_param_name}}:String}')"
        return res

    def as_select_sql(self, table_alias: str = "calls_merged", pb: ParamBuilder) -> str:
        raise NotImplementedError("Dynamic fields cannot be selected directly, yet - implement me!")

    def with_path(self, path: list[str]) -> "CallsMergedDynamicField":
        extra_path = [*(self.extra_path or [])]
        extra_path.extend(path)
        return CallsMergedDynamicField(
            field=self.field,
            agg_fn=self.agg_fn,
            extra_path=extra_path
        )

def _quote_json_path(parts: list[str]) -> str:
    """Helper function to quote a json path for use in a clickhouse query. Moreover,
    this converts index operations from dot notation (conforms to Mongo) to bracket
    notation (required by clickhouse)

    See comments on `GetFieldOperator` for current limitations
    """
    parts_final = []
    for part in parts:
        append_part = '."' + part + '"'
        if len(part) > 0 and part[0] != 0:
            try:
                int(part)
                append_part = "[" + part + "]"
            except ValueError:
                pass
        parts_final.append(append_part)
    return "$" + "".join(parts_final)


class SortField(BaseModel):
    field: CallsMergedField
    direction: typing.Literal["ASC", "DESC"]

    def as_sql(self, table_alias: str = "calls_merged", pb: ParamBuilder) -> str:
        return f"{self.field.as_sql(table_alias)} {self.direction}"

class Condition(BaseModel):
    query: Query
    _consumed_fields: typing.Optional[list[CallsMergedField]] = None

    def as_sql(self, table_alias: str = "calls_merged", pb: ParamBuilder) -> str:
        raise NotImplementedError("Implement me!")

    def get_consumed_fields(self) -> List[CallsMergedField]:
        if self._consumed_fields is None:
            raise NotImplementedError("Implement me!")
        return self._consumed_fields

class CallsQuery(BaseModel):
    """Critical to be injection safe!"""
    project_id: str
    select_fields: List[CallsMergedField] = Field(default_factory=list)
    filter_conditions: List[Condition] = Field(default_factory=list)
    order_fields: List[SortField] = Field(default_factory=list)
    limit: Optional[int] = None
    offset: Optional[int] = None

    def add_field(self, field: str):
        self.select_fields.append(get_field_by_name(field))
        return self

    def add_condition(self, query: Query):
        self.filter_conditions.append(Condition(query=query))
        return self

    def add_order(self, field: str, direction: str):
        direction = direction.upper()
        if direction not in ["ASC", "DESC"]:
            raise ValueError(f"Direction {direction} is not allowed")
        self.order_fields.append(SortField(field=get_field_by_name(field), direction=direction))
        return self

    def set_limit(self, limit: int):
        if limit < 0:
            raise ValueError("Limit must be a positive integer")
        if self.limit is not None:
            raise ValueError("Limit can only be set once")
        self.limit = limit
        return self
    
    def set_offset(self, offset: int):
        if offset < 0:
            raise ValueError("Offset must be a positive integer")
        if self.offset is not None:
            raise ValueError("Offset can only be set once")
        self.offset = offset
        return self

    def clone(self):
        return CallsQuery(
            project_id=self.project_id,
            select_fields=self.select_fields.copy(),
            filter_conditions=self.filter_conditions.copy(),
            limit=self.limit,
            offset=self.offset
        )

    def as_sql(self, pb: ParamBuilder) -> str:
        outer_query = self.clone()
        outer_query.filter_conditions = []
        filtered_calls_query = CallsQuery(self.project_id).add_field("id").add_condition(not_deleted_at)
        for cond in self.filter_conditions:
            consumed_fields = cond.get_consumed_fields()
            if not any([isinstance(field, CallsMergedDynamicField) for field in consumed_fields]):
                filtered_calls_query.add_condition(cond)
            else:
                outer_query.add_condition(cond)

        dynamic_order_fields = [field for field in self.order_fields if isinstance(field.field, CallsMergedDynamicField)]
        if len(dynamic_order_fields) == 0 and self.limit is not None and len(self.outer_query.filter_conditions) == 0:
            filtered_calls_query.set_limit(self.limit)
            if self.offset is not None:
                filtered_calls_query.set_offset(self.offset)
            filtered_calls_query.order_fields = self.order_fields
            outer_query.offset = None
            outer_query.limit = None

        dynamic_select_fields = [field for field in self.select_fields if isinstance(field, CallsMergedDynamicField)]
        if len(dynamic_select_fields) == 0:
            filtered_calls_query.select_fields = self.select_fields
            return filtered_calls_query._as_sql_base_format(pb)

        assert filtered_calls_query.limit is None
        assert filtered_calls_query.offset is None
        assert len(filtered_calls_query.order_fields) == 0

        # TODO: Recursive expansion goes here

        return f"""
        WITH filtered_calls AS ({filtered_calls_query._as_sql_base_format(pb)})
        {outer_query._as_sql_base_format(pb, id_subquery_name="filtered_calls")}
        """

    def _as_sql_base_format(self, pb: ParamBuilder, id_subquery_name: Optional[str] =  None) -> str:
        select_fields_sql = ", ".join([field.as_select_sql() for field in self.select_fields])

        having_filter_sql = ""
        if len(self.filter_conditions) > 0:
            having_filter_sql = "HAVING " + " AND ".join([condition.as_sql(pb) for condition in self.filter_conditions])

        order_by_sql = ""
        if len(self.order_fields) > 0:
            order_by_sql = "ORDER BY "  + ", ".join([order_field.as_sql() for order_field in self.order_fields])

        limit_sql = ""
        if self.limit is not None:
            limit_sql = f"LIMIT {self.limit}"

        offset_sql = ""
        if self.offset is not None:
            offset_sql = f"OFFSET {self.offset}"

        id_subquery_sql = ""
        if id_subquery_name is not None:
            id_subquery_sql = "AND id IN (SELECT id FROM {id_subquery_name})"

        return f"""
        SELECT {select_fields_sql}
        FROM calls_merged
        WHERE project_id = {self.project_id}
        {id_subquery_sql}                     -- optional
        GROUP BY (project_id, id)
        {having_filter_sql}                   -- optional 
        {order_by_sql}                        -- optional
        {limit_sql}                           -- optional
        {offset_sql}                          -- optional
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
        if dumped_start_part in dynamic_fields:
            field = dynamic_fields[dumped_start_part]
            if len(field_parts) > 1:
                return field.with_path(field_parts[1:])
        raise ValueError(f"Field {name} is not allowed")
    return allowed_fields[name]

