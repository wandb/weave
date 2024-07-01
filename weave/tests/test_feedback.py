import pytest

import weave.trace_server.trace_server_interface as tsi


def test_client_feedback(client) -> None:
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


def test_custom_feedback(client) -> None:
    feedbacks = client.feedback()
    assert len(feedbacks) == 0

    # Add custom feedback to call
    call = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call, "hello1")
    trace_object = client.call(call.id)
    feedback_id1 = trace_object.feedback.add("correctness", {"value": 4})
    feedback_id2 = trace_object.feedback.add("hallucination", value=0.5)

    # Check expectations
    feedbacks = client.feedback()
    assert len(feedbacks) == 2

    f = client.feedback(feedback_id1)[0]
    assert f.feedback_type == "correctness"
    assert f.payload["value"] == 4

    f = client.feedback(feedback_id2)[0]
    assert f.feedback_type == "hallucination"
    assert f.payload["value"] == 0.5

    with pytest.raises(ValueError):
        trace_object.feedback.add("wandb.trying_to_use_reserved_prefix", value=1)
