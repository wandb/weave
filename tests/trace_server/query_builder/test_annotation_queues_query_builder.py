import sqlparse

from weave.trace_server.clickhouse_query_layer.query_builders.annotation_queues import (
    make_queue_items_query,
    make_queues_query,
)
from weave.trace_server.common_interface import AnnotationQueueItemsFilter, SortBy
from weave.trace_server.orm import ParamBuilder


def assert_sql(
    expected_query: str, expected_params: dict, query: str, params: dict
) -> None:
    expected_formatted = sqlparse.format(expected_query, reindent=True)
    found_formatted = sqlparse.format(query, reindent=True)

    assert expected_formatted == found_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"\nExpected params: {expected_params}\n\nGot params: {params}"
    )


def test_make_queues_query_with_name_and_pagination() -> None:
    pb = ParamBuilder("pb")
    query = make_queues_query(
        project_id="project",
        pb=pb,
        name="queue",
        sort_by=[SortBy(field="name", direction="asc")],
        limit=10,
        offset=5,
    )
    params = pb.get_params()

    expected_query = """
    SELECT
        id,
        project_id,
        name,
        description,
        scorer_refs,
        created_at,
        created_by,
        updated_at,
        deleted_at
    FROM annotation_queues
    WHERE project_id = {pb_0: String}
        AND deleted_at IS NULL
        AND lowerUTF8(name) LIKE lowerUTF8({pb_1: String})
    ORDER BY name ASC, id ASC
    LIMIT {pb_2: Int64} OFFSET {pb_3: Int64}
    """

    expected_params = {
        "pb_0": "project",
        "pb_1": "%queue%",
        "pb_2": 10,
        "pb_3": 5,
    }

    assert_sql(expected_query, expected_params, query, params)


def test_make_queue_items_query_with_filter_and_annotation_states() -> None:
    pb = ParamBuilder("pb")
    query = make_queue_items_query(
        project_id="project",
        queue_id="queue-id",
        pb=pb,
        filter=AnnotationQueueItemsFilter(
            call_id="call-id",
            annotation_states=["completed"],
        ),
        sort_by=[SortBy(field="call_started_at", direction="desc")],
    )
    params = pb.get_params()

    expected_query = """
    SELECT * FROM (
        SELECT
            qi.id,
            any(qi.project_id) as project_id,
            any(qi.queue_id) as queue_id,
            any(qi.call_id) as call_id,
            any(qi.call_started_at) as call_started_at,
            any(qi.call_ended_at) as call_ended_at,
            any(qi.call_op_name) as call_op_name,
            any(qi.call_trace_id) as call_trace_id,
            any(qi.display_fields) as display_fields,
            any(qi.added_by) as added_by,
            any(qi.created_at) as created_at,
            any(qi.created_by) as created_by,
            any(qi.updated_at) as updated_at,
            any(qi.deleted_at) as deleted_at,
            toString(argMax(p.annotation_state, p.updated_at)) as annotation_state,
            argMax(p.annotator_id, p.updated_at) as annotator_user_id
        FROM annotation_queue_items qi
        LEFT JOIN annotator_queue_items_progress p
            ON p.queue_item_id = qi.id
            AND p.project_id = qi.project_id
            AND p.deleted_at IS NULL
        WHERE qi.project_id = {pb_0: String}
            AND qi.queue_id = {pb_1: String}
            AND qi.deleted_at IS NULL
            AND qi.call_id = {pb_2:String}
        GROUP BY qi.id
    )
    WHERE annotation_state IN {pb_3:Array(String)}
    ORDER BY call_started_at DESC, id ASC
    """

    expected_params = {
        "pb_0": "project",
        "pb_1": "queue-id",
        "pb_2": "call-id",
        "pb_3": ["completed"],
    }

    assert_sql(expected_query, expected_params, query, params)
