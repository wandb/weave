"""Hardcoded filter processing for the calls query builder.

Converts CallsFilter objects into SQL WHERE clause fragments for ClickHouse.
These filters are "hardcoded" in the sense that they map directly from
CallsFilter fields to optimized SQL conditions, rather than going through
the generic query AST processing in conditions.py.
"""

from pydantic import BaseModel

from weave.shared.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    split_exact_and_wildcard_values,
    wildcard_version_value_to_ref_prefix,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.fields import (
    CallsMergedAggField,
    get_field_by_name,
)
from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.orm import ParamBuilder, combine_conditions
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.trace_server_common import assert_parameter_length_less_than_max


class HardCodedFilter(BaseModel):
    # serves as a sql-generation utility for CallsFilter, and should stay in sync with the CallsFilter class.
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
        self,
        pb: ParamBuilder,
        table_alias: str,
        use_agg_fn: bool = True,
        read_table: "ReadTable" = ReadTable.CALLS_MERGED,
    ) -> str:
        return combine_conditions(
            process_calls_filter_to_conditions(
                self.filter,
                pb,
                table_alias,
                use_agg_fn=use_agg_fn,
                read_table=read_table,
            ),
            "AND",
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
    read_table: ReadTable = ReadTable.CALLS_MERGED,
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

    thread_null = thread_id_field.null_check_sql(
        param_builder, table_alias, read_table, use_agg_fn=False
    )
    return f" AND ({thread_cond} OR {thread_null})"


def process_turn_id_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
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

    turn_null = turn_id_field.null_check_sql(
        param_builder, table_alias, read_table, use_agg_fn=False
    )
    return f" AND ({turn_cond} OR {turn_null})"


def process_trace_roots_only_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
) -> str:
    """Pulls out the trace_roots_only and returns a sql string if there are any trace_roots_only."""
    if hardcoded_filter is None or not hardcoded_filter.filter.trace_roots_only:
        return ""

    parent_id_field = get_field_by_name("parent_id")
    if not isinstance(parent_id_field, CallsMergedAggField):
        raise TypeError("parent_id is not an aggregate field")

    parent_null = parent_id_field.null_check_sql(
        param_builder, table_alias, read_table, use_agg_fn=False
    )
    return f"AND ({parent_null})"


def process_parent_ids_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
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

    parent_null = parent_id_field.null_check_sql(
        param_builder, table_alias, read_table, use_agg_fn=False
    )
    return f"AND ({parent_ids_sql} OR {parent_null})"


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
        ref_filter_sql = combine_conditions(
            _build_clickhouse_ref_match_conditions(refs, field_sql, param_builder),
            "OR",
        )
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
    read_table: "ReadTable" = ReadTable.CALLS_MERGED,
) -> str:
    """Processes object ref fields to an optimization sql string."""
    if not object_ref_fields_consumed:
        return ""

    # Optimization: narrow the scan to rows that actually carry the refs we
    # are filtering on.
    #
    # calls_merged has split start/end rows, so we must also include
    # "naked call end" rows (started_at IS NULL) for input ref filters and
    # "naked call start" rows (ended_at IS NULL) for output ref filters.
    #
    # calls_complete has one complete row per call -- started_at is always
    # set (non-nullable, no sentinel) and ended_at uses a sentinel for
    # unfinished calls.  We still include the ended_at sentinel fallback
    # for output refs so unfinished calls aren't silently dropped.
    refs_filter_opt_sql = ""
    if "inputs_dump" in object_ref_fields_consumed:
        if read_table == ReadTable.CALLS_COMPLETE:
            refs_filter_opt_sql += f"AND (length({table_alias}.input_refs) > 0)"
        else:
            started_at_field = get_field_by_name("started_at")
            started_at_null = started_at_field.null_check_sql(
                param_builder, table_alias, read_table, use_agg_fn=False
            )
            refs_filter_opt_sql += (
                f"AND (length({table_alias}.input_refs) > 0 OR {started_at_null})"
            )
    if "output_dump" in object_ref_fields_consumed:
        ended_at_field = get_field_by_name("ended_at")
        ended_at_null = ended_at_field.null_check_sql(
            param_builder, table_alias, read_table, use_agg_fn=False
        )
        refs_filter_opt_sql += (
            f"AND (length({table_alias}.output_refs) > 0 OR {ended_at_null})"
        )

    return refs_filter_opt_sql


def process_wb_run_ids_filter_to_sql(
    hardcoded_filter: HardCodedFilter | None,
    param_builder: ParamBuilder,
    table_alias: str,
    read_table: ReadTable = ReadTable.CALLS_MERGED,
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

    wb_run_null = wb_run_id_field.null_check_sql(
        param_builder, table_alias, read_table, use_agg_fn=False
    )
    return f"AND ({wb_run_id_filter_sql} OR {wb_run_null})"


def process_calls_filter_to_conditions(
    filter: tsi.CallsFilter,
    param_builder: ParamBuilder,
    table_alias: str,
    use_agg_fn: bool = True,
    read_table: "ReadTable" = ReadTable.CALLS_MERGED,
) -> list[str]:
    """Converts a CallsFilter to a list of conditions for a clickhouse query.

    Excludes the op_name, which is handled separately.

    Args:
        filter: The CallsFilter to convert
        param_builder: Parameter builder for query parameterization
        table_alias: The table alias to use in SQL
        use_agg_fn: Whether to wrap fields in aggregate functions
        read_table: Which table to query (affects null/sentinel semantics)
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
        input_refs_sql = get_field_sql("input_refs")
        conditions.append(
            combine_conditions(
                _build_clickhouse_ref_match_conditions(
                    filter.input_refs, input_refs_sql, param_builder
                ),
                "OR",
            )
        )

    if filter.output_refs:
        assert_parameter_length_less_than_max("output_refs", len(filter.output_refs))
        output_refs_sql = get_field_sql("output_refs")
        conditions.append(
            combine_conditions(
                _build_clickhouse_ref_match_conditions(
                    filter.output_refs, output_refs_sql, param_builder
                ),
                "OR",
            )
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


def _build_clickhouse_ref_match_conditions(
    refs: list[str], field_sql: str, param_builder: ParamBuilder
) -> list[str]:
    exact_refs, wildcard_refs = split_exact_and_wildcard_values(refs)
    or_conditions: list[str] = []
    if exact_refs:
        or_conditions.append(
            f"hasAny({field_sql}, {param_slot(param_builder.add_param(exact_refs), 'Array(String)')})"
        )
    for ref in wildcard_refs:
        ref_prefix = wildcard_version_value_to_ref_prefix(ref)
        or_conditions.append(
            f"arrayExists(x -> startsWith(x, {param_slot(param_builder.add_param(ref_prefix), 'String')}), {field_sql})"
        )
    return or_conditions
