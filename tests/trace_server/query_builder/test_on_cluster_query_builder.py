"""Tests for ON CLUSTER clause handling in query builders.

These tests verify that when cluster_name is set, the ON CLUSTER clause
is properly added to all table references in the generated SQL, and that
only distributed tables (e.g. calls_complete) get the _local suffix.
"""

import pytest
import sqlparse

from weave.trace_server.calls_query_builder.calls_query_builder import (
    _format_table_name_with_cluster,
    build_calls_complete_delete_query,
    build_calls_complete_update_end_query,
    build_calls_complete_update_query,
)
from weave.trace_server.clickhouse_trace_server_settings import LOCAL_TABLE_SUFFIX
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.annotation_queues_query_builder import (
    make_annotator_progress_update_query,
    make_queue_delete_query,
    make_queue_update_query,
)

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
            exception = {{exception:String}},
            output_dump = {{output_dump:String}},
            summary_dump = {{summary_dump:String}},
            output_refs = {{output_refs:Array(String)}},
            wb_run_step_end = {{wb_run_step_end:UInt64}},
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


@pytest.mark.parametrize(
    ("table_name", "cluster_name", "is_distributed", "expected"),
    [
        # Distributed table with cluster: gets _local suffix + ON CLUSTER
        ("calls_complete", CLUSTER_NAME, True, f"calls_complete_local ON CLUSTER {CLUSTER_NAME}"),
        # Non-distributed table with cluster: gets ON CLUSTER but NO _local suffix
        ("annotation_queues", CLUSTER_NAME, False, f"annotation_queues ON CLUSTER {CLUSTER_NAME}"),
        # No cluster: table name unchanged regardless of is_distributed
        ("calls_complete", None, True, "calls_complete"),
        ("annotation_queues", None, False, "annotation_queues"),
    ],
    ids=[
        "distributed_with_cluster",
        "non_distributed_with_cluster",
        "distributed_no_cluster",
        "non_distributed_no_cluster",
    ],
)
def test_format_table_name_with_cluster(
    table_name: str,
    cluster_name: str | None,
    is_distributed: bool,
    expected: str,
) -> None:
    """Non-distributed tables must never get a _local suffix.

    Regression test: _format_table_name_with_cluster previously appended _local
    to ALL tables when cluster_name was set, but non-distributed tables like
    annotation_queues don't have _local counterparts, causing
    DB::Exception: Table ... does not exist.
    """
    result = _format_table_name_with_cluster(
        table_name, cluster_name, is_distributed=is_distributed
    )
    assert result == expected


def test_annotation_queue_mutations_never_use_local_suffix() -> None:
    """All annotation queue mutation builders must NOT append _local, even with a cluster.

    Regression: #6093 and #6114 reused _format_table_name_with_cluster (designed
    for distributed calls_complete) on non-distributed annotation_queue tables,
    producing queries against non-existent *_local tables.
    """
    pb = ParamBuilder()
    delete_query = make_queue_delete_query(
        project_id="proj",
        queue_id="queue-1",
        pb=pb,
        cluster_name=CLUSTER_NAME,
    )
    assert f"annotation_queues ON CLUSTER {CLUSTER_NAME}" in delete_query
    assert "annotation_queues_local" not in delete_query

    pb = ParamBuilder()
    update_query = make_queue_update_query(
        project_id="proj",
        queue_id="queue-1",
        pb=pb,
        cluster_name=CLUSTER_NAME,
        name="new-name",
    )
    assert f"annotation_queues ON CLUSTER {CLUSTER_NAME}" in update_query
    assert "annotation_queues_local" not in update_query

    pb = ParamBuilder()
    progress_query = make_annotator_progress_update_query(
        project_id="proj",
        queue_item_id="item-1",
        annotator_id="user-1",
        annotation_state="completed",
        pb=pb,
        cluster_name=CLUSTER_NAME,
    )
    assert f"annotator_queue_items_progress ON CLUSTER {CLUSTER_NAME}" in progress_query
    assert "annotator_queue_items_progress_local" not in progress_query


def test_calls_complete_mutations_use_local_suffix_with_cluster() -> None:
    """All calls_complete mutation builders must use _local suffix when cluster is set."""
    query = build_calls_complete_update_end_query(
        table_name="calls_complete",
        project_id_param="project_id",
        started_at_param="started_at",
        id_param="id",
        ended_at_param="ended_at",
        exception_param="exception",
        output_dump_param="output_dump",
        summary_dump_param="summary_dump",
        output_refs_param="output_refs",
        wb_run_step_end_param="wb_run_step_end",
        cluster_name=CLUSTER_NAME,
    )
    assert f"calls_complete_local ON CLUSTER {CLUSTER_NAME}" in query

    delete_query = build_calls_complete_delete_query(
        table_name="calls_complete",
        project_id_param="project_id",
        call_ids_param="call_ids",
        cluster_name=CLUSTER_NAME,
    )
    assert f"calls_complete_local ON CLUSTER {CLUSTER_NAME}" in delete_query

    update_query = build_calls_complete_update_query(
        table_name="calls_complete",
        project_id_param="project_id",
        id_param="id",
        display_name_param="display_name",
        cluster_name=CLUSTER_NAME,
    )
    assert f"calls_complete_local ON CLUSTER {CLUSTER_NAME}" in update_query
