from tests.trace_server.query_builder.utils import assert_raw_sql
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.constants import (
    EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
    EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
)
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.eval_results_query_builder import (
    build_eval_results_cte_chain,
    build_eval_results_query,
)


def test_cte_chain_calls_merged() -> None:
    """Full CTE chain for calls_merged with intersection."""
    pb = ParamBuilder("pb")
    cte = build_eval_results_cte_chain(
        project_id="proj-1",
        eval_root_ids=["eval-1", "eval-2"],
        sort_by=None,
        filters=None,
        require_intersection=True,
        limit=50,
        offset=0,
        pb=pb,
        read_table="calls_merged",
    )
    assert_raw_sql(
        cte,
        """
            predict_and_score_calls AS (
                SELECT calls_merged.id AS call_id,
                    any(calls_merged.parent_id) AS eval_call_id,
                    any(calls_merged.inputs_dump) AS inputs_dump,
                    any(calls_merged.output_dump) AS output_dump,
                    CASE
                        WHEN position(JSON_VALUE(any(calls_merged.inputs_dump), '$.example'), '/attr/rows/id/') > 0
                            THEN regexpExtract(JSON_VALUE(any(calls_merged.inputs_dump), '$.example'), '/attr/rows/id/([^/]+)$', 1)
                        ELSE hex(SHA256(JSONExtractRaw(any(calls_merged.inputs_dump), 'example')))
                    END AS row_digest
                FROM calls_merged
                PREWHERE calls_merged.project_id = {pb_0:String}
                WHERE (calls_merged.parent_id IN {pb_1:Array(String)}
                    OR calls_merged.parent_id IS NULL)
                    AND calls_merged.id NOT IN {pb_1:Array(String)}
                    AND (position(calls_merged.op_name, {pb_2:String}) > 0
                        OR position(calls_merged.op_name, {pb_3:String}) > 0
                        OR calls_merged.op_name IS NULL)
                GROUP BY (calls_merged.project_id, calls_merged.id)
                HAVING any(calls_merged.parent_id) IN {pb_1:Array(String)}
                    AND (position(any(calls_merged.op_name), {pb_2:String}) > 0
                        OR position(any(calls_merged.op_name), {pb_3:String}) > 0)
                    AND any(calls_merged.deleted_at) IS NULL
                    AND any(calls_merged.started_at) IS NOT NULL
            ),

            predict_and_score_calls_resolved AS (
                SELECT * FROM predict_and_score_calls
            ),

            ranked_digests AS (
                SELECT row_digest,
                    ROW_NUMBER() OVER(ORDER BY row_digest ASC) AS row_order
                FROM predict_and_score_calls_resolved
                GROUP BY row_digest
                HAVING 1=1
                    AND countDistinct(eval_call_id) >= {pb_4:UInt64}
            ),

            ranked_digest_count AS (
                SELECT count(*) AS total_rows FROM ranked_digests
            ),

            page_digests AS (
                SELECT row_digest, row_order
                FROM ranked_digests
                ORDER BY row_order
                LIMIT 50
                OFFSET 0
            ),

            page_resolved_inputs AS (
                SELECT digest, any(val_dump) AS val_dump
                FROM table_rows
                PREWHERE project_id = {pb_0:String}
                WHERE digest IN (SELECT row_digest FROM page_digests)
                GROUP BY digest
            ),

            page_rows AS (
                SELECT predict_and_score_calls_resolved.call_id AS call_id,
                    predict_and_score_calls_resolved.eval_call_id AS eval_call_id,
                    predict_and_score_calls_resolved.row_digest AS row_digest,
                    page_digests.row_order AS row_order,
                    COALESCE(page_resolved_inputs.val_dump, JSONExtractRaw(predict_and_score_calls_resolved.inputs_dump, 'example')) AS resolved_inputs
                FROM predict_and_score_calls_resolved
                INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
                LEFT JOIN page_resolved_inputs ON page_resolved_inputs.digest = predict_and_score_calls_resolved.row_digest
            )
            """,
        pb.get_params(),
        {
            "pb_0": "proj-1",
            "pb_1": ["eval-1", "eval-2"],
            "pb_2": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            "pb_3": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
            "pb_4": 2,
        },
    )


