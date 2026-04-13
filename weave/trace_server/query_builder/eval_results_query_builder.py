"""Query builder for the /eval_results endpoint.

Generates ClickHouse CTEs for the eval_results CTE chain:
  predict_and_score_calls          → filter to predict-and-score calls, extract row_digest
  predict_and_score_calls_resolved → LEFT JOIN table_rows to resolve dataset-backed inputs
  ranked_digests                   → GROUP BY row_digest, HAVING filters, ROW_NUMBER for sort
  ranked_digest_count              → total matching rows (for pagination metadata)
  page_digests                     → paginated slice of ranked_digests
  page_rows                        → call IDs + resolved_inputs for the page
"""

from functools import partial

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.orm import (
    ParamBuilder,
    _process_query_to_conditions,
    quote_json_path_parts,
    split_escaped_field_path,
)

# SQL CASE expression for extracting row_digest from predict-and-score call inputs.
# Dataset-backed rows: extract digest from the ref URI.
# Inline rows: SHA256 hash of the raw JSON example object.
#
# {inputs_field} is substituted at build time with the correct expression
# (e.g. "any(calls_merged.inputs_dump)" for calls_merged, or
#  "calls_complete.inputs_dump" for calls_complete).
ROW_DIGEST_SQL_TEMPLATE = """CASE
    WHEN position(JSON_VALUE({inputs_field}, '$.example'), '/attr/rows/id/') > 0
    THEN regexpExtract(JSON_VALUE({inputs_field}, '$.example'), '/attr/rows/id/([^/]+)$', 1)
    ELSE hex(SHA256(JSONExtractRaw({inputs_field}, 'example')))
END"""


def _or_any_prefix_matches(op_name_expr: str, op_prefix_params: list[str]) -> str:
    """`position(op_name, p) > 0` OR'd across every prefix param."""
    return " OR ".join(f"position({op_name_expr}, {p}) > 0" for p in op_prefix_params)


def build_predict_and_score_calls_cte(
    project_id_param: str,
    eval_root_ids_param: str,
    op_prefix_params: list[str],
    inputs_field: str,
    read_table: str,
) -> str:
    """Build the predict_and_score_calls CTE SQL.

    Filters to predict-and-score calls that are direct children of eval roots
    and extracts row_digest from inputs. ``op_prefix_params`` must contain
    every known op-name variant (Python/TS imperative snake_case, TS
    non-imperative camelCase); a call matches if any prefix appears in op_name.
    """
    row_digest_expr = ROW_DIGEST_SQL_TEMPLATE.format(inputs_field=inputs_field)
    op_match_where = _or_any_prefix_matches("calls_merged.op_name", op_prefix_params)
    op_match_having = _or_any_prefix_matches(
        "any(calls_merged.op_name)", op_prefix_params
    )

    if read_table == "calls_merged":
        return f"""predict_and_score_calls AS (
    SELECT
        calls_merged.id AS call_id,
        any(calls_merged.parent_id) AS eval_call_id,
        any(calls_merged.inputs_dump) AS inputs_dump,
        any(calls_merged.output_dump) AS output_dump,
        any(calls_merged.summary_dump) AS summary_dump,
        {row_digest_expr} AS row_digest
    FROM calls_merged
    PREWHERE calls_merged.project_id = {project_id_param}
    WHERE (
        calls_merged.parent_id IN {eval_root_ids_param}
        OR calls_merged.parent_id IS NULL
    )
    AND calls_merged.id NOT IN {eval_root_ids_param}
    AND (
        {op_match_where}
        OR calls_merged.op_name IS NULL
    )
    GROUP BY (calls_merged.project_id, calls_merged.id)
    HAVING any(calls_merged.parent_id) IN {eval_root_ids_param}
        AND ({op_match_having})
)"""
    else:
        op_match_calls_complete = _or_any_prefix_matches(
            "calls_complete.op_name", op_prefix_params
        )
        return f"""predict_and_score_calls AS (
    SELECT
        calls_complete.id AS call_id,
        calls_complete.parent_id AS eval_call_id,
        calls_complete.inputs_dump,
        calls_complete.output_dump,
        calls_complete.summary_dump,
        {row_digest_expr} AS row_digest
    FROM calls_complete
    PREWHERE calls_complete.project_id = {project_id_param}
    WHERE calls_complete.parent_id IN {eval_root_ids_param}
      AND calls_complete.id NOT IN {eval_root_ids_param}
      AND ({op_match_calls_complete})
)"""


