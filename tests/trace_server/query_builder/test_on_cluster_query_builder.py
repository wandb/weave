"""Tests for CallsQuery with distributed mode (ON CLUSTER clause).

These tests verify that when cluster_name is set, the ON CLUSTER clause
is properly added to all table references in the generated SQL.
"""

import pytest
import sqlparse

from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    build_calls_complete_update_end_query,
    build_calls_stats_query,
)
from weave.trace_server.orm import ParamBuilder

CLUSTER_NAME = "weave_cluster"


def test_query_baseline_with_cluster() -> None:
    """Test basic query with ON CLUSTER clause added to calls_merged table."""
    cq = CallsQuery(project_id="project", cluster_name=CLUSTER_NAME)
    cq.add_field("id")
    assert_sql(
        cq,
        f"""
        SELECT calls_merged.id AS id
        FROM calls_merged ON CLUSTER {CLUSTER_NAME}
        WHERE calls_merged.project_id = {{pb_0:String}}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((
                any(calls_merged.deleted_at) IS NULL
            ))
            AND
            ((
               NOT ((
                  any(calls_merged.started_at) IS NULL
               ))
            ))
        )
        """,
        {"pb_0": "project"},
    )


def test_query_with_cte_optimization_and_cluster() -> None:
    """Test query with CTE optimization pattern (filter_query + select_query).

    This tests that cluster_name is propagated to both the filter and select queries
    when the optimization pattern creates CTEs.
    """
    cq = CallsQuery(project_id="project", cluster_name=CLUSTER_NAME)
    cq.add_field("id")
    cq.add_field("inputs")
    cq.set_hardcoded_filter(
        HardCodedFilter(
            filter=tsi.CallsFilter(
                op_names=["a", "b"],
            )
        )
    )
    assert_sql(
        cq,
        f"""
        WITH filtered_calls AS (
            SELECT
                calls_merged.id AS id
            FROM calls_merged ON CLUSTER {CLUSTER_NAME}
            WHERE calls_merged.project_id = {{pb_1:String}}
                AND ((calls_merged.op_name IN {{pb_0:Array(String)}})
                    OR (calls_merged.op_name IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
        )
        SELECT
            calls_merged.id AS id,
            any(calls_merged.inputs_dump) AS inputs_dump
        FROM calls_merged ON CLUSTER {CLUSTER_NAME}
        WHERE
            calls_merged.project_id = {{pb_1:String}}
        AND
            (calls_merged.id IN filtered_calls)
        GROUP BY (calls_merged.project_id, calls_merged.id)
        """,
        {"pb_0": ["a", "b"], "pb_1": "project"},
    )


def test_query_with_feedback_join_and_cluster() -> None:
    """Test query with feedback join includes ON CLUSTER for feedback table."""
    cq = CallsQuery(project_id="project", cluster_name=CLUSTER_NAME)
    cq.add_field("id")
    cq.add_order("feedback.[wandb.runnable.my_op].payload.output.expected", "desc")
    assert_sql(
        cq,
        f"""
            SELECT
                calls_merged.id AS id
            FROM
                calls_merged ON CLUSTER {CLUSTER_NAME}
            LEFT JOIN (
                SELECT * FROM feedback ON CLUSTER {CLUSTER_NAME} WHERE feedback.project_id = {{pb_4:String}}
            ) AS feedback ON (
                feedback.weave_ref = concat('weave-trace-internal:///',
                {{pb_4:String}},
                '/call/',
                calls_merged.id))
            WHERE
                calls_merged.project_id = {{pb_4:String}}
            GROUP BY
                (calls_merged.project_id,
                calls_merged.id)
            HAVING
                (((any(calls_merged.deleted_at) IS NULL))
                    AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
            ORDER BY
                (NOT (JSONType(anyIf(feedback.payload_dump,
                feedback.feedback_type = {{pb_0:String}}),
                {{pb_1:String}},
                {{pb_2:String}}) = 'Null'
                    OR JSONType(anyIf(feedback.payload_dump,
                    feedback.feedback_type = {{pb_0:String}}),
                    {{pb_1:String}},
                    {{pb_2:String}}) IS NULL)) desc,
                toFloat64OrNull(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
                feedback.feedback_type = {{pb_0:String}}),
                {{pb_3:String}}), 'null'), '')) DESC,
                toString(coalesce(nullIf(JSON_VALUE(anyIf(feedback.payload_dump,
                feedback.feedback_type = {{pb_0:String}}),
                {{pb_3:String}}), 'null'), '')) DESC
            """,
        {
            "pb_0": "wandb.runnable.my_op",
            "pb_1": "output",
            "pb_2": "expected",
            "pb_3": '$."output"."expected"',
            "pb_4": "project",
        },
    )


