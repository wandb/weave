"""Tests for ON CLUSTER clause handling in query builders.

Regression: _format_table_name_with_cluster used to bake _local into the table
name whenever cluster_name was set. But cluster_name is set in replicated mode
too, where _local tables don't exist. The _local suffix is now the caller's
responsibility (via _get_calls_complete_table_name in the batched server).
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


def test_format_table_name_with_cluster_never_appends_local() -> None:
    """_format_table_name_with_cluster only adds ON CLUSTER, never _local."""
    # With cluster → ON CLUSTER appended, table name unchanged
    assert _format_table_name_with_cluster("t", CLUSTER) == f"t ON CLUSTER {CLUSTER}"
    # Already-local table name preserved as-is
    assert (
        _format_table_name_with_cluster("t_local", CLUSTER)
        == f"t_local ON CLUSTER {CLUSTER}"
    )
    # No cluster → plain table name
    assert _format_table_name_with_cluster("t", None) == "t"


def test_on_cluster_mutations_never_inject_local_suffix() -> None:
    """No mutation builder should inject _local — only the caller controls the table name.

    Exercises all 6 mutation builders. calls_complete builders receive the plain
    table name; in production the batched server passes _get_calls_complete_table_name()
    which resolves to calls_complete_local only in distributed mode.
    """
    # --- calls_complete: plain name in → plain name + ON CLUSTER out ---
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
    assert f"calls_complete ON CLUSTER {CLUSTER}" in update_end
    assert "calls_complete_local" not in update_end

    # When caller passes _local name, it's preserved
    update_end_local = build_calls_complete_update_end_query(
        table_name="calls_complete_local",
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
    assert f"calls_complete_local ON CLUSTER {CLUSTER}" in update_end_local

    delete = build_calls_complete_delete_query(
        table_name="calls_complete",
        project_id_param="p",
        call_ids_param="c",
        cluster_name=CLUSTER,
    )
    assert f"calls_complete ON CLUSTER {CLUSTER}" in delete
    assert "calls_complete_local" not in delete

    update = build_calls_complete_update_query(
        table_name="calls_complete",
        project_id_param="p",
        id_param="i",
        display_name_param="d",
        cluster_name=CLUSTER,
    )
    assert f"calls_complete ON CLUSTER {CLUSTER}" in update
    assert "calls_complete_local" not in update

    # --- annotation queues: same behavior, no _local ---
    pb = ParamBuilder()
    q_delete = make_queue_delete_query(
        project_id="proj", queue_id="q", pb=pb, cluster_name=CLUSTER
    )
    assert f"annotation_queues ON CLUSTER {CLUSTER}" in q_delete
    assert "annotation_queues_local" not in q_delete

    pb = ParamBuilder()
    q_update = make_queue_update_query(
        project_id="proj", queue_id="q", pb=pb, cluster_name=CLUSTER, name="n"
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