def test_cte_chain_calls_complete() -> None:
    """Full CTE chain for calls_complete with offset."""
    pb = ParamBuilder("pb")
    cte = build_eval_results_cte_chain(
        project_id="proj-1",
        eval_root_ids=["eval-1"],
        sort_by=None,
        filters=None,
        require_intersection=False,
        limit=25,
        offset=10,
        pb=pb,
        read_table="calls_complete",
    )
    assert_raw_sql(
        cte,
        """
            predict_and_score_calls AS (
                SELECT calls_complete.id AS call_id,
                    calls_complete.parent_id AS eval_call_id,
                    calls_complete.inputs_dump,
                    calls_complete.output_dump,
                    CASE
                        WHEN position(JSON_VALUE(calls_complete.inputs_dump, '$.example'), '/attr/rows/id/') > 0
                            THEN regexpExtract(JSON_VALUE(calls_complete.inputs_dump, '$.example'), '/attr/rows/id/([^/]+)$', 1)
                        ELSE hex(SHA256(JSONExtractRaw(calls_complete.inputs_dump, 'example')))
                    END AS row_digest
                FROM calls_complete
                PREWHERE calls_complete.project_id = {pb_0:String}
                WHERE calls_complete.parent_id IN {pb_1:Array(String)}
                    AND calls_complete.id NOT IN {pb_1:Array(String)}
                    AND (position(calls_complete.op_name, {pb_2:String}) > 0
                        OR position(calls_complete.op_name, {pb_3:String}) > 0)
                    AND calls_complete.deleted_at = {pb_4:DateTime64(3)}
            ),

            predict_and_score_calls_resolved AS (
                SELECT * FROM predict_and_score_calls
            ),

            ranked_digests AS (
                SELECT row_digest,
                    ROW_NUMBER() OVER(ORDER BY row_digest ASC) AS row_order
                FROM predict_and_score_calls_resolved
                GROUP BY row_digest
                HAVING 1=1
            ),

            ranked_digest_count AS (
                SELECT count(*) AS total_rows FROM ranked_digests
            ),

            page_digests AS (
                SELECT row_digest, row_order
                FROM ranked_digests
                ORDER BY row_order
                LIMIT 25
                OFFSET 10
            ),

            page_resolved_inputs AS (
                SELECT digest, any(val_dump) AS val_dump
                FROM table_rows
                PREWHERE project_id = {pb_0:String}
                WHERE digest IN (SELECT row_digest FROM page_digests)
                GROUP BY digest
            ),

            page_rows AS (
                SELECT predict_and_score_calls_resolved.call_id AS call_id,
                    predict_and_score_calls_resolved.eval_call_id AS eval_call_id,
                    predict_and_score_calls_resolved.row_digest AS row_digest,
                    page_digests.row_order AS row_order,
                    COALESCE(page_resolved_inputs.val_dump, JSONExtractRaw(predict_and_score_calls_resolved.inputs_dump, 'example')) AS resolved_inputs
                FROM predict_and_score_calls_resolved
                INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
                LEFT JOIN page_resolved_inputs ON page_resolved_inputs.digest = predict_and_score_calls_resolved.row_digest
            )
            """,
        pb.get_params(),
        {
            "pb_0": "proj-1",
            "pb_1": ["eval-1"],
            "pb_2": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            "pb_3": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
            "pb_4": SENTINEL_DATETIME,
        },
    )


