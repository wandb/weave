"""Query builder for the /eval_results endpoint.

Generates ClickHouse CTEs for the eval_results CTE chain:
  predict_and_score_calls          → filter to predict-and-score calls, extract row_digest
  predict_and_score_calls_resolved → (conditionally) LEFT JOIN table_rows so sort/filter on inputs.* can read the dataset row
  ranked_digests                   → GROUP BY row_digest, HAVING filters, ROW_NUMBER for sort
  ranked_digest_count              → total matching rows (for pagination metadata)
  page_digests                     → paginated slice of ranked_digests
  page_rows                        → call IDs + digests + order for the page

Heavy data (call payload columns, dataset-row val_dump) is fetched by separate
statements with literal id/digest params in PREWHERE — see
build_eval_results_hydration_query and build_table_rows_resolution_query.
"""

from functools import partial

from weave.trace_server import constants
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.optimization_builder import (
    DATETIME_BUFFER_TIME_SECONDS,
)
from weave.trace_server.calls_query_builder.utils import (
    json_dump_field_as_sql,
    param_slot,
)
from weave.trace_server.ch_sentinel_values import SENTINEL_EPOCH
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
    """`multiSearchAny(op_name, [prefixes])`: matches if any prefix is a substring (engages idx_op_name ngrambf index)."""
    return f"multiSearchAny({op_name_expr}, [{', '.join(op_prefix_params)}])"


def _build_eval_start_lower_bound(
    project_id_param: str, eval_root_ids_param: str
) -> str:
    """sortable_datetime floor for the calls_merged scan, as a scalar subquery.

    Predict-and-score calls start at/after their eval root, so bounding by the
    roots' earliest start (minus a buffer) engages the sortable_datetime minmax
    index and prunes granules. Falls back to epoch if the root start is NULL.
    """
    return f"""coalesce(
        (
            SELECT min(roots.started_at) - toIntervalSecond({DATETIME_BUFFER_TIME_SECONDS})
            FROM calls_merged AS roots
            PREWHERE roots.project_id = {project_id_param}
            WHERE roots.id IN {eval_root_ids_param}
        ),
        toDateTime64(0, 3)
    )"""


