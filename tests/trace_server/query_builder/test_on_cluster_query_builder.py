"""Tests for ON CLUSTER clause handling in query builders.

Verifies that only distributed tables get the _local suffix in ON CLUSTER
mutations, and that non-distributed tables (annotation_queues) do not.

Regression: #6093 and #6114 reused _format_table_name_with_cluster (designed
for distributed calls_complete) on non-distributed annotation_queue tables,
producing queries against non-existent *_local tables.
"""

from weave.trace_server.calls_query_builder.calls_query_builder import (
    _format_table_name_with_cluster,
    build_calls_complete_delete_query,
    build_calls_complete_update_end_query,
    build_calls_complete_update_query,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.annotation_queues_query_builder import (
    make_annotator_progress_update_query,
    make_queue_delete_query,
    make_queue_update_query,
)

CLUSTER = "weave_cluster"


def test_local_suffix_only_for_distributed_tables() -> None:
    """_format_table_name_with_cluster must only append _local when is_distributed=True."""
    # Distributed + cluster → _local ON CLUSTER
    assert (
        _format_table_name_with_cluster("t", CLUSTER, is_distributed=True)
        == f"t_local ON CLUSTER {CLUSTER}"
    )
    # Non-distributed + cluster → ON CLUSTER without _local
    assert (
        _format_table_name_with_cluster("t", CLUSTER, is_distributed=False)
        == f"t ON CLUSTER {CLUSTER}"
    )
    # No cluster → plain table name regardless
    assert _format_table_name_with_cluster("t", None, is_distributed=True) == "t"
    assert _format_table_name_with_cluster("t", None, is_distributed=False) == "t"


def test_on_cluster_mutations_distributed_vs_non_distributed() -> None:
    """Distributed tables (calls_complete) get _local suffix; non-distributed tables don't.

    Exercises all 6 mutation builders that use _format_table_name_with_cluster.
    """
    # --- calls_complete: all three builders must produce _local ---
    update_end = build_calls_complete_update_end_query(
        table_name="calls_complete",
        project_id_param="p",
        started_at_param="s",
        id_param="i",
        ended_at_param="e",
        exception_param="x",
        output_dump_param="o",
        summary_dump_param="sm",
        output_refs_param="or",
        wb_run_step_end_param="w",
        cluster_name=CLUSTER,
    )
    assert f"calls_complete_local ON CLUSTER {CLUSTER}" in update_end

    delete = build_calls_complete_delete_query(
        table_name="calls_complete",
        project_id_param="p",
        call_ids_param="c",
        cluster_name=CLUSTER,
    )
    assert f"calls_complete_local ON CLUSTER {CLUSTER}" in delete

    update = build_calls_complete_update_query(
        table_name="calls_complete",
        project_id_param="p",
        id_param="i",
        display_name_param="d",
        cluster_name=CLUSTER,
    )
    assert f"calls_complete_local ON CLUSTER {CLUSTER}" in update

    # --- annotation queues: must NOT produce _local ---
    pb = ParamBuilder()
    q_delete = make_queue_delete_query(
        project_id="proj", queue_id="q", pb=pb, cluster_name=CLUSTER
    )
    assert f"annotation_queues ON CLUSTER {CLUSTER}" in q_delete
    assert "annotation_queues_local" not in q_delete

    pb = ParamBuilder()
    q_update = make_queue_update_query(
        project_id="proj",
        queue_id="q",
        pb=pb,
        cluster_name=CLUSTER,
        name="n",
    )
    assert f"annotation_queues ON CLUSTER {CLUSTER}" in q_update
    assert "annotation_queues_local" not in q_update

    pb = ParamBuilder()
    progress = make_annotator_progress_update_query(
        project_id="proj",
        queue_item_id="qi",
        annotator_id="a",
        annotation_state="done",
        pb=pb,
        cluster_name=CLUSTER,
    )
    assert f"annotator_queue_items_progress ON CLUSTER {CLUSTER}" in progress
    assert "annotator_queue_items_progress_local" not in progress
