from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
)
from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.project_version.types import ReadTable


def test_object_ref_filter_simple() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "output.model.temperature"},
                    {"$literal": 1},
                ]
            }
        )
    )
    cq.add_order("started_at", "desc")
    cq.set_expand_columns(["output.model"])
    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (length(calls_merged.output_refs) > 0
                  OR calls_merged.ended_at IS NULL)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_3:String}), 'null'), '') IN
                      (SELECT ref
                       FROM obj_filter_0)
                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_3:String}), 'null'), ''), '/([^/]+)$', 1) IN
                      (SELECT ref
                       FROM obj_filter_0)))
                   AND ((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) DESC)
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."temperature"',
            "pb_2": 1,
            "pb_3": '$."model"',
        },
    )


def test_object_ref_filter_lt() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.LtOperation.model_validate(
            {
                "$lt": [
                    {"$getField": "output.model.temperature"},
                    {"$literal": 1},
                ]
            }
        )
    )
    cq.add_order("started_at", "desc")
    cq.set_expand_columns(["output.model"])
    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) < {pb_2:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) < {pb_2:UInt64}
           GROUP BY project_id,
                    digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (length(calls_merged.output_refs) > 0
                  OR calls_merged.ended_at IS NULL)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_3:String}), 'null'), '') IN
                      (SELECT ref
                       FROM obj_filter_0)
                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_3:String}), 'null'), ''), '/([^/]+)$', 1) IN
                      (SELECT ref
                       FROM obj_filter_0)))
                   AND ((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) DESC)
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."temperature"',
            "pb_2": 1,
            "pb_3": '$."model"',
        },
    )


def test_object_ref_filter_nested() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "inputs.model.temperature.unit.size"},
                    {"$literal": "large"},
                ]
            }
        )
    )
    cq.set_hardcoded_filter(HardCodedFilter(filter={"trace_roots_only": True}))
    cq.add_order("started_at", "desc")
    cq.set_limit(50)
    cq.set_offset(0)
    cq.set_expand_columns(
        ["inputs.model", "inputs.model.temperature", "inputs.model.temperature.unit"],
    )
    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    digest),
             obj_filter_1 AS
          (SELECT ov.digest,
                  concat('weave-trace-internal:///', ov.project_id, '/object/', ov.object_id, ':', ov.digest) AS ref
           FROM object_versions ov
           WHERE ov.project_id = {pb_0:String}
             AND length(refs) > 0
             AND JSON_VALUE(ov.val_dump, {pb_3:String}) IN (SELECT ref FROM obj_filter_0)
           GROUP BY ov.project_id,
                    ov.object_id,
                    ov.digest),
             obj_filter_2 AS
          (SELECT ov.digest,
                  concat('weave-trace-internal:///', ov.project_id, '/object/', ov.object_id, ':', ov.digest) AS ref
           FROM object_versions ov
           WHERE ov.project_id = {pb_0:String}
             AND length(refs) > 0
             AND JSON_VALUE(ov.val_dump, {pb_4:String}) IN (SELECT ref FROM obj_filter_1)
           GROUP BY ov.project_id,
                    ov.object_id,
                    ov.digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (calls_merged.parent_id IS NULL)
             AND (length(calls_merged.input_refs) > 0
                  OR calls_merged.started_at IS NULL)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_5:String}), 'null'), '') IN
                      (SELECT ref
                       FROM obj_filter_2)
                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_5:String}), 'null'), ''), '/([^/]+)$', 1) IN
                      (SELECT ref
                       FROM obj_filter_2)))
                   AND ((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) DESC
           LIMIT 50
           OFFSET 0)
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."size"',
            "pb_2": "large",
            "pb_3": '$."unit"',
            "pb_4": '$."temperature"',
            "pb_5": '$."model"',
        },
    )