def test_storage_size_fields_with_cluster() -> None:
    """Test querying with storage size fields includes ON CLUSTER for calls_merged_stats."""
    cq = CallsQuery(
        project_id="test/project",
        include_storage_size=True,
        cluster_name=CLUSTER_NAME,
    )
    cq.add_field("id")
    cq.add_field("storage_size_bytes")

    assert_sql(
        cq,
        f"""
        SELECT calls_merged.id AS id,
           any(storage_size_tbl.storage_size_bytes) AS storage_size_bytes
        FROM calls_merged ON CLUSTER {CLUSTER_NAME}
        LEFT JOIN
        (SELECT id,
                sum(COALESCE(attributes_size_bytes, 0) + COALESCE(inputs_size_bytes, 0) + COALESCE(output_size_bytes, 0) + COALESCE(summary_size_bytes, 0)) AS storage_size_bytes
        FROM calls_merged_stats ON CLUSTER {CLUSTER_NAME}
        WHERE project_id = {{pb_0:String}}
        GROUP BY id) AS storage_size_tbl ON calls_merged.id = storage_size_tbl.id
        WHERE calls_merged.project_id = {{pb_0:String}}
        GROUP BY (calls_merged.project_id,
                calls_merged.id)
        HAVING (((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL)))))
        """,
        {"pb_0": "test/project"},
    )


def test_set_cluster_name_method() -> None:
    """Test the set_cluster_name method for method chaining."""
    cq = CallsQuery(project_id="project")
    cq.add_field("id")

    # Initially no cluster name
    pb = ParamBuilder("pb")
    query_without_cluster = cq.as_sql(pb)
    assert "ON CLUSTER" not in query_without_cluster

    # Set cluster name via method
    cq.set_cluster_name(CLUSTER_NAME)
    pb = ParamBuilder("pb")
    query_with_cluster = cq.as_sql(pb)
    assert f"ON CLUSTER {CLUSTER_NAME}" in query_with_cluster

    # Clear cluster name
    cq.set_cluster_name(None)
    pb = ParamBuilder("pb")
    query_cleared = cq.as_sql(pb)
    assert "ON CLUSTER" not in query_cleared


def test_stats_query_with_cluster() -> None:
    """Test that build_calls_stats_query includes ON CLUSTER in distributed mode."""
    import sqlparse

    req = tsi.CallsQueryStatsReq(
        project_id="test/project",
        filter=tsi.CallsFilter(op_names=["my_op"]),
    )

    # With cluster_name - includes ON CLUSTER
    pb = ParamBuilder("pb")
    query, _ = build_calls_stats_query(req, pb, cluster_name=CLUSTER_NAME)
    params = pb.get_params()

    expected_query = f"""
    SELECT count()
    FROM (
        SELECT calls_merged.id AS id
        FROM calls_merged ON CLUSTER {CLUSTER_NAME}
        WHERE calls_merged.project_id = {{pb_1:String}}
            AND ((calls_merged.op_name IN {{pb_0:Array(String)}})
                OR (calls_merged.op_name IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
    )
    """
    expected_params = {"pb_0": ["my_op"], "pb_1": "test/project"}

    actual_formatted = sqlparse.format(query.strip(), reindent=True)
    expected_formatted = sqlparse.format(expected_query.strip(), reindent=True)
    assert actual_formatted == expected_formatted, (
        f"Query mismatch:\nExpected:\n{expected_formatted}\n\nGot:\n{actual_formatted}"
    )
    assert params == expected_params, f"Params mismatch: {params} != {expected_params}"