def build_predict_and_score_calls_resolved_cte(
    project_id_param: str,
) -> str:
    """Build the predict_and_score_calls_resolved CTE SQL.

    LEFT JOINs table_rows to resolve dataset-backed inputs.
    For inline rows, COALESCE falls through to the raw inputs_dump.example.
    """
    return f"""predict_and_score_calls_resolved AS (
    SELECT
        predict_and_score_calls.*,
        COALESCE(
            tr.val_dump,
            JSONExtractRaw(predict_and_score_calls.inputs_dump, 'example')
        ) AS resolved_inputs
    FROM predict_and_score_calls
    LEFT JOIN (
        SELECT project_id, digest, any(val_dump) AS val_dump
        FROM table_rows
        PREWHERE project_id = {project_id_param}
        WHERE digest IN (SELECT row_digest FROM predict_and_score_calls)
        GROUP BY project_id, digest
    ) AS tr ON tr.digest = predict_and_score_calls.row_digest
)"""


def _string_param(pb: ParamBuilder, value: str) -> str:
    """Add a deduplicated string param and return its {name:String} slot."""
    return param_slot(pb.add_param(value), "String")


def resolve_eval_field_to_sql(
    field_path: str,
    pb: ParamBuilder,
    evaluation_call_id: str | None = None,
) -> tuple[str, set[str]]:
    """Translate an eval_results field path to an aggregated ClickHouse SQL expression.

    Used as a field_resolver callback for _process_query_to_conditions and
    for building ORDER BY expressions. Results include aggregate functions
    (avg, any) so they work in HAVING/ORDER BY after GROUP BY row_digest.

    Returns:
        (sql_expression, set of physical columns used)
    """
    if field_path == "row_digest":
        return "row_digest", {"inputs_dump"}

    if field_path.startswith("inputs."):
        remaining = field_path[len("inputs.") :]
        parts = split_escaped_field_path(remaining)
        path = _string_param(pb, quote_json_path_parts(parts))
        inner = f"nullIf(JSON_VALUE(resolved_inputs, {path}), 'null')"
        inner = _wrap_with_eval_scope(inner, evaluation_call_id, pb)
        return f"any({inner})", {"inputs_dump"}

    if field_path.startswith("output."):
        remaining = field_path[len("output.") :]
        parts = ["output"] + split_escaped_field_path(remaining)
        path = _string_param(pb, quote_json_path_parts(parts))
        inner = f"nullIf(JSON_VALUE(output_dump, {path}), 'null')"
        inner = _wrap_with_eval_scope(inner, evaluation_call_id, pb)
        return f"any({inner})", {"output_dump"}

    if field_path.startswith("scores."):
        remaining = field_path[len("scores.") :]
        parts = ["scores"] + split_escaped_field_path(remaining)
        path = _string_param(pb, quote_json_path_parts(parts))
        raw = f"nullIf(JSON_VALUE(output_dump, {path}), 'null')"
        # coerce json booleans ('true'/'false') to numeric before avg
        coerced = f"multiIf({raw} = 'true', '1', {raw} = 'false', '0', {raw})"
        coerced = _wrap_with_eval_scope(coerced, evaluation_call_id, pb)
        return f"avg(toFloat64OrNull({coerced}))", {"output_dump"}

    raise InvalidRequest(
        f"Unsupported eval results field: '{field_path}'. "
        f"Supported prefixes: scores.*, inputs.*, output.*, row_digest."
    )


def _wrap_with_eval_scope(
    inner_sql: str,
    evaluation_call_id: str | None,
    pb: ParamBuilder,
) -> str:
    """Wrap an expression with CASE WHEN eval_call_id = ... to scope to one eval."""
    if evaluation_call_id is None:
        return inner_sql
    id_slot = _string_param(pb, evaluation_call_id)
    return f"CASE WHEN eval_call_id = {id_slot} THEN {inner_sql} ELSE NULL END"


def _make_field_resolver(
    evaluation_call_id: str | None,
) -> partial[tuple[str, set[str]]]:
    """Create a field_resolver callback for _process_query_to_conditions."""
    return partial(resolve_eval_field_to_sql, evaluation_call_id=evaluation_call_id)


def build_sort_expression(
    sort_by: list[tsi.EvalResultsSortBy] | None,
    eval_root_ids: list[str],
    pb: ParamBuilder,
) -> str:
    """Build the ORDER BY expression for ranked_digests.

    Always appends row_digest ASC as a stable tie-breaker.
    When sort_by is None, returns just the tie-breaker.
    """
    if not sort_by:
        return "row_digest ASC"

    parts: list[str] = []
    for s in sort_by:
        direction = "DESC" if s.direction == "desc" else "ASC"
        if s.mode == "difference" and len(eval_root_ids) > 1:
            expr = _build_difference_sort(s.field, eval_root_ids, pb)
        else:
            expr, _ = resolve_eval_field_to_sql(
                s.field, pb, evaluation_call_id=s.evaluation_call_id
            )
        parts.append(f"{expr} {direction}")

    parts.append("row_digest ASC")
    return ", ".join(parts)