def test_multiple_object_ref_filters() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "inputs.model.temperature"},
                            {"$literal": 1},
                        ]
                    },
                    {
                        "$not": [
                            {
                                "$gt": [
                                    {
                                        "$convert": {
                                            "input": {
                                                "$getField": "inputs.model.temperature"
                                            },
                                            "to": "double",
                                        }
                                    },
                                    {"$literal": 2},
                                ],
                            }
                        ],
                    },
                ]
            }
        )
    )
    cq.set_hardcoded_filter(HardCodedFilter(filter={"trace_roots_only": True}))
    cq.add_order("started_at", "desc")
    cq.set_expand_columns(["inputs.model"])
    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    digest),
            obj_filter_1 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND toFloat64OrNull(JSON_VALUE(val_dump, {pb_1:String})) > {pb_3:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND toFloat64OrNull(JSON_VALUE(val_dump, {pb_1:String})) > {pb_3:UInt64}
           GROUP BY project_id,
                    digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (calls_merged.parent_id IS NULL)
             AND (length(calls_merged.input_refs) > 0
                  OR calls_merged.started_at IS NULL)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), '') IN
                      (SELECT ref
                       FROM obj_filter_0)
                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), ''), '/([^/]+)$', 1) IN
                      (SELECT ref
                       FROM obj_filter_0)))
                   AND ((NOT ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), '') IN
                               (SELECT ref
                                FROM obj_filter_1)
                             OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), ''), '/([^/]+)$', 1) IN
                               (SELECT ref
                                FROM obj_filter_1)))))
                   AND ((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) DESC)
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."temperature"',
            "pb_2": 1,
            "pb_3": 2,
            "pb_4": '$."model"',
        },
    )


def test_object_ref_filter_duplicates_and_similar() -> None:
    """Test duplicate identical conditions and very similar ones to ensure proper deduplication."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    # Identical conditions - should be deduplicated
                    {
                        "$eq": [
                            {"$getField": "inputs.model.temperature"},
                            {"$literal": 1},
                        ]
                    },
                    {
                        "$eq": [
                            {"$getField": "inputs.model.temperature"},
                            {"$literal": 1},
                        ]
                    },
                    # Very similar but different value - should create separate CTEs
                    {
                        "$eq": [
                            {"$getField": "inputs.model.temperature"},
                            {"$literal": 2},
                        ]
                    },
                    # Different field path but same object - should reuse existing CTEs
                    {
                        "$eq": [
                            {"$getField": "inputs.model.max_tokens"},
                            {"$literal": 100},
                        ]
                    },
                    # Same ref path, different value
                    {
                        "$eq": [
                            {"$getField": "inputs.model.max_tokens.size"},
                            {"$literal": 1},
                        ]
                    },
                    # Normal non object ref condition
                    {
                        "$contains": {
                            "input": {"$getField": "inputs.param.message"},
                            "substr": {"$literal": "completed"},
                            "case_insensitive": True,
                        }
                    },
                ]
            }
        )
    )
    cq.set_hardcoded_filter(HardCodedFilter(filter={"trace_roots_only": True}))
    cq.set_expand_columns(["inputs.model"])

    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    digest),
             obj_filter_1 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_3:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_3:UInt64}
           GROUP BY project_id,
                    digest),
             obj_filter_2 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_4:String}) = {pb_5:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_4:String}) = {pb_5:UInt64}
           GROUP BY project_id,
                    digest),
             obj_filter_3 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_6:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_6:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (calls_merged.parent_id IS NULL)
             AND ((lower(calls_merged.inputs_dump) LIKE {pb_10:String}
                  OR calls_merged.inputs_dump IS NULL))
             AND (length(calls_merged.input_refs) > 0
                  OR calls_merged.started_at IS NULL)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
              (SELECT ref
               FROM obj_filter_0)
             OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
              (SELECT ref
               FROM obj_filter_0)))
           AND ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
               (SELECT ref
                FROM obj_filter_0)
             OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
               (SELECT ref
                FROM obj_filter_0)))
           AND ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
               (SELECT ref
                FROM obj_filter_1)
             OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
               (SELECT ref
                FROM obj_filter_1)))
           AND ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
                 (SELECT ref
                  FROM obj_filter_2)
               OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
                 (SELECT ref
                  FROM obj_filter_2)))
           AND ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
               (SELECT ref
                FROM obj_filter_3)
             OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
               (SELECT ref
                FROM obj_filter_3)))
           AND (positionCaseInsensitive(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_8:String}), 'null'), ''), {pb_9:String}) > 0)
           AND ((any(calls_merged.deleted_at) IS NULL))
           AND ((NOT ((any(calls_merged.started_at) IS NULL))))))
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        """,
        {
            "pb_0": "project",
            "pb_1": '$."temperature"',
            "pb_2": 1,
            "pb_3": 2,
            "pb_4": '$."max_tokens"',
            "pb_5": 100,
            "pb_6": '$."max_tokens"."size"',
            "pb_7": '$."model"',
            "pb_8": '$."param"."message"',
            "pb_9": "completed",
            "pb_10": '%"%completed%"%',
        },
    )


