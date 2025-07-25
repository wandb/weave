import sqlparse

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder


def assert_sql(cq: CallsQuery, exp_query, exp_params):
    """Helper function to assert SQL queries match expected output."""
    pb = ParamBuilder("pb")
    query = cq.as_sql(pb)
    params = pb.get_params()

    exp_formatted = sqlparse.format(exp_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert exp_formatted == found_formatted
    assert exp_params == params


def test_basic_descendants_query() -> None:
    """Test basic descendants query with depth limit."""
    cq = CallsQuery(
        project_id="project",
        descendant_query_parent_ids=["root_call_123"],
        descendant_query_depth=2,
    )
    cq.add_field("id")
    cq.add_field("parent_id")

    assert_sql(
        cq,
        """
        WITH RECURSIVE descendant_call_ids AS (
            SELECT
                id,
                0 AS depth
            FROM calls_merged
            WHERE project_id = {pb_1:String}
                AND id IN {pb_2:Array(String)}

            UNION ALL

            SELECT
                c.id,
                d.depth + 1 AS depth
            FROM calls_merged c
            INNER JOIN descendant_call_ids d ON c.parent_id = d.id
            WHERE c.project_id = {pb_1:String}
                AND d.depth < {pb_0:UInt64}
        ),
        filtered_calls AS (
            SELECT calls_merged.id AS id
            FROM calls_merged
            WHERE calls_merged.project_id = {pb_1:String}
              AND (calls_merged.id IN (SELECT id FROM descendant_call_ids))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.parent_id) AS parent_id
        FROM calls_merged
        WHERE calls_merged.project_id = {pb_1:String}
          AND (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {"pb_0": 2, "pb_1": "project", "pb_2": ["root_call_123"]},
    )


def test_descendants_with_feedback_and_ordering() -> None:
    """Test descendants query with feedback sorting and filtering."""
    cq = CallsQuery(
        project_id="project",
        descendant_query_parent_ids=["parent_call_456"],
        descendant_query_depth=3,
    )
    cq.add_field("id")
    cq.add_field("op_name")
    cq.add_order("feedback.[wandb.runnable.eval].payload.score", "desc")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["llm_call", "evaluation"],
            )
        )
    )
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "feedback.[wandb.runnable.eval].payload.score"},
                    {"$literal": 0.8},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        WITH RECURSIVE descendant_call_ids AS (
            SELECT
                id,
                0 AS depth
            FROM calls_merged
            WHERE project_id = {pb_1:String}
                AND id IN {pb_2:Array(String)}

            UNION ALL

            SELECT
                c.id,
                d.depth + 1 AS depth
            FROM calls_merged c
            INNER JOIN descendant_call_ids d ON c.parent_id = d.id
            WHERE c.project_id = {pb_1:String}
                AND d.depth < {pb_0:UInt64}
        ),
        filtered_calls AS (
            SELECT calls_merged.id AS id
            FROM calls_merged
            LEFT JOIN (
                SELECT * FROM feedback WHERE feedback.project_id = {pb_1:String}
            ) AS feedback ON (
                feedback.weave_ref = concat('weave-trace-internal:///',
                {pb_1:String},
                '/call/',
                calls_merged.id))
            WHERE calls_merged.project_id = {pb_1:String}
                AND (calls_merged.id IN (SELECT id FROM descendant_call_ids))
                AND ((calls_merged.op_name IN {pb_6:Array(String)})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_3:String}),
                {pb_4:String}), 'null'), '') > {pb_5:Float64}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
            ORDER BY
                (NOT (JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_3:String}),
                {pb_7:String}) = 'Null'
                    OR JSONType(anyIf(feedback.payload_dump,
                    feedback.feedback_type = {pb_3:String}),
                    {pb_7:String}) IS NULL)) desc,
                toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_3:String}),
                {pb_4:String}), 'null'), '')) DESC,
                toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_3:String}),
                {pb_4:String}), 'null'), '')) DESC
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.op_name) AS op_name
        FROM calls_merged
        LEFT JOIN (
            SELECT * FROM feedback WHERE feedback.project_id = {pb_1:String}
        ) AS feedback ON (
            feedback.weave_ref = concat('weave-trace-internal:///',
            {pb_1:String},
            '/call/',
            calls_merged.id))
        WHERE calls_merged.project_id = {pb_1:String}
          AND (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        ORDER BY
            (NOT (JSONType(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_3:String}),
            {pb_7:String}) = 'Null'
                OR JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {pb_3:String}),
                {pb_7:String}) IS NULL)) desc,
            toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_3:String}),
            {pb_4:String}), 'null'), '')) DESC,
            toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
            feedback.feedback_type = {pb_3:String}),
            {pb_4:String}), 'null'), '')) DESC
        """,
        {
            "pb_0": 3,
            "pb_1": "project",
            "pb_2": ["parent_call_456"],
            "pb_3": "wandb.runnable.eval",
            "pb_4": '$."score"',
            "pb_5": 0.8,
            "pb_6": ["llm_call", "evaluation"],
            "pb_7": "score",
        },
    )


def test_descendants_with_complex_filters_and_offset() -> None:
    """Test descendants query with complex JSON filtering, datetime conditions, and pagination."""
    cq = CallsQuery(
        project_id="project",
        descendant_query_parent_ids=["root_evaluation_call"],
        descendant_query_depth=5,
    )
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("started_at")
    cq.set_limit(25)
    cq.set_offset(100)
    cq.add_order("started_at", "desc")

    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["dataset.evaluate", "model.predict"],
            )
        )
    )

    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$gt": [
                            {"$getField": "started_at"},
                            {"$literal": 1709251200},  # 2024-03-01 00:00:00 UTC
                        ]
                    },
                    {
                        "$eq": [
                            {"$getField": "inputs.model_config.temperature"},
                            {"$literal": "0.7"},
                        ]
                    },
                    {
                        "$contains": {
                            "input": {"$getField": "inputs.prompt"},
                            "substr": {"$literal": "evaluate"},
                            "case_insensitive": True,
                        }
                    },
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        WITH RECURSIVE descendant_call_ids AS
  (SELECT id,
          0 AS depth
   FROM calls_merged
   WHERE project_id = {pb_1:String}
     AND id IN {pb_2:Array(String)}
   UNION ALL SELECT c.id,
                    d.depth + 1 AS depth
   FROM calls_merged c
   INNER JOIN descendant_call_ids d ON c.parent_id = d.id
   WHERE c.project_id = {pb_1:String}
     AND d.depth < {pb_0:UInt64}),
               filtered_calls AS
  (SELECT calls_merged.id AS id
   FROM calls_merged
   WHERE calls_merged.project_id = {pb_1:String}
     AND (calls_merged.id IN
            (SELECT id
             FROM descendant_call_ids))
     AND (calls_merged.sortable_datetime > {pb_11:String})
     AND ((calls_merged.op_name IN {pb_8:Array(String)})
          OR (calls_merged.op_name IS NULL))
     AND ((calls_merged.inputs_dump LIKE {pb_9:String}
           OR calls_merged.inputs_dump IS NULL)
          AND (lower(calls_merged.inputs_dump) LIKE {pb_10:String}
               OR calls_merged.inputs_dump IS NULL))
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   HAVING (((any(calls_merged.started_at) > {pb_3:UInt64}))
           AND ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), '') = {pb_5:String}))
           AND (positionCaseInsensitive(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_6:String}), 'null'), ''), {pb_7:String}) > 0)
           AND ((any(calls_merged.deleted_at) IS NULL))
           AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
   ORDER BY any(calls_merged.started_at) DESC
   LIMIT 25
   OFFSET 100)