def test_stats_query_optimized_with_cluster() -> None:
    """Test that optimized stats queries include ON CLUSTER in distributed mode.

    This tests the optimized path (limit=1, no filters) which bypasses CallsQuery.
    """
    # This request triggers the optimized _optimized_project_contains_call_query path
    req = tsi.CallsQueryStatsReq(
        project_id="test/project",
        limit=1,
        # No filter, no query - triggers optimization
    )

    # With cluster_name - includes ON CLUSTER
    pb = ParamBuilder("pb")
    query, _ = build_calls_stats_query(req, pb, cluster_name=CLUSTER_NAME)
    params = pb.get_params()

    expected_query = f"""
    SELECT toUInt8(count()) AS has_any
    FROM (
        SELECT 1
        FROM calls_merged ON CLUSTER {CLUSTER_NAME}
        WHERE project_id = {{pb_0:String}}
        LIMIT 1
    )
    """
    expected_params = {"pb_0": "test/project"}

    actual_formatted = sqlparse.format(query.strip(), reindent=True)
    expected_formatted = sqlparse.format(expected_query.strip(), reindent=True)
    assert actual_formatted == expected_formatted, (
        f"Query mismatch:\nExpected:\n{expected_formatted}\n\nGot:\n{actual_formatted}"
    )
    assert params == expected_params, f"Params mismatch: {params} != {expected_params}"


@pytest.mark.parametrize(
    ("table_name", "cluster_name", "expected_table_clause"),
    [
        # In distributed mode: use _local table with ON CLUSTER
        (
            "calls_complete_local",
            CLUSTER_NAME,
            f"calls_complete_local ON CLUSTER {CLUSTER_NAME}",
        ),
        # In non-distributed mode: use regular table without ON CLUSTER
        ("calls_complete", None, "calls_complete"),
    ],
    ids=["distributed_mode", "non_distributed_mode"],
)
def test_update_query_cluster_support(
    table_name: str, cluster_name: str | None, expected_table_clause: str
) -> None:
    """Test that build_calls_complete_update_end_query handles ON CLUSTER correctly.

    In distributed mode, UPDATE statements must target the local table
    (calls_complete_local) with ON CLUSTER clause. In non-distributed mode,
    we target the regular table without ON CLUSTER.
    """
    query = build_calls_complete_update_end_query(
        table_name=table_name,
        project_id_param="project_id",
        started_at_param="started_at",
        id_param="id",
        ended_at_param="ended_at",
        exception_param="exception",
        output_dump_param="output_dump",
        summary_dump_param="summary_dump",
        output_refs_param="output_refs",
        wb_run_step_end_param="wb_run_step_end",
        cluster_name=cluster_name,
    )

    expected = f"""
        UPDATE {expected_table_clause}
        SET
            ended_at = fromUnixTimestamp64Micro({{ended_at:Int64}}, 'UTC'),
            exception = {{exception:Nullable(String)}},
            output_dump = {{output_dump:String}},
            summary_dump = {{summary_dump:String}},
            output_refs = {{output_refs:Array(String)}},
            wb_run_step_end = {{wb_run_step_end:Nullable(UInt64)}},
            updated_at = now64(3)
        WHERE project_id = {{project_id:String}}
            AND started_at = fromUnixTimestamp64Micro({{started_at:Int64}}, 'UTC')
            AND id = {{id:String}}
    """

    exp_formatted = sqlparse.format(expected, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert exp_formatted == found_formatted, (
        f"\nExpected:\n{exp_formatted}\n\nGot:\n{found_formatted}"
    )