def test_object_ref_filter_complex_mixed_conditions() -> None:
    """Test complex scenarios with OR conditions mixing object refs and non-object refs."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_condition(
        tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    # Object ref condition
                    {
                        "$and": [
                            {
                                "$eq": [
                                    {"$getField": "inputs.model.provider"},
                                    {"$literal": "openai"},
                                ]
                            },
                            {
                                "$gt": [
                                    {"$getField": "inputs.model.temperature"},
                                    {"$literal": 0.5},
                                ]
                            },
                        ]
                    },
                    # Non-object ref condition (should go to regular HAVING)
                    {
                        "$eq": [
                            {"$getField": "inputs.prompt"},
                            {"$literal": "test prompt"},
                        ]
                    },
                    # Another object ref with NOT
                    {
                        "$not": [
                            {
                                "$eq": [
                                    {"$getField": "inputs.model.stream"},
                                    {"$literal": True},
                                ]
                            }
                        ]
                    },
                ]
            }
        )
    )
    cq.set_hardcoded_filter(HardCodedFilter(filter={"op_names": ["llm_call"]}))
    cq.add_order("started_at", "desc")
    cq.set_limit(10)
    cq.set_expand_columns(["inputs.model"])

    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    digest),
                           obj_filter_1 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_3:String}) > {pb_4:Float64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_3:String}) > {pb_4:Float64}
           GROUP BY project_id,
                    digest),
                           obj_filter_2 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_5:String}) = {pb_6:Bool}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_5:String}) = {pb_6:Bool}
           GROUP BY project_id,
                    digest),
             filtered_calls AS (
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE ((calls_merged.op_name IN {pb_10:Array(String)})
               OR (calls_merged.op_name IS NULL))
          AND (length(calls_merged.input_refs) > 0
               OR calls_merged.started_at IS NULL)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        HAVING (((((((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
                       (SELECT ref
                        FROM obj_filter_0)
                     OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
                       (SELECT ref
                        FROM obj_filter_0)))
                    AND ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
                           (SELECT ref
                            FROM obj_filter_1)
                         OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
                           (SELECT ref
                            FROM obj_filter_1)))))
                  OR ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_8:String}), 'null'), '') = {pb_9:String}))
                  OR ((NOT ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), '') IN
                             (SELECT ref
                              FROM obj_filter_2)
                           OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_7:String}), 'null'), ''), '/([^/]+)$', 1) IN
                             (SELECT ref
                              FROM obj_filter_2)))))))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
                ORDER BY any(calls_merged.started_at) DESC
                LIMIT 10)
        SELECT calls_merged.id AS id,
               any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."provider"',
            "pb_2": "openai",
            "pb_3": '$."temperature"',
            "pb_4": 0.5,
            "pb_5": '$."stream"',
            "pb_6": True,
            "pb_7": '$."model"',
            "pb_8": '$."prompt"',
            "pb_9": "test prompt",
            "pb_10": ["llm_call"],
        },
    )


def test_object_ref_order_by_simple() -> None:
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_order("inputs.model.temperature", "desc")
    cq.set_expand_columns(["inputs.model"])
    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  nullIf(coalesce(nullIf(JSON_VALUE(any(val_dump), {pb_1:String}), 'null'), ''), '') AS object_val_dump,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  nullIf(coalesce(nullIf(JSON_VALUE(any(val_dump), {pb_1:String}), 'null'), ''), '') AS object_val_dump,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
           GROUP BY project_id,
                    digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           LEFT JOIN obj_filter_0 ON (coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), '') = obj_filter_0.ref
                                      OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), ''), '/([^/]+)$', 1) = obj_filter_0.ref)
           PREWHERE calls_merged.project_id = {pb_0:String}
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY (NOT (JSONType(any(obj_filter_0.object_val_dump)) = 'Null'
                          OR JSONType(any(obj_filter_0.object_val_dump)) IS NULL)) desc, toFloat64OrNull(any(obj_filter_0.object_val_dump)) DESC, toString(any(obj_filter_0.object_val_dump)) DESC)
        SELECT calls_merged.id AS id
        FROM calls_merged
        LEFT JOIN obj_filter_0 ON (coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), '') = obj_filter_0.ref
                                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_merged.inputs_dump, {pb_2:String}), 'null'), ''), '/([^/]+)$', 1) = obj_filter_0.ref)
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        ORDER BY (NOT (JSONType(any(obj_filter_0.object_val_dump)) = 'Null'
                       OR JSONType(any(obj_filter_0.object_val_dump)) IS NULL)) desc, toFloat64OrNull(any(obj_filter_0.object_val_dump)) DESC, toString(any(obj_filter_0.object_val_dump)) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."temperature"',
            "pb_2": '$."model"',
        },
    )


def test_object_ref_filter_heavily_nested_keys() -> None:
    """Test that heavily nested keys are properly quoted in JSON paths."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "inputs.model.config.temperature.value.unit"},
                    {"$literal": "celsius"},
                ]
            }
        )
    )
    cq.set_expand_columns(["inputs.model", "inputs.model.config"])
    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    digest),
             obj_filter_1 AS
          (SELECT ov.digest,
                  concat('weave-trace-internal:///', ov.project_id, '/object/', ov.object_id, ':', ov.digest) AS ref
           FROM object_versions ov
           WHERE ov.project_id = {pb_0:String}
             AND length(refs) > 0
             AND JSON_VALUE(ov.val_dump, {pb_3:String}) IN (SELECT ref FROM obj_filter_0)
           GROUP BY ov.project_id,
                    ov.object_id,
                    ov.digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (length(calls_merged.input_refs) > 0
                  OR calls_merged.started_at IS NULL)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), '') IN
                      (SELECT ref
                       FROM obj_filter_1)
                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), ''), '/([^/]+)$', 1) IN
                      (SELECT ref
                       FROM obj_filter_1)))
                   AND ((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        )
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        """,
        {
            "pb_0": "project",
            "pb_1": '$."temperature"."value"."unit"',
            "pb_2": "celsius",
            "pb_3": '$."config"',
            "pb_4": '$."model"',
        },
    )


def test_object_ref_filter_complex_nested_path() -> None:
    """Test the specific case mentioned: path = "a.b.c.d.e" with expand_columns=["a.b", "a.b.c.d"]."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "inputs.a.b.c.d.e"},
                    {"$literal": "test_value"},
                ]
            }
        )
    )
    cq.set_hardcoded_filter(HardCodedFilter(filter={"trace_roots_only": True}))
    cq.add_order("started_at", "desc")
    cq.set_expand_columns(["inputs.a.b", "inputs.a.b.c.d"])

    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    digest),
             obj_filter_1 AS
          (SELECT ov.digest,
                  concat('weave-trace-internal:///', ov.project_id, '/object/', ov.object_id, ':', ov.digest) AS ref
           FROM object_versions ov
           WHERE ov.project_id = {pb_0:String}
             AND length(refs) > 0
             AND JSON_VALUE(ov.val_dump, {pb_3:String}) IN (SELECT ref FROM obj_filter_0)
           GROUP BY ov.project_id,
                    ov.object_id,
                    ov.digest),
             filtered_calls AS
          (SELECT calls_merged.id AS id
           FROM calls_merged
           PREWHERE calls_merged.project_id = {pb_0:String}
           WHERE (calls_merged.parent_id IS NULL)
             AND (length(calls_merged.input_refs) > 0
                  OR calls_merged.started_at IS NULL)
           GROUP BY (calls_merged.project_id,
                     calls_merged.id)
           HAVING (((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), '') IN
                      (SELECT ref
                       FROM obj_filter_1)
                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_4:String}), 'null'), ''), '/([^/]+)$', 1) IN
                      (SELECT ref
                       FROM obj_filter_1)))
                   AND ((any(calls_merged.deleted_at) IS NULL))
                   AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
           ORDER BY any(calls_merged.started_at) DESC)
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_0:String}
        WHERE (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id,
                  calls_merged.id)
        ORDER BY any(calls_merged.started_at) DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."e"',
            "pb_2": "test_value",
            "pb_3": '$."c"."d"',
            "pb_4": '$."a"."b"',
        },
    )