SELECT calls_merged.id AS id,
       any(calls_merged.inputs_dump) AS inputs_dump,
       any(calls_merged.started_at) AS started_at
FROM calls_merged
WHERE calls_merged.project_id = {pb_1:String}
  AND (calls_merged.id IN filtered_calls)
GROUP BY (calls_merged.project_id,
          calls_merged.id)
ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": 5,
            "pb_1": "project",
            "pb_2": ["root_evaluation_call"],
            "pb_3": 1709251200,
            "pb_4": '$."model_config"."temperature"',
            "pb_5": "0.7",
            "pb_6": '$."prompt"',
            "pb_7": "evaluate",
            "pb_8": ["dataset.evaluate", "model.predict"],
            "pb_9": '%"0.7"%',
            "pb_10": '%"%evaluate%"%',
            "pb_11": "2024-02-29 23:55:00.000000",
        },
    )


def test_descendants_unlimited_depth_with_trace_filtering() -> None:
    """Test descendants query with unlimited depth and trace-level filtering."""
    cq = CallsQuery(
        project_id="project", descendant_query_parent_ids=["trace_root_abc123"]
    )
    cq.add_field("id")
    cq.add_field("trace_id")
    cq.add_field("op_name")
    cq.add_field("summary")
    # No depth set = unlimited depth

    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                trace_ids=["abc123def456"],
                trace_roots_only=False,  # We want all descendants, not just roots
            )
        )
    )

    cq.add_condition(
        tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {
                        "$eq": [
                            {"$getField": "summary.weave.status"},
                            {"$literal": "error"},
                        ]
                    },
                    {
                        "$gt": [
                            {"$getField": "summary.weave.latency_ms"},
                            {"$literal": 5000},  # > 5 seconds
                        ]
                    },
                ]
            }
        )
    )

    cq.add_order("summary.weave.latency_ms", "desc")
    cq.set_limit(10)

    assert_sql(
        cq,
        """
        WITH RECURSIVE descendant_call_ids AS
  (SELECT id,
          0 AS depth
   FROM calls_merged
   WHERE project_id = {pb_1:String}
     AND id IN {pb_2:Array(String)}
   UNION ALL SELECT c.id,
                    d.depth + 1 AS depth
   FROM calls_merged c
   INNER JOIN descendant_call_ids d ON c.parent_id = d.id
   WHERE c.project_id = {pb_1:String}
     AND d.depth < {pb_0:UInt64}),
               filtered_calls AS
  (SELECT calls_merged.id AS id
   FROM calls_merged
   WHERE calls_merged.project_id = {pb_1:String}
     AND (calls_merged.id IN
            (SELECT id
             FROM descendant_call_ids))
     AND (calls_merged.trace_id = {pb_9:String}
          OR calls_merged.trace_id IS NULL)
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   HAVING ((((CASE
                  WHEN any(calls_merged.exception) IS NOT NULL THEN {pb_4:String}
                  WHEN IFNULL(toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.summary_dump), {pb_3:String}), 'null'), '')), 0) > 0 THEN {pb_7:String}
                  WHEN any(calls_merged.ended_at) IS NULL THEN {pb_5:String}
                  ELSE {pb_6:String}
              END = {pb_4:String})
             OR (CASE
                     WHEN any(calls_merged.ended_at) IS NULL THEN NULL
                     ELSE (toUnixTimestamp64Milli(any(calls_merged.ended_at)) - toUnixTimestamp64Milli(any(calls_merged.started_at)))
                 END > {pb_8:UInt64})))
           AND ((any(calls_merged.deleted_at) IS NULL))
           AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
   ORDER BY CASE
                WHEN any(calls_merged.ended_at) IS NULL THEN NULL
                ELSE (toUnixTimestamp64Milli(any(calls_merged.ended_at)) - toUnixTimestamp64Milli(any(calls_merged.started_at)))
            END DESC
   LIMIT 10)
SELECT calls_merged.id AS id,
       any(calls_merged.trace_id) AS trace_id,
       any(calls_merged.op_name) AS op_name,
       any(calls_merged.summary_dump) AS summary_dump
FROM calls_merged
WHERE calls_merged.project_id = {pb_1:String}
  AND (calls_merged.id IN filtered_calls)
GROUP BY (calls_merged.project_id,
          calls_merged.id)
ORDER BY CASE
             WHEN any(calls_merged.ended_at) IS NULL THEN NULL
             ELSE (toUnixTimestamp64Milli(any(calls_merged.ended_at)) - toUnixTimestamp64Milli(any(calls_merged.started_at)))
         END DESC
        """,
        {
            "pb_0": 100,
            "pb_1": "project",
            "pb_2": ["trace_root_abc123"],
            "pb_3": '$."status_counts"."error"',
            "pb_4": "error",
            "pb_5": "running",
            "pb_6": "success",
            "pb_7": "descendant_error",
            "pb_8": 5000,
            "pb_9": "abc123def456",
        },
    )


