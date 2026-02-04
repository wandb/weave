"""Tests for CallsQuery with distributed mode (ON CLUSTER clause).

These tests verify that when cluster_name is set, the ON CLUSTER clause
is properly added to all table references in the generated SQL.
"""

import pytest
import sqlparse

from weave.trace_server.clickhouse_query_layer.query_builders.calls.calls_query_builder import (
    build_calls_complete_update_end_query,
)
from weave.trace_server.clickhouse_query_layer.settings import LOCAL_TABLE_SUFFIX

CLUSTER_NAME = "weave_cluster"


@pytest.mark.parametrize(
    ("table_name", "cluster_name", "expected_table_clause"),
    [
        # In distributed mode: use _local table with ON CLUSTER
        (
            "calls_complete",
            CLUSTER_NAME,
            f"calls_complete{LOCAL_TABLE_SUFFIX} ON CLUSTER {CLUSTER_NAME}",
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
