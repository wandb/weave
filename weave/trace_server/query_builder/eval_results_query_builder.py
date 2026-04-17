"""Query builder for the /eval_results endpoint.

Generates ClickHouse CTEs for the eval_results CTE chain:
  predict_and_score_calls          → filter to predict-and-score calls, extract row_digest
  predict_and_score_calls_resolved → (conditionally) LEFT JOIN table_rows so sort/filter on inputs.* can read the dataset row
  ranked_digests                   → GROUP BY row_digest, HAVING filters, ROW_NUMBER for sort
  ranked_digest_count              → total matching rows (for pagination metadata)
  page_digests                     → paginated slice of ranked_digests
  page_resolved_inputs             → table_rows JOIN for the paginated digests only
  page_rows                        → call IDs + resolved_inputs for the page
"""

from functools import partial

from weave.trace_server import constants
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.utils import (
    json_dump_field_as_sql,
    param_slot,
)
from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.orm import (
    ParamBuilder,
    _process_query_to_conditions,
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


def _sort_filter_uses_inputs(
    sort_by: list[tsi.EvalResultsSortBy] | None,
    filters: list[tsi.EvalResultsFilter] | None,
) -> bool:
    """True if any sort_by.field or filter $getField references ``inputs.*``."""
    if sort_by:
        for s in sort_by:
            if s.field.startswith("inputs."):
                return True

    if not filters:
        return False

    found = False

    def collector(path: str, _pb: ParamBuilder) -> tuple[str, set[str]]:
        nonlocal found
        if path.startswith("inputs."):
            found = True
        return "NULL", set()

    pb = ParamBuilder()
    for f in filters:
        _process_query_to_conditions(
            f.query, [], [], param_builder=pb, field_resolver=collector
        )
    return found


def build_predict_and_score_calls_cte(
    project_id_param: str,
    eval_root_ids_param: str,
    op_prefix_params: list[str],
    inputs_field: str,
    read_table: str,
    deleted_at_sentinel_param: str | None = None,
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
        AND any(calls_merged.deleted_at) IS NULL
        AND any(calls_merged.started_at) IS NOT NULL
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
        {row_digest_expr} AS row_digest
    FROM calls_complete
    PREWHERE calls_complete.project_id = {project_id_param}
    WHERE calls_complete.parent_id IN {eval_root_ids_param}
      AND calls_complete.id NOT IN {eval_root_ids_param}
      AND ({op_match_calls_complete})
      AND calls_complete.deleted_at = {deleted_at_sentinel_param}
)"""


def build_predict_and_score_calls_resolved_cte(
    project_id_param: str,
    needs_inputs_resolution: bool,
) -> str:
    """Build the predict_and_score_calls_resolved CTE SQL.

    When ``needs_inputs_resolution`` is True (sort/filter references an
    ``inputs.*`` field), LEFT JOIN table_rows so ``resolved_inputs`` is
    available to HAVING/ORDER BY.
    """
    if not needs_inputs_resolution:
        return """predict_and_score_calls_resolved AS (
    SELECT * FROM predict_and_score_calls
)"""

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


def _build_json_field_inner(
    field_path: str,
    pb: ParamBuilder,
    evaluation_call_id: str | None = None,
) -> tuple[str, set[str]]:
    """Per-row SQL for an eval field (String-typed, no aggregate).

    If evaluation_call_id is set, wraps the extract with CASE WHEN to scope
    it to a single eval; aggregation is the caller's responsibility (filter
    wraps with any(); sort wraps with avg(toFloat64OrNull(...)) for scores
    or any() otherwise).

    Returns:
        (per_row_sql_expression, set of physical columns used)
    """
    if field_path == "row_digest":
        return "row_digest", {"inputs_dump"}

    if field_path.startswith("inputs."):
        extra = split_escaped_field_path(field_path[len("inputs.") :])
        inner = json_dump_field_as_sql(pb, "", "resolved_inputs", extra)
        cols = {"inputs_dump"}
    elif field_path.startswith("output."):
        extra = split_escaped_field_path(field_path[len("output.") :])
        inner = json_dump_field_as_sql(pb, "", "output_dump", extra)
        cols = {"output_dump"}
    elif field_path.startswith("scores."):
        extra = ["scores"] + split_escaped_field_path(field_path[len("scores.") :])
        raw = json_dump_field_as_sql(pb, "", "output_dump", extra)
        inner = f"multiIf({raw} = 'true', '1', {raw} = 'false', '0', {raw})"
        cols = {"output_dump"}
    else:
        raise InvalidRequest(
            f"Unsupported eval results field: '{field_path}'. "
            f"Supported prefixes: scores.*, inputs.*, output.*, row_digest."
        )

    inner = _wrap_with_eval_scope(inner, evaluation_call_id, pb)
    return inner, cols


def resolve_eval_field_to_sql(
    field_path: str,
    pb: ParamBuilder,
    evaluation_call_id: str | None = None,
) -> tuple[str, set[str]]:
    """Filter-path field resolver: wraps per-row expression in any().

    Returns:
        (sql_expression, set of physical columns used)
    """
    inner, cols = _build_json_field_inner(field_path, pb, evaluation_call_id)
    if field_path == "row_digest":
        return inner, cols
    return f"any({inner})", cols


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


def _score_sort_numeric(inner_sql: str) -> str:
    """Numeric avg applied to a pre-coerced scores per-row String expression.

    The bool coercion lives inside _build_json_field_inner; this only adds the
    toFloat64OrNull + avg wrapping that the sort path needs.
    """
    return f"avg(toFloat64OrNull({inner_sql}))"


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
            expr = _build_sort_aggregate(s.field, pb, s.evaluation_call_id)
        parts.append(f"{expr} {direction}")

    parts.append("row_digest ASC")
    return ", ".join(parts)


def _build_sort_aggregate(
    field_path: str,
    pb: ParamBuilder,
    evaluation_call_id: str | None,
) -> str:
    """Build the per-field sort expression, applying the right aggregate.

    Scores get numeric avg (with bool coercion); other fields get any().
    row_digest is used bare (it's the GROUP BY key).
    """
    inner, _ = _build_json_field_inner(field_path, pb, evaluation_call_id)
    if field_path == "row_digest":
        return inner
    if field_path.startswith("scores."):
        return _score_sort_numeric(inner)
    return f"any({inner})"


def _build_difference_sort(
    field_path: str,
    eval_root_ids: list[str],
    pb: ParamBuilder,
) -> str:
    """Build greatest(...) - least(...) expression for difference mode sorting."""
    per_eval_exprs: list[str] = []
    for eval_id in eval_root_ids:
        per_eval_exprs.append(_build_sort_aggregate(field_path, pb, eval_id))
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


def build_page_resolved_inputs_cte(project_id_param: str) -> str:
    """Hydrate dataset-row val_dump for just the page's digests."""
    return f"""page_resolved_inputs AS (
    SELECT digest, any(val_dump) AS val_dump
    FROM table_rows
    PREWHERE project_id = {project_id_param}
    WHERE digest IN (SELECT row_digest FROM page_digests)
    GROUP BY digest
)"""


def build_page_rows_cte() -> str:
    """Build page_rows CTE: joins page digests with the per-page val_dump
    resolution.
    """
    return """page_rows AS (
    SELECT
        predict_and_score_calls_resolved.call_id AS call_id,
        predict_and_score_calls_resolved.eval_call_id AS eval_call_id,
        predict_and_score_calls_resolved.row_digest AS row_digest,
        page_digests.row_order AS row_order,
        COALESCE(
            page_resolved_inputs.val_dump,
            JSONExtractRaw(predict_and_score_calls_resolved.inputs_dump, 'example')
        ) AS resolved_inputs
    FROM predict_and_score_calls_resolved
    INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
    LEFT JOIN page_resolved_inputs ON page_resolved_inputs.digest = predict_and_score_calls_resolved.row_digest
)"""


def _build_page_calls_cte(project_id_param: str, read_table: str) -> str:
    """Build page_calls CTE: pre-filter and pre-aggregate source table for page rows only."""
    if read_table == "calls_merged":
        return f"""page_calls AS (
    SELECT
        calls_merged.id AS call_id,
        any(calls_merged.project_id) AS project_id,
        any(calls_merged.trace_id) AS trace_id,
        any(calls_merged.op_name) AS op_name,
        any(calls_merged.started_at) AS started_at,
        any(calls_merged.ended_at) AS ended_at,
        any(calls_merged.inputs_dump) AS inputs_dump,
        any(calls_merged.output_dump) AS output_dump,
        any(calls_merged.summary_dump) AS summary_dump
    FROM calls_merged
    PREWHERE calls_merged.project_id = {project_id_param}
    WHERE calls_merged.id IN (SELECT call_id FROM page_rows)
    GROUP BY (calls_merged.project_id, calls_merged.id)
)"""
    else:
        return f"""page_calls AS (
    SELECT
        calls_complete.id AS call_id,
        calls_complete.project_id,
        calls_complete.trace_id,
        calls_complete.op_name,
        calls_complete.started_at,
        calls_complete.ended_at,
        calls_complete.inputs_dump,
        calls_complete.output_dump,
        calls_complete.summary_dump
    FROM calls_complete
    WHERE calls_complete.project_id = {project_id_param}
      AND calls_complete.id IN (SELECT call_id FROM page_rows)
)"""


def build_eval_results_query(
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
    """Build the complete eval_results SQL query.

    The CTE chain carries only lightweight columns for sort/filter/pagination.
    A page_calls CTE pre-filters the source table to just the page's call IDs,
    then the outer SELECT joins two small tables (page_rows + page_calls).
    """
    cte_chain = build_eval_results_cte_chain(
        project_id,
        eval_root_ids,
        sort_by,
        filters,
        require_intersection,
        limit,
        offset,
        pb,
        read_table,
    )
    project_id_param = param_slot(pb.add_param(project_id), "String")
    page_calls_cte = _build_page_calls_cte(project_id_param, read_table)

    return f"""WITH {cte_chain.strip()},

{page_calls_cte}
SELECT
    page_rows.call_id AS id,
    page_rows.eval_call_id AS parent_id,
    page_calls.project_id,
    page_calls.trace_id,
    page_calls.op_name,
    page_calls.started_at,
    page_calls.ended_at,
    page_calls.inputs_dump,
    page_calls.output_dump,
    page_calls.summary_dump,
    page_rows.row_digest AS __row_digest,
    page_rows.row_order AS __row_order,
    page_rows.resolved_inputs AS __resolved_inputs,
    (SELECT total_rows FROM ranked_digest_count) AS __total_rows
FROM page_rows
LEFT JOIN page_calls ON page_calls.call_id = page_rows.call_id
ORDER BY page_rows.row_order ASC"""


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
    """Build the CTE chain body (without WITH keyword).

    Composes: predict_and_score_calls → predict_and_score_calls_resolved →
              ranked_digests → ranked_digest_count → page_digests → page_rows
    """
    project_id_param = pb.add(project_id, None, "String")
    eval_root_ids_param = pb.add(eval_root_ids, None, "Array(String)")
    op_prefix_params = [
        pb.add(name, None, "String")
        for name in constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES
    ]

    # for calls_complete, deleted_at uses epoch zero instead of NULL.
    deleted_at_sentinel_param = None
    if read_table != "calls_merged":
        deleted_at_sentinel_param = param_slot(
            pb.add_param(SENTINEL_DATETIME), "DateTime64(3)"
        )

    inputs_field = (
        "any(calls_merged.inputs_dump)"
        if read_table == "calls_merged"
        else "calls_complete.inputs_dump"
    )

    needs_inputs_resolution = _sort_filter_uses_inputs(sort_by, filters)

    calls_cte = build_predict_and_score_calls_cte(
        project_id_param,
        eval_root_ids_param,
        op_prefix_params,
        inputs_field,
        read_table,
        deleted_at_sentinel_param,
    )
    resolved_cte = build_predict_and_score_calls_resolved_cte(
        project_id_param, needs_inputs_resolution
    )
    ranked_cte = build_ranked_digests_cte(
        eval_root_ids,
        sort_by,
        filters,
        require_intersection,
        limit,
        offset,
        pb,
    )
    page_resolved_cte = build_page_resolved_inputs_cte(project_id_param)
    page_rows_cte = build_page_rows_cte()

    return f"""{calls_cte},

{resolved_cte},

{ranked_cte},

{page_resolved_cte},

{page_rows_cte}"""