def test_cte_chain_sort_and_multi_eval_filters() -> None:
    """Full CTE chain: scoped sort + two per-eval filters + intersection on calls_complete."""
    pb = ParamBuilder("pb")
    sort_by = [
        tsi.EvalResultsSortBy(
            field="scores.accuracy",
            direction="desc",
            evaluation_call_id="eval-1",
        )
    ]
    filters = [
        tsi.EvalResultsFilter(
            evaluation_call_id="eval-1",
            query=Query.model_validate(
                {
                    "$expr": {
                        "$gte": [
                            {
                                "$convert": {
                                    "input": {"$getField": "scores.accuracy"},
                                    "to": "double",
                                }
                            },
                            {"$literal": 0.5},
                        ]
                    }
                }
            ),
        ),
        tsi.EvalResultsFilter(
            evaluation_call_id="eval-2",
            query=Query.model_validate(
                {
                    "$expr": {
                        "$lte": [
                            {
                                "$convert": {
                                    "input": {"$getField": "scores.accuracy"},
                                    "to": "double",
                                }
                            },
                            {"$literal": 0.9},
                        ]
                    }
                }
            ),
        ),
    ]
    cte = build_eval_results_cte_chain(
        project_id="proj-1",
        eval_root_ids=["eval-1", "eval-2"],
        sort_by=sort_by,
        filters=filters,
        require_intersection=True,
        limit=100,
        offset=50,
        pb=pb,
        read_table="calls_complete",
    )
    assert_raw_sql(
        cte,
        """
            predict_and_score_calls AS (
                SELECT calls_complete.id AS call_id,
                    calls_complete.parent_id AS eval_call_id,
                    calls_complete.inputs_dump,
                    calls_complete.output_dump,
                    CASE
                        WHEN position(JSON_VALUE(calls_complete.inputs_dump, '$.example'), '/attr/rows/id/') > 0
                            THEN regexpExtract(JSON_VALUE(calls_complete.inputs_dump, '$.example'), '/attr/rows/id/([^/]+)$', 1)
                        ELSE hex(SHA256(JSONExtractRaw(calls_complete.inputs_dump, 'example')))
                    END AS row_digest
                FROM calls_complete
                PREWHERE calls_complete.project_id = {pb_0:String}
                WHERE calls_complete.parent_id IN {pb_1:Array(String)}
                    AND calls_complete.id NOT IN {pb_1:Array(String)}
                    AND (position(calls_complete.op_name, {pb_2:String}) > 0
                        OR position(calls_complete.op_name, {pb_3:String}) > 0)
                    AND calls_complete.deleted_at = {pb_4:DateTime64(3)}
            ),

            predict_and_score_calls_resolved AS (
                SELECT * FROM predict_and_score_calls
            ),

            ranked_digests AS (
                SELECT row_digest,
                    ROW_NUMBER() OVER(ORDER BY avg(toFloat64OrNull(CASE WHEN eval_call_id = {pb_6:String} THEN multiIf(coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '') = 'true', '1', coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '') = 'false', '0', coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '')) ELSE NULL END)) DESC, row_digest ASC) AS row_order
                FROM predict_and_score_calls_resolved
                GROUP BY row_digest
                HAVING 1=1
                    AND countDistinct(eval_call_id) >= {pb_7:UInt64}
                    AND (toFloat64OrNull(any(CASE WHEN eval_call_id = {pb_6:String} THEN multiIf(coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '') = 'true', '1', coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '') = 'false', '0', coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '')) ELSE NULL END)) >= {pb_8:Float64})
                    AND (toFloat64OrNull(any(CASE WHEN eval_call_id = {pb_9:String} THEN multiIf(coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '') = 'true', '1', coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '') = 'false', '0', coalesce(nullIf(JSON_VALUE(output_dump, {pb_5:String}), 'null'), '')) ELSE NULL END)) <= {pb_10:Float64})
            ),

            ranked_digest_count AS (
                SELECT count(*) AS total_rows FROM ranked_digests
            ),

            page_digests AS (
                SELECT row_digest, row_order
                FROM ranked_digests
                ORDER BY row_order
                LIMIT 100
                OFFSET 50
            ),

            page_resolved_inputs AS (
                SELECT digest, any(val_dump) AS val_dump
                FROM table_rows
                PREWHERE project_id = {pb_0:String}
                WHERE digest IN (SELECT row_digest FROM page_digests)
                GROUP BY digest
            ),

            page_rows AS (
                SELECT predict_and_score_calls_resolved.call_id AS call_id,
                    predict_and_score_calls_resolved.eval_call_id AS eval_call_id,
                    predict_and_score_calls_resolved.row_digest AS row_digest,
                    page_digests.row_order AS row_order,
                    COALESCE(page_resolved_inputs.val_dump, JSONExtractRaw(predict_and_score_calls_resolved.inputs_dump, 'example')) AS resolved_inputs
                FROM predict_and_score_calls_resolved
                INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
                LEFT JOIN page_resolved_inputs ON page_resolved_inputs.digest = predict_and_score_calls_resolved.row_digest
            )
            """,
        pb.get_params(),
        {
            "pb_0": "proj-1",
            "pb_1": ["eval-1", "eval-2"],
            "pb_2": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            "pb_3": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
            "pb_4": SENTINEL_DATETIME,
            "pb_5": '$."scores"."accuracy"',
            "pb_6": "eval-1",
            "pb_7": 2,
            "pb_8": 0.5,
            "pb_9": "eval-2",
            "pb_10": 0.9,
        },
    )