def test_object_ref_filter_calls_complete() -> None:
    """Test object ref filtering with calls_complete table.

    This test ensures that when using ReadTable.CALLS_COMPLETE:
    1. No aggregate functions like any() are used
    2. No GROUP BY clause is generated
    3. Filter conditions use AND clauses instead of HAVING
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "output.model.temperature"},
                    {"$literal": 1},
                ]
            }
        )
    )
    cq.add_order("started_at", "desc")
    cq.set_expand_columns(["output.model"])
    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:UInt64}
           GROUP BY project_id,
                    digest),
             filtered_calls AS
          (SELECT calls_complete.id AS id
           FROM calls_complete PREWHERE calls_complete.project_id = {pb_0:String}
           WHERE (length(calls_complete.output_refs) > 0
                  OR calls_complete.ended_at = {pb_5:DateTime64(6)})
           AND (((coalesce(nullIf(JSON_VALUE(calls_complete.output_dump, {pb_3:String}), 'null'), '') IN
                      (SELECT ref
                       FROM obj_filter_0)
                   OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_complete.output_dump, {pb_3:String}), 'null'), ''), '/([^/]+)$', 1) IN
                      (SELECT ref
                       FROM obj_filter_0)))
                   AND ((calls_complete.deleted_at = {pb_4:DateTime64(3)}))
                   AND ((NOT ((calls_complete.started_at IS NULL)))))
           ORDER BY calls_complete.started_at DESC)
        SELECT calls_complete.id AS id
        FROM calls_complete PREWHERE calls_complete.project_id = {pb_0:String}
        WHERE (calls_complete.id IN filtered_calls)
        ORDER BY calls_complete.started_at DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."temperature"',
            "pb_2": 1,
            "pb_3": '$."model"',
            "pb_4": SENTINEL_DATETIME,
            "pb_5": SENTINEL_DATETIME,
        },
    )


def test_object_ref_filter_calls_complete_mixed_conditions() -> None:
    """Test calls_complete with mixed object ref and non-object ref conditions.

    Verifies that both object ref conditions and regular conditions work
    correctly without aggregate functions when using calls_complete.
    """
    cq = CallsQuery(project_id="project", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_field("inputs")
    cq.add_condition(
        tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    # Object ref condition
                    {
                        "$eq": [
                            {"$getField": "inputs.model.provider"},
                            {"$literal": "openai"},
                        ]
                    },
                    # Non-object ref condition
                    {
                        "$eq": [
                            {"$getField": "inputs.prompt"},
                            {"$literal": "test prompt"},
                        ]
                    },
                ]
            }
        )
    )
    cq.set_hardcoded_filter(HardCodedFilter(filter={"trace_roots_only": True}))
    cq.add_order("started_at", "desc")
    cq.set_limit(10)
    cq.set_expand_columns(["inputs.model"])

    assert_sql(
        cq,
        """
        WITH obj_filter_0 AS
          (SELECT digest,
                  concat('weave-trace-internal:///', project_id, '/object/', object_id, ':', digest) AS ref
           FROM object_versions
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    object_id,
                    digest

           UNION ALL

           SELECT digest,
                  digest as ref
           FROM table_rows
           WHERE project_id = {pb_0:String}
             AND JSON_VALUE(val_dump, {pb_1:String}) = {pb_2:String}
           GROUP BY project_id,
                    digest),
             filtered_calls AS (
        SELECT calls_complete.id AS id
        FROM calls_complete PREWHERE calls_complete.project_id = {pb_0:String}
        WHERE (calls_complete.parent_id = {pb_7:String})
          AND (length(calls_complete.input_refs) > 0
               OR calls_complete.started_at IS NULL)
        AND (((((coalesce(nullIf(JSON_VALUE(calls_complete.inputs_dump, {pb_3:String}), 'null'), '') IN
                       (SELECT ref
                        FROM obj_filter_0)
                     OR regexpExtract(coalesce(nullIf(JSON_VALUE(calls_complete.inputs_dump, {pb_3:String}), 'null'), ''), '/([^/]+)$', 1) IN
                       (SELECT ref
                        FROM obj_filter_0)))
                  OR ((coalesce(nullIf(JSON_VALUE(calls_complete.inputs_dump, {pb_4:String}), 'null'), '') = {pb_5:String}))))
                AND ((calls_complete.deleted_at = {pb_6:DateTime64(3)}))
                AND ((NOT ((calls_complete.started_at IS NULL)))))
                ORDER BY calls_complete.started_at DESC
                LIMIT 10)
        SELECT calls_complete.id AS id,
               calls_complete.inputs_dump AS inputs_dump
        FROM calls_complete PREWHERE calls_complete.project_id = {pb_0:String}
        WHERE (calls_complete.id IN filtered_calls)
        ORDER BY calls_complete.started_at DESC
        """,
        {
            "pb_0": "project",
            "pb_1": '$."provider"',
            "pb_2": "openai",
            "pb_3": '$."model"',
            "pb_4": '$."prompt"',
            "pb_5": "test prompt",
            "pb_6": SENTINEL_DATETIME,
            "pb_7": "",
        },
    )
