import weave.trace_server.trace_server_interface as tsi


def test_client_feedback(client) -> None:

    # Patch feedback_create to set wb_user_id
    original_feedback_create = client.server.feedback_create

    def patched_create(req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        req.wb_user_id = "test-user-id"
        return original_feedback_create(req)

    client.server.feedback_create = patched_create

    feedbacks = client.feedback()
    assert len(feedbacks) == 0

    # Make three feedbacks on two calls
    call1 = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call1, "hello1")
    trace_object1 = client.call(call1.id)
    feedback_id_emoji = trace_object1.feedback.add_reaction("👍")
    trace_object1.feedback.add_note("this is a note on call1")

    call2 = client.create_call("x", {"a": 6, "b": 11})
    client.finish_call(call2, "hello2")
    trace_object2 = client.call(call2.id)
    feedback_id_note2 = trace_object2.feedback.add_note("this is a note on call2")

    # Check expectations
    feedbacks = client.feedback()
    assert len(feedbacks) == 3

    f = client.feedback(feedback_id_note2)[0]
    assert f.payload == {"note": "this is a note on call2"}

    f = client.feedback(reaction="👍")[0]
    assert f.id == feedback_id_emoji

    assert len(client.feedback(limit=1)) == 1

    # Purge a feedback
    assert len(trace_object2.feedback) == 1
    trace_object2.feedback.purge(feedback_id_note2)
    assert len(trace_object2.feedback) == 0
    feedbacks = client.feedback()
    assert len(feedbacks) == 2