def test_full_query_calls_merged() -> None:
    """Full SQL: lean CTEs + outer SELECT hydrates from calls_merged."""
    pb = ParamBuilder("pb")
    sql = build_eval_results_query(
        project_id="proj-1",
        eval_root_ids=["eval-1"],
        sort_by=None,
        filters=None,
        require_intersection=False,
        limit=10,
        offset=0,
        pb=pb,
        read_table="calls_merged",
    )
    assert_raw_sql(
        sql,
        """
        WITH predict_and_score_calls AS (
                SELECT calls_merged.id AS call_id,
                    any(calls_merged.parent_id) AS eval_call_id,
                    any(calls_merged.inputs_dump) AS inputs_dump,
                    any(calls_merged.output_dump) AS output_dump,
                    CASE
                        WHEN position(JSON_VALUE(any(calls_merged.inputs_dump), '$.example'), '/attr/rows/id/') > 0
                            THEN regexpExtract(JSON_VALUE(any(calls_merged.inputs_dump), '$.example'), '/attr/rows/id/([^/]+)$', 1)
                        ELSE hex(SHA256(JSONExtractRaw(any(calls_merged.inputs_dump), 'example')))
                    END AS row_digest
                FROM calls_merged
                PREWHERE calls_merged.project_id = {pb_0:String}
                WHERE (calls_merged.parent_id IN {pb_1:Array(String)}
                    OR calls_merged.parent_id IS NULL)
                    AND calls_merged.id NOT IN {pb_1:Array(String)}
                    AND (position(calls_merged.op_name, {pb_2:String}) > 0
                        OR position(calls_merged.op_name, {pb_3:String}) > 0
                        OR calls_merged.op_name IS NULL)
                GROUP BY (calls_merged.project_id, calls_merged.id)
                HAVING any(calls_merged.parent_id) IN {pb_1:Array(String)}
                    AND (position(any(calls_merged.op_name), {pb_2:String}) > 0
                        OR position(any(calls_merged.op_name), {pb_3:String}) > 0)
                    AND any(calls_merged.deleted_at) IS NULL
                    AND any(calls_merged.started_at) IS NOT NULL
            ),

            predict_and_score_calls_resolved AS (
                SELECT * FROM predict_and_score_calls
            ),

            ranked_digests AS (
                SELECT row_digest,
                    ROW_NUMBER() OVER(ORDER BY row_digest ASC) AS row_order
                FROM predict_and_score_calls_resolved
                GROUP BY row_digest
                HAVING 1=1
            ),

            ranked_digest_count AS (
                SELECT count(*) AS total_rows FROM ranked_digests
            ),

            page_digests AS (
                SELECT row_digest, row_order
                FROM ranked_digests
                ORDER BY row_order
                LIMIT 10
                OFFSET 0
            ),

            page_resolved_inputs AS (
                SELECT digest, any(val_dump) AS val_dump
                FROM table_rows
                PREWHERE project_id = {pb_0:String}
                WHERE digest IN (SELECT row_digest FROM page_digests)
                GROUP BY digest
            ),

            page_rows AS (
                SELECT predict_and_score_calls_resolved.call_id AS call_id,
                    predict_and_score_calls_resolved.eval_call_id AS eval_call_id,
                    predict_and_score_calls_resolved.row_digest AS row_digest,
                    page_digests.row_order AS row_order,
                    COALESCE(page_resolved_inputs.val_dump, JSONExtractRaw(predict_and_score_calls_resolved.inputs_dump, 'example')) AS resolved_inputs
                FROM predict_and_score_calls_resolved
                INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
                LEFT JOIN page_resolved_inputs ON page_resolved_inputs.digest = predict_and_score_calls_resolved.row_digest
            ),

            page_calls AS (
                SELECT calls_merged.id AS call_id,
                    any(calls_merged.project_id) AS project_id,
                    any(calls_merged.trace_id) AS trace_id,
                    any(calls_merged.op_name) AS op_name,
                    any(calls_merged.started_at) AS started_at,
                    any(calls_merged.ended_at) AS ended_at,
                    any(calls_merged.inputs_dump) AS inputs_dump,
                    any(calls_merged.output_dump) AS output_dump,
                    any(calls_merged.summary_dump) AS summary_dump
                FROM calls_merged
                PREWHERE calls_merged.project_id = {pb_4:String}
                WHERE calls_merged.id IN (SELECT call_id FROM page_rows)
                GROUP BY (calls_merged.project_id, calls_merged.id)
            )
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
        ORDER BY page_rows.row_order ASC
        """,
        pb.get_params(),
        {
            "pb_0": "proj-1",
            "pb_1": ["eval-1"],
            "pb_2": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            "pb_3": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
            "pb_4": "proj-1",
        },
    )


