"""Query builder for the /eval_results endpoint.

Generates ClickHouse CTEs for resolving dataset-backed inputs via table_rows JOIN.

CTE chain:
  predict_and_score_calls          → filter to predict-and-score calls, extract row_digest
  predict_and_score_calls_resolved → LEFT JOIN table_rows to resolve dataset-backed inputs
"""

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

PREDICT_AND_SCORE_OP_PREFIX = "Evaluation.predict_and_score"


def build_predict_and_score_calls_cte(
    project_id_param: str,
    eval_root_ids_param: str,
    op_prefix_param: str,
    inputs_field: str,
    read_table: str,
) -> str:
    """Build the predict_and_score_calls CTE SQL.

    Filters to predict-and-score calls that are direct children of eval roots
    and extracts row_digest from inputs.
    """
    row_digest_expr = ROW_DIGEST_SQL_TEMPLATE.format(inputs_field=inputs_field)

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
        position(calls_merged.op_name, {op_prefix_param}) > 0
        OR calls_merged.op_name IS NULL
    )
    GROUP BY (calls_merged.project_id, calls_merged.id)
    HAVING any(calls_merged.parent_id) IN {eval_root_ids_param}
        AND position(any(calls_merged.op_name), {op_prefix_param}) > 0
)"""
    else:
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
      AND position(calls_complete.op_name, {op_prefix_param}) > 0
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