def _build_eval_end_upper_bound(project_id_param: str, eval_root_ids_param: str) -> str:
    """sortable_datetime ceiling for the calls_merged scan, as a scalar subquery.

    Predict-and-score calls finish before their eval root does, so bounding by
    the roots' latest ended_at (plus a buffer) keeps the scan inside the eval
    run window instead of eval start -> now. Falls back to a far-future
    datetime (no ceiling) when any root is still running or has no rows.
    """
    return f"""coalesce(
        (
            SELECT CASE
                WHEN countIf(root_ended_at IS NULL) > 0 THEN NULL
                ELSE max(root_ended_at) + toIntervalSecond({DATETIME_BUFFER_TIME_SECONDS})
            END
            FROM (
                SELECT max(roots.ended_at) AS root_ended_at
                FROM calls_merged AS roots
                PREWHERE roots.project_id = {project_id_param}
                WHERE roots.id IN {eval_root_ids_param}
                GROUP BY roots.id
            )
        ),
        toDateTime64('2100-01-01 00:00:00', 3)
    )"""


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
            f.query, param_builder=pb, field_resolver=collector
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
        eval_start_lower_bound = _build_eval_start_lower_bound(
            project_id_param, eval_root_ids_param
        )
        eval_end_upper_bound = _build_eval_end_upper_bound(
            project_id_param, eval_root_ids_param
        )
        # The inner id subquery matches on call-start rows only (they carry
        # parent_id/op_name), reading light columns. It lives in PREWHERE (an
        # explicit PREWHERE disables automatic condition movement) so the outer
        # aggregation reads inputs_dump/output_dump for just those ids instead
        # of every call in the window. The outer keeps only the lower time
        # bound: delete rows are written at deletion time (after the eval
        # window) and must still merge in so HAVING can exclude deleted calls.
        return f"""predict_and_score_calls AS (
    SELECT
        calls_merged.id AS call_id,
        any(calls_merged.parent_id) AS eval_call_id,
        any(calls_merged.inputs_dump) AS inputs_dump,
        any(calls_merged.output_dump) AS output_dump,
        {row_digest_expr} AS row_digest
    FROM calls_merged
    PREWHERE calls_merged.project_id = {project_id_param}
    AND calls_merged.id IN (
        SELECT calls_merged.id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {project_id_param}
        WHERE calls_merged.parent_id IN {eval_root_ids_param}
        AND calls_merged.id NOT IN {eval_root_ids_param}
        AND {op_match_where}
        AND calls_merged.sortable_datetime >= {eval_start_lower_bound}
        AND calls_merged.sortable_datetime <= {eval_end_upper_bound}
    )
    WHERE calls_merged.sortable_datetime >= {eval_start_lower_bound}
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
            nullIf(tr.val_dump, ''),
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


def _sort_numeric_scalar(
    field_path: str,
    pb: ParamBuilder,
    evaluation_call_id: str | None,
) -> str:
    """Return a single numeric scalar for a field (no direction, no multi-term).

    Safe to embed inside greatest()/least() for difference-mode sorting. Scores
    carry their bool coercion via _build_json_field_inner; inputs/output are
    coerced to float here so numeric values sort numerically rather than
    lexicographically. (Only ever called for scores/inputs/output fields --
    difference mode never targets row_digest.)
    """
    inner, _ = _build_json_field_inner(field_path, pb, evaluation_call_id)
    if field_path.startswith("scores."):
        return _score_sort_numeric(inner)
    return f"toFloat64OrNull(any({inner}))"


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
            parts.append(_build_difference_sort(s.field, eval_root_ids, pb, direction))
        else:
            parts.append(
                _build_sort_aggregate(s.field, pb, s.evaluation_call_id, direction)
            )

    parts.append("row_digest ASC")
    return ", ".join(parts)


def _build_sort_aggregate(
    field_path: str,
    pb: ParamBuilder,
    evaluation_call_id: str | None,
    direction: str,
) -> str:
    """Build the per-field ORDER BY fragment, including its direction(s).

    - row_digest: bare GROUP BY key.
    - scores.*: numeric avg (with bool coercion), single term.
    - inputs.*/output.*: a three-term existence -> numeric -> string fallback,
      mirroring OrderField in the calls query
      (calls_query_builder._build_standard_order_sql). The existence term is
      fixed DESC so rows with a numeric value precede NULL/text rows in BOTH
      sort directions -- ClickHouse places NULLs first on DESC by default and
      these builders use no explicit NULLS clauses. The numeric term sorts
      numeric values; the string term orders the remaining (text) rows.
    """
    inner, _ = _build_json_field_inner(field_path, pb, evaluation_call_id)
    if field_path == "row_digest":
        return f"{inner} {direction}"
    if field_path.startswith("scores."):
        return f"{_score_sort_numeric(inner)} {direction}"
    numeric = f"toFloat64OrNull(any({inner}))"
    string = f"any({inner})"
    return f"({numeric} IS NOT NULL) DESC, {numeric} {direction}, {string} {direction}"


def _build_difference_sort(
    field_path: str,
    eval_root_ids: list[str],
    pb: ParamBuilder,
    direction: str,
) -> str:
    """Build greatest(...) - least(...) expression for difference mode sorting.

    Uses the numeric scalar per eval so the subtraction is numeric; sorting an
    output column in difference mode previously subtracted raw strings.
    """
    per_eval_exprs: list[str] = []
    for eval_id in eval_root_ids:
        per_eval_exprs.append(_sort_numeric_scalar(field_path, pb, eval_id))
    joined = ", ".join(per_eval_exprs)
    return f"greatest({joined}) - least({joined}) {direction}"


def _build_having_clause(
    eval_root_ids: list[str],
    filters: list[tsi.EvalResultsFilter] | None,
    require_intersection: bool,
    pb: ParamBuilder,
    filter_logic_operator: str = "or",
) -> str:
    """Build the HAVING clause for ranked_digests.

    Args:
        filter_logic_operator: 'and' (Match All) or 'or' (Match Any, default).
            - 'and': Row must match filters in ALL evals
            - 'or': Row must match filters in ANY eval (default)
    """
    having_parts: list[str] = ["1=1"]

    if require_intersection and len(eval_root_ids) > 1:
        num_param = pb.add(len(eval_root_ids), None, "UInt64")
        having_parts.append(f"countDistinct(eval_call_id) >= {num_param}")

    if filters:
        if filter_logic_operator == "or":
            # Match Any: group conditions by eval, OR between groups
            eval_groups: dict[str | None, list[str]] = {}
            for f in filters:
                resolver = _make_field_resolver(f.evaluation_call_id)
                conditions, _ = _process_query_to_conditions(
                    f.query, param_builder=pb, field_resolver=resolver
                )
                eval_groups.setdefault(f.evaluation_call_id, []).extend(conditions)

            # Each eval's conditions are AND'd, then OR'd between evals
            group_clauses = []
            for conds in eval_groups.values():
                if conds:
                    group_clauses.append(f"({' AND '.join(conds)})")
            if group_clauses:
                having_parts.append(f"({' OR '.join(group_clauses)})")
        else:
            # Match All (default): flat AND of all conditions
            for f in filters:
                resolver = _make_field_resolver(f.evaluation_call_id)
                conditions, _ = _process_query_to_conditions(
                    f.query, param_builder=pb, field_resolver=resolver
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
    filter_logic_operator: str = "or",
) -> str:
    """Build ranked_digests, ranked_digest_count, and page_digests CTEs.

    ranked_digests: single grouped projection with HAVING + ROW_NUMBER.
    ranked_digest_count: total matching rows derived from ranked_digests.
    page_digests: paginated slice derived from ranked_digests.
    """
    sort_expr = build_sort_expression(sort_by, eval_root_ids, pb)
    having_clause = _build_having_clause(
        eval_root_ids, filters, require_intersection, pb, filter_logic_operator
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
    """Build page_rows CTE: page digests joined back to their calls.

    Dataset-row resolution deliberately does NOT happen here: a
    `digest IN (SELECT ... FROM page_digests)` scan of table_rows reads
    val_dump for every row in the surviving granules (GBs on fat datasets)
    even though only the page's digests are needed. Callers that want
    resolved rows fetch them with build_table_rows_resolution_query using
    the returned digests as a literal PREWHERE param.
    """
    return """page_rows AS (
    SELECT
        predict_and_score_calls_resolved.call_id AS call_id,
        predict_and_score_calls_resolved.eval_call_id AS eval_call_id,
        predict_and_score_calls_resolved.row_digest AS row_digest,
        page_digests.row_order AS row_order
    FROM predict_and_score_calls_resolved
    INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
)"""


def build_table_rows_resolution_query(
    project_id: str,
    digests: list[str],
    pb: ParamBuilder,
) -> str:
    """Resolve dataset-row val_dump for a literal digest list (PREWHERE)."""
    project_id_param = param_slot(pb.add_param(project_id), "String")
    digests_param = pb.add(digests, None, "Array(String)")
    return f"""SELECT digest, any(val_dump) AS val_dump