def test_full_query_calls_complete() -> None:
    """Full SQL: lean CTEs + page_calls hydration on calls_complete (no GROUP BY)."""
    pb = ParamBuilder("pb")
    sql = build_eval_results_query(
        project_id="proj-1",
        eval_root_ids=["eval-1"],
        sort_by=None,
        filters=None,
        require_intersection=False,
        limit=10,
        offset=0,
        pb=pb,
        read_table="calls_complete",
    )
    assert_raw_sql(
        sql,
        """
        WITH predict_and_score_calls AS (
                SELECT calls_complete.id AS call_id,
                    calls_complete.parent_id AS eval_call_id,
                    calls_complete.inputs_dump,
                    calls_complete.output_dump,
                    CASE
                        WHEN position(JSON_VALUE(calls_complete.inputs_dump, '$.example'), '/attr/rows/id/') > 0
                            THEN regexpExtract(JSON_VALUE(calls_complete.inputs_dump, '$.example'), '/attr/rows/id/([^/]+)$', 1)
                        ELSE hex(SHA256(JSONExtractRaw(calls_complete.inputs_dump, 'example')))
                    END AS row_digest
                FROM calls_complete
                PREWHERE calls_complete.project_id = {pb_0:String}
                WHERE calls_complete.parent_id IN {pb_1:Array(String)}
                    AND calls_complete.id NOT IN {pb_1:Array(String)}
                    AND (position(calls_complete.op_name, {pb_2:String}) > 0
                        OR position(calls_complete.op_name, {pb_3:String}) > 0)
                    AND calls_complete.deleted_at = {pb_4:DateTime64(3)}
            ),

            predict_and_score_calls_resolved AS (
                SELECT * FROM predict_and_score_calls
            ),

            ranked_digests AS (
                SELECT row_digest,
                    ROW_NUMBER() OVER(ORDER BY row_digest ASC) AS row_order
                FROM predict_and_score_calls_resolved
                GROUP BY row_digest
                HAVING 1=1
            ),

            ranked_digest_count AS (
                SELECT count(*) AS total_rows FROM ranked_digests
            ),

            page_digests AS (
                SELECT row_digest, row_order
                FROM ranked_digests
                ORDER BY row_order
                LIMIT 10
                OFFSET 0
            ),

            page_resolved_inputs AS (
                SELECT digest, any(val_dump) AS val_dump
                FROM table_rows
                PREWHERE project_id = {pb_0:String}
                WHERE digest IN (SELECT row_digest FROM page_digests)
                GROUP BY digest
            ),

            page_rows AS (
                SELECT predict_and_score_calls_resolved.call_id AS call_id,
                    predict_and_score_calls_resolved.eval_call_id AS eval_call_id,
                    predict_and_score_calls_resolved.row_digest AS row_digest,
                    page_digests.row_order AS row_order,
                    COALESCE(page_resolved_inputs.val_dump, JSONExtractRaw(predict_and_score_calls_resolved.inputs_dump, 'example')) AS resolved_inputs
                FROM predict_and_score_calls_resolved
                INNER JOIN page_digests ON predict_and_score_calls_resolved.row_digest = page_digests.row_digest
                LEFT JOIN page_resolved_inputs ON page_resolved_inputs.digest = predict_and_score_calls_resolved.row_digest
            ),

            page_calls AS (
                SELECT calls_complete.id AS call_id,
                    calls_complete.project_id,
                    calls_complete.trace_id,
                    calls_complete.op_name,
                    calls_complete.started_at,
                    calls_complete.ended_at,
                    calls_complete.inputs_dump,
                    calls_complete.output_dump,
                    calls_complete.summary_dump
                FROM calls_complete
                WHERE calls_complete.project_id = {pb_5:String}
                    AND calls_complete.id IN (SELECT call_id FROM page_rows)
            )
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
        ORDER BY page_rows.row_order ASC
        """,
        pb.get_params(),
        {
            "pb_0": "proj-1",
            "pb_1": ["eval-1"],
            "pb_2": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            "pb_3": EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
            "pb_4": SENTINEL_DATETIME,
            "pb_5": "proj-1",
        },
    )
