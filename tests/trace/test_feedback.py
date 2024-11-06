import datetime

import pytest

import weave
from tests.trace.util import client_is_sqlite
from weave.trace.weave_client import WeaveClient, get_ref
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest


def test_client_feedback(client) -> None:
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 0

    # Make three feedbacks on two calls
    call1 = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call1, "hello1")
    trace_object1 = client.get_call(call1.id)
    feedback_id_emoji = trace_object1.feedback.add_reaction("👍")
    trace_object1.feedback.add_note("this is a note on call1")

    call2 = client.create_call("x", {"a": 6, "b": 11})
    client.finish_call(call2, "hello2")
    trace_object2 = client.get_call(call2.id)
    feedback_id_note2 = trace_object2.feedback.add_note("this is a note on call2")

    # Check expectations
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 3

    f = client.get_feedback(feedback_id_note2)[0]
    assert f.payload == {"note": "this is a note on call2"}

    f = client.get_feedback(reaction="👍")[0]
    assert f.id == feedback_id_emoji

    assert len(client.get_feedback(limit=1)) == 1

    # Purge a feedback
    assert len(trace_object2.feedback) == 1
    trace_object2.feedback.purge(feedback_id_note2)
    assert len(trace_object2.feedback) == 0
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 2


def test_custom_feedback(client) -> None:
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 0

    # Add custom feedback to call
    call = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call, "hello1")
    trace_object = client.get_call(call.id)
    feedback_id1 = trace_object.feedback.add("correctness", {"value": 4})
    feedback_id2 = trace_object.feedback.add("hallucination", value=0.5)

    # Check expectations
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 2

    f = client.get_feedback(feedback_id1)[0]
    assert f.feedback_type == "correctness"
    assert f.payload["value"] == 4

    f = client.get_feedback(feedback_id2)[0]
    assert f.feedback_type == "hallucination"
    assert f.payload["value"] == 0.5

    with pytest.raises(ValueError):
        trace_object.feedback.add("wandb.trying_to_use_reserved_prefix", value=1)


def test_annotation_feedback(client: WeaveClient) -> None:
    project_id = client._project_id()
    column_name = "column_name"
    feedback_type = f"wandb.annotation.{column_name}"
    weave_ref = f"weave:///{project_id}/call/cal_id_123"
    annotation_ref = f"weave:///{project_id}/object/{column_name}:obj_id_123"
    payload = {"value": 1}

    # Case 1: Errors with no name in type (dangle or char len 0)
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.annotation",  # No name
                payload=payload,
                annotation_ref=annotation_ref,
            )
        )

    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.annotation.",  # Trailing period
                payload=payload,
                annotation_ref=annotation_ref,
            )
        )
    # Case 2: Errors with incorrect ref string format
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                annotation_ref=f"weave:///{project_id}/object/{column_name}",  # No digest
            )
        )
    # Case 3: Errors with name mismatch
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type + "_wrong_name",
                payload=payload,
                annotation_ref=annotation_ref,
            )
        )
    # Case 4: Errors if annotation ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.annotation",
                payload=payload,
                annotation_ref=f"weave:///{project_id}/op/{column_name}:obj_id_123",
            )
        )

    # Case 5: Invalid payload
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload={"not": "a valid payload"},
                annotation_ref=annotation_ref,
            )
        )

    # Success
    create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            annotation_ref=annotation_ref,
        )
    )
    assert create_res.id != None
    # Correct Query Result Payload
    query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
        )
    )
    assert len(query_res.result) == 1
    assert query_res.result[0] == {
        "id": create_res.id,
        "project_id": project_id,
        "weave_ref": weave_ref,
        "wb_user_id": "shawn",
        "creator": None,
        # Sad - seems like sqlite and clickhouse remote different types here
        "created_at": create_res.created_at.isoformat().replace("T", " ")
        if client_is_sqlite(client)
        else MatchAnyDatetime(),
        "feedback_type": feedback_type,
        "payload": payload,
        "annotation_ref": annotation_ref,
        "runnable_ref": None,
        "call_ref": None,
        "trigger_ref": None,
    }


def test_runnable_feedback(client: WeaveClient) -> None:
    """Test feedback creation with runnable references."""
    project_id = client._project_id()
    runnable_name = "runnable_name"
    feedback_type = f"wandb.runnable.{runnable_name}"
    weave_ref = f"weave:///{project_id}/call/cal_id_123"
    runnable_ref = f"weave:///{project_id}/op/{runnable_name}:op_id_123"
    call_ref = f"weave:///{project_id}/call/call_id_123"
    trigger_ref = f"weave:///{project_id}/object/{runnable_name}:trigger_id_123"
    payload = {"output": 1}

    # Case 1: Errors with no name in type (dangle or char len 0)
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.runnable",  # No name
                payload=payload,
                runnable_ref=runnable_ref,
            )
        )

    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.runnable.",  # Trailing period
                payload=payload,
                runnable_ref=runnable_ref,
            )
        )

    # Case 2: Errors with incorrect ref string format
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                runnable_ref=f"weave:///{project_id}/op/{runnable_name}",  # No digest
            )
        )

    # Case 3: Errors with name mismatch
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type + "_wrong_name",
                payload=payload,
                runnable_ref=runnable_ref,
            )
        )

    # Case 4: Errors if runnable ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.runnable",  # Wrong type
                payload=payload,
                runnable_ref=runnable_ref,  # Wrong type
            )
        )

    # Case 5: Errors if call ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.runnable",  # Wrong type
                payload=payload,
                call_ref=call_ref,
            )
        )

    # Case 6: Errors if trigger ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.runnable",
                payload=payload,
                trigger_ref=trigger_ref,
            )
        )

    # Case 7: Invalid payload
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload={"not": "a valid payload"},
                runnable_ref=runnable_ref,
                call_ref=call_ref,
                trigger_ref=trigger_ref,
            )
        )

    # Success
    create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            runnable_ref=runnable_ref,
            call_ref=call_ref,
            trigger_ref=trigger_ref,
        )
    )
    assert create_res.id is not None

    # Verify Query Result Payload
    query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
        )
    )
    assert len(query_res.result) == 1
    assert query_res.result[0] == {
        "id": create_res.id,
        "project_id": project_id,
        "weave_ref": weave_ref,
        "wb_user_id": "shawn",
        "creator": None,
        # Sad - seems like sqlite and clickhouse remote different types here
        "created_at": create_res.created_at.isoformat().replace("T", " ")
        if client_is_sqlite(client)
        else MatchAnyDatetime(),
        "feedback_type": feedback_type,
        "payload": payload,
        "annotation_ref": None,
        "runnable_ref": runnable_ref,
        "call_ref": call_ref,
        "trigger_ref": trigger_ref,
    }