def test_descendants_with_object_reference_filtering() -> None:
    """Test descendants query with object reference filtering on model configuration."""
    cq = CallsQuery(
        project_id="project",
        descendant_query_parent_ids=["llm_root_call_999"],
        descendant_query_depth=3,
    )
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_field("op_name")
    cq.set_limit(20)

    # Search descendants of a root LLM call
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["openai.chat.completions", "anthropic.messages"],
            )
        )
    )

    # Filter for descendants where the model has specific temperature and provider settings
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "inputs.model.provider"},
                            {"$literal": "openai"},
                        ]
                    }
                ]
            }
        )
    )

    cq.add_order("inputs.model.temperature", "desc")

    # Expand the model object reference so we can filter/order by its fields
    cq.set_expand_columns(["inputs.model"])

    assert_sql(
        cq,
        """
        WITH RECURSIVE descendant_call_ids AS
  (SELECT id,
          0 AS depth
   FROM calls_merged
   WHERE project_id = {pb_0:String}
     AND id IN {pb_5:Array(String)}
   UNION ALL SELECT c.id,
                    d.depth + 1 AS depth
   FROM calls_merged c
   INNER JOIN descendant_call_ids d ON c.parent_id = d.id
   WHERE c.project_id = {pb_0:String}
     AND d.depth < {pb_4:UInt64}),
               obj_filter_0 AS
  (SELECT digest,
          concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
   FROM object_versions
   WHERE project_id = {pb_0:String}
     AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
   GROUP BY project_id,
            object_id,
            digest
   UNION ALL SELECT digest,
                    digest as ref
   FROM table_rows
   WHERE project_id = {pb_0:String}
     AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
   GROUP BY project_id,
            digest),
               obj_filter_1 AS
  (SELECT digest,
          nullIf(coalesce(nullIf(JSON_VALUE(any(val_dump), {pb_3:String}), 'null'), ''), '') AS object_val_dump,
          concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
   FROM object_versions
   WHERE project_id = {pb_0:String}
   GROUP BY project_id,
            object_id,
            digest
   UNION ALL SELECT digest,
                    nullIf(coalesce(nullIf(JSON_VALUE(any(val_dump), {pb_3:String}), 'null'), ''), '') AS object_val_dump,
                    digest as ref
   FROM table_rows
   WHERE project_id = {pb_0:String}
   GROUP BY project_id,
            digest),
               filtered_calls AS
  (SELECT calls_merged.id AS id
   FROM calls_merged
   LEFT JOIN obj_filter_1 ON (coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_6:String}), 'null'), '') = obj_filter_1.ref
                              OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_6:String}), 'null'), ''), '/([^/]+)$', 1) = obj_filter_1.ref)
   WHERE calls_merged.project_id = {pb_0:String}
     AND (calls_merged.id IN
            (SELECT id
             FROM descendant_call_ids))
     AND ((calls_merged.op_name IN {pb_7:Array(String)})
          OR (calls_merged.op_name IS NULL))
     AND (length(calls_merged.input_refs) > 0
          OR calls_merged.started_at IS NULL)
   GROUP BY (calls_merged.project_id,
             calls_merged.id)
   HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_6:String}), 'null'), '') IN
               (SELECT ref
                FROM obj_filter_0)
             OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_6:String}), 'null'), ''), '/([^/]+)$', 1) IN
               (SELECT ref
                FROM obj_filter_0)))
           AND ((any(calls_merged.deleted_at) IS NULL))
           AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
   ORDER BY (NOT (JSONType(any(obj_filter_1.object_val_dump)) = 'Null'
                  OR JSONType(any(obj_filter_1.object_val_dump)) IS NULL)) desc, toFloat64OrNull(any(obj_filter_1.object_val_dump)) DESC, toString(any(obj_filter_1.object_val_dump)) DESC
   LIMIT 20)
SELECT calls_merged.id AS id,
       any(calls_merged.inputs_dump) AS inputs_dump,
       any(calls_merged.op_name) AS op_name
FROM calls_merged
LEFT JOIN obj_filter_1 ON (coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_6:String}), 'null'), '') = obj_filter_1.ref
                           OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_6:String}), 'null'), ''), '/([^/]+)$', 1) = obj_filter_1.ref)
WHERE calls_merged.project_id = {pb_0:String}
  AND (calls_merged.id IN filtered_calls)
GROUP BY (calls_merged.project_id,
          calls_merged.id)
ORDER BY (NOT (JSONType(any(obj_filter_1.object_val_dump)) = 'Null'
               OR JSONType(any(obj_filter_1.object_val_dump)) IS NULL)) desc, toFloat64OrNull(any(obj_filter_1.object_val_dump)) DESC, toString(any(obj_filter_1.object_val_dump)) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."provider"',
            "pb_2": "openai",
            "pb_3": '$."temperature"',
            "pb_4": 3,
            "pb_5": ["llm_root_call_999"],
            "pb_6": '$."model"',
            "pb_7": ["openai.chat.completions", "anthropic.messages"],
        },
    )