def _build_difference_sort(
    field_path: str,
    eval_root_ids: list[str],
    pb: ParamBuilder,
) -> str:
    """Build greatest(...) - least(...) expression for difference mode sorting."""
    per_eval_exprs: list[str] = []
    for eval_id in eval_root_ids:
        expr, _ = resolve_eval_field_to_sql(field_path, pb, evaluation_call_id=eval_id)
        per_eval_exprs.append(expr)
    joined = ", ".join(per_eval_exprs)
    return f"greatest({joined}) - least({joined})"


def _build_having_clause(
    eval_root_ids: list[str],
    filters: list[tsi.EvalResultsFilter] | None,
    require_intersection: bool,
    pb: ParamBuilder,
) -> str:
    """Build the HAVING clause for ranked_digests."""
    having_parts: list[str] = ["1=1"]

    if require_intersection and len(eval_root_ids) > 1:
        num_param = pb.add(len(eval_root_ids), None, "UInt64")
        having_parts.append(f"countDistinct(eval_call_id) >= {num_param}")

    if filters:
        for f in filters:
            resolver = _make_field_resolver(f.evaluation_call_id)
            conditions, _ = _process_query_to_conditions(
                f.query, [], [], param_builder=pb, field_resolver=resolver
            )
            having_parts.extend(conditions)

    return "\n                    AND ".join(having_parts)


def build_ranked_digests_cte(
    eval_root_ids: list[str],
    sort_by: list[tsi.EvalResultsSortBy] | None,
    filters: list[tsi.EvalResultsFilter] | None,
    require_intersection: bool,
    limit: int | None,
    offset: int,
    pb: ParamBuilder,
) -> str:
    """Build ranked_digests, ranked_digest_count, and page_digests CTEs.

    ranked_digests: single grouped projection with HAVING + ROW_NUMBER.
    ranked_digest_count: total matching rows derived from ranked_digests.
    page_digests: paginated slice derived from ranked_digests.
    """
    sort_expr = build_sort_expression(sort_by, eval_root_ids, pb)
    having_clause = _build_having_clause(
        eval_root_ids, filters, require_intersection, pb
    )

    pagination = ""
    if limit is not None:
        pagination += f"\n                LIMIT {limit}"
        pagination += f"\n                OFFSET {offset}"
    elif offset > 0:
        pagination += f"\n                OFFSET {offset}"

    return f"""ranked_digests AS (
    SELECT row_digest,
        ROW_NUMBER() OVER(ORDER BY {sort_expr}) AS row_order
    FROM predict_and_score_calls_resolved
    GROUP BY row_digest
    HAVING {having_clause}
),

ranked_digest_count AS (
    SELECT count(*) AS total_rows FROM ranked_digests
),

page_digests AS (
    SELECT row_digest, row_order
    FROM ranked_digests
    ORDER BY row_order{pagination}
)"""


def build_page_rows_cte() -> str:
    """Build page_rows CTE: call IDs + resolved_inputs for the page."""
    return """page_rows AS (
    SELECT
        predict_and_score_calls_resolved.call_id,
        predict_and_score_calls_resolved.row_digest,
        page_digests.row_order,
        predict_and_score_calls_resolved.resolved_inputs
    FROM predict_and_score_calls_resolved
    INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
)"""


def build_eval_results_cte_chain(
    project_id: str,
    eval_root_ids: list[str],
    sort_by: list[tsi.EvalResultsSortBy] | None,
    filters: list[tsi.EvalResultsFilter] | None,
    require_intersection: bool,
    limit: int | None,
    offset: int,
    pb: ParamBuilder,
    read_table: str,
) -> str:
    """Build the full CTE chain for eval_results pagination.

    Returns CTE body without the WITH keyword — the caller (CallsQuery.as_sql)
    prepends WITH when merging with its own CTEs.

    Composes: predict_and_score_calls → predict_and_score_calls_resolved →
              ranked_digests → ranked_digest_count → page_digests → page_rows
    """
    project_id_param = pb.add(project_id, None, "String")
    eval_root_ids_param = pb.add(eval_root_ids, None, "Array(String)")
    op_prefix_param = pb.add(PREDICT_AND_SCORE_OP_PREFIX, None, "String")

    inputs_field = (
        "any(calls_merged.inputs_dump)"
        if read_table == "calls_merged"
        else "calls_complete.inputs_dump"
    )

    calls_cte = build_predict_and_score_calls_cte(
        project_id_param,
        eval_root_ids_param,
        op_prefix_param,
        inputs_field,
        read_table,
    )
    resolved_cte = build_predict_and_score_calls_resolved_cte(project_id_param)
    ranked_cte = build_ranked_digests_cte(
        eval_root_ids,
        sort_by,
        filters,
        require_intersection,
        limit,
        offset,
        pb,
    )
    page_rows_cte = build_page_rows_cte()

    return f"""{calls_cte},

{resolved_cte},

{ranked_cte},

{page_rows_cte}"""