FROM table_rows
PREWHERE project_id = {project_id_param}
AND digest IN {digests_param}
GROUP BY digest"""


def build_eval_results_page_query(
    project_id: str,
    eval_root_ids: list[str],
    sort_by: list[tsi.EvalResultsSortBy] | None,
    filters: list[tsi.EvalResultsFilter] | None,
    require_intersection: bool,
    limit: int | None,
    offset: int,
    pb: ParamBuilder,
    read_table: str,
    filter_logic_operator: str = "or",
) -> str:
    """Build the page-selection SQL: which rows to show, on light columns only.

    Returns one row per page call with call_id, eval_call_id, row_digest,
    row_order, resolved_inputs, and the total row count. Heavy call payloads
    are fetched by a second statement (build_eval_results_hydration_query)
    with the selected ids as a literal parameter: an in-statement
    `id IN (SELECT ... FROM page_rows)` cannot sit in PREWHERE (chained-CTE
    references re-evaluate pathologically), and from WHERE the dump columns
    are read for every row in the surviving granules -- GBs on fat projects
    to display 50 rows.
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
        filter_logic_operator,
    )
    return f"""WITH {cte_chain.strip()}
SELECT
    page_rows.call_id AS call_id,
    page_rows.eval_call_id AS eval_call_id,
    page_rows.row_digest AS row_digest,
    page_rows.row_order AS row_order,
    (SELECT total_rows FROM ranked_digest_count) AS total_rows
FROM page_rows
ORDER BY page_rows.row_order ASC"""


def build_eval_results_hydration_query(
    project_id: str,
    call_ids: list[str],
    pb: ParamBuilder,
    read_table: str,
) -> str:
    """Build the hydration SQL: heavy call columns for a literal id list.

    The literal id set sits in PREWHERE, so ClickHouse row-filters on
    (project_id, id) before reading the dump columns -- reads stay
    proportional to the page, not to the granules the page's rows live in.
    """
    project_id_param = param_slot(pb.add_param(project_id), "String")
    call_ids_param = pb.add(call_ids, None, "Array(String)")

    if read_table == "calls_merged":
        return f"""SELECT
    calls_merged.id AS id,
    any(calls_merged.project_id) AS project_id,
    any(calls_merged.trace_id) AS trace_id,
    any(calls_merged.op_name) AS op_name,
    any(calls_merged.started_at) AS started_at,
    any(calls_merged.ended_at) AS ended_at,
    any(calls_merged.attributes_dump) AS attributes_dump,
    any(calls_merged.inputs_dump) AS inputs_dump,
    any(calls_merged.output_dump) AS output_dump,
    any(calls_merged.summary_dump) AS summary_dump
FROM calls_merged
PREWHERE calls_merged.project_id = {project_id_param}
AND calls_merged.id IN {call_ids_param}
GROUP BY (calls_merged.project_id, calls_merged.id)"""
    else:
        return f"""SELECT
    calls_complete.id AS id,
    calls_complete.project_id,
    calls_complete.trace_id,
    calls_complete.op_name,
    calls_complete.started_at,
    calls_complete.ended_at,
    calls_complete.attributes_dump,
    calls_complete.inputs_dump,
    calls_complete.output_dump,
    calls_complete.summary_dump
FROM calls_complete
PREWHERE calls_complete.project_id = {project_id_param}
AND calls_complete.id IN {call_ids_param}"""


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
    filter_logic_operator: str = "or",
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
            pb.add_param(SENTINEL_EPOCH), "DateTime64(3)"
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
        filter_logic_operator,
    )
    page_rows_cte = build_page_rows_cte()

    return f"""{calls_cte},

{resolved_cte},

{ranked_cte},

{page_rows_cte}"""