def populate_feedback(client: WeaveClient) -> None:
    @weave.op
    def my_scorer(x: int, output: int) -> int:
        expected = ["a", "b", "c", "d"][x]
        return {
            "model_output": output,
            "expected": expected,
            "match": output == expected,
        }

    @weave.op
    def my_model(x: int) -> str:
        return [
            "a",
            "x",  # intentional "mistake"
            "c",
            "y",  # intentional "mistake"
        ][x]

    ids = []
    for x in range(4):
        _, c = my_model.call(x)
        ids.append(c.id)
        c._apply_scorer(my_scorer)

    assert len(list(my_scorer.calls())) == 4
    assert len(list(my_model.calls())) == 4

    return ids, my_scorer, my_model


def test_sort_by_feedback(client: WeaveClient) -> None:
    if client_is_sqlite(client):
        # Not implemented in sqlite - skip
        return pytest.skip()

    """Test sorting by feedback."""
    ids, my_scorer, my_model = populate_feedback(client)

    for fields, asc_ids in [
        (
            ["feedback.[wandb.runnable.my_scorer].payload.output.model_output"],
            [ids[0], ids[2], ids[1], ids[3]],
        ),
        (
            ["feedback.[wandb.runnable.my_scorer].payload.output.expected"],
            [ids[0], ids[1], ids[2], ids[3]],
        ),
        (
            [
                "feedback.[wandb.runnable.my_scorer].payload.output.match",
                "feedback.[wandb.runnable.my_scorer].payload.output.model_output",
            ],
            [ids[1], ids[3], ids[0], ids[2]],
        ),
    ]:
        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client._project_id(),
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri()]),
                sort_by=[
                    tsi.SortBy(
                        field=field,
                        direction="asc",
                    )
                    for field in fields
                ],
            )
        )

        found_ids = [c.id for c in calls]
        assert (
            found_ids == asc_ids
        ), f"Sorting by {fields} ascending failed, expected {asc_ids}, got {found_ids}"

        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client._project_id(),
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri()]),
                sort_by=[
                    tsi.SortBy(
                        field=field,
                        direction="desc",
                    )
                    for field in fields
                ],
            )
        )

        found_ids = [c.id for c in calls]
        assert (
            found_ids == asc_ids[::-1]
        ), f"Sorting by {fields} descending failed, expected {asc_ids[::-1]}, got {found_ids}"


def test_filter_by_feedback(client: WeaveClient) -> None:
    if client_is_sqlite(client):
        # Not implemented in sqlite - skip
        return pytest.skip()

    """Test filtering by feedback."""
    ids, my_scorer, my_model = populate_feedback(client)
    for field, value, eq_ids, gt_ids in [
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.model_output",
            "a",
            [ids[0]],
            [ids[1], ids[2], ids[3]],
        ),
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.expected",
            "c",
            [ids[2]],
            [ids[3]],
        ),
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.match",
            "false",
            [ids[1], ids[3]],
            [ids[0], ids[2]],
        ),
    ]:
        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client._project_id(),
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri()]),
                query={
                    "$expr": {
                        "$eq": [
                            {"$getField": field},
                            {"$literal": value},
                        ]
                    }
                },
            )
        )

        found_ids = [c.id for c in calls]
        assert (
            found_ids == eq_ids
        ), f"Filtering by {field} == {value} failed, expected {eq_ids}, got {found_ids}"

        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client._project_id(),
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri()]),
                query={
                    "$expr": {
                        "$gt": [
                            {"$getField": field},
                            {"$literal": value},
                        ]
                    }
                },
            )
        )

        found_ids = [c.id for c in calls]
        assert (
            found_ids == gt_ids
        ), f"Filtering by {field} > {value} failed, expected {gt_ids}, got {found_ids}"


class MatchAnyDatetime:
    def __eq__(self, other):
        return isinstance(other, datetime.datetime)


def test_filter_and_sort_by_feedback(client: WeaveClient) -> None:
    if client_is_sqlite(client):
        # Not implemented in sqlite - skip
        return pytest.skip()

    """Test filtering by feedback."""
    ids, my_scorer, my_model = populate_feedback(client)
    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri()]),
            # Filter down to just correct matches
            query={
                "$expr": {
                    "$eq": [
                        {
                            "$getField": "feedback.[wandb.runnable.my_scorer].payload.output.match"
                        },
                        {"$literal": "true"},
                    ]
                }
            },
            # Sort by the model output desc
            sort_by=[
                {
                    "field": "feedback.[wandb.runnable.my_scorer].payload.output.model_output",
                    "direction": "desc",
                }
            ],
        )
    )
    calls = list(calls)
    assert len(calls) == 2
    assert [c.id for c in calls] == [ids[2], ids[0]]
