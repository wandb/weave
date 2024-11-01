import pytest

from weave.trace_server.trace_server_interface import (
    FeedbackCreateReq,
    FeedbackQueryReq,
    FeedbackReplaceReq,
)


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


def test_feedback_replace(client) -> None:
    # Create initial feedback
    create_req = FeedbackCreateReq(
        project_id="test/project",
        weave_ref="weave:///test/project/obj/123:abc",
        feedback_type="reaction",
        payload={"emoji": "👍"},
        wb_user_id="test_user",
    )
    initial_feedback = client.server.feedback_create(create_req)

    # Create another feedback with different type
    note_feedback = client.server.feedback_create(
        FeedbackCreateReq(
            project_id="test/project",
            weave_ref="weave:///test/project/obj/456:def",
            feedback_type="note",
            payload={"note": "This is a test note"},
            wb_user_id="test_user",
        )
    )

    # Replace the first feedback with new content
    replace_req = FeedbackReplaceReq(
        project_id="test/project",
        weave_ref="weave:///test/project/obj/123:abc",
        feedback_type="note",
        payload={"note": "Updated feedback"},
        feedback_id=initial_feedback.id,
        wb_user_id="test_user",
    )
    replaced_feedback = client.server.feedback_replace(replace_req)

    # Verify the replacement
    assert replaced_feedback.feedback_type == "note"
    assert replaced_feedback.payload == {"note": "Updated feedback"}

    # Verify the other feedback remains unchanged
    query_res = client.server.feedback_query(
        FeedbackQueryReq(
            project_id="test/project", fields=["id", "feedback_type", "payload"]
        )
    )

    feedbacks = query_res.result
    assert len(feedbacks) == 2

    # Find the non-replaced feedback and verify it's unchanged
    other_feedback = next(f for f in feedbacks if f["id"] == note_feedback.id)
    assert other_feedback["feedback_type"] == "note"
    assert other_feedback["payload"] == {"note": "This is a test note"}

    # now replace the replaced feedback with the original content
    replace_req = FeedbackReplaceReq(
        project_id="test/project",
        weave_ref="weave:///test/project/obj/123:abc",
        feedback_type="reaction",
        payload={"emoji": "👍"},
        feedback_id=replaced_feedback.id,
        wb_user_id="test_user",
    )
    replaced_feedback = client.server.feedback_replace(replace_req)

    assert replaced_feedback.feedback_type == "reaction"
    assert replaced_feedback.payload == {"emoji": "👍"}
