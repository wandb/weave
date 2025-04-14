from weave.trace import log


def test_log_call_empty(client):
    log.log()
    calls = client.get_calls()
    assert len(calls) == 1


def test_log_call_with_parent(client):
    p = log.log(name="parent")
    c = p.log(name="child")
    calls = client.get_calls()
    assert len(calls) == 2
    assert (
        calls[0].op_name
        == "weave:///shawn/test-project/op/parent:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw"
    )
    assert (
        calls[1].op_name
        == "weave:///shawn/test-project/op/child:tzUhDyzVm5bqQsuqh5RT4axEXSosyLIYZn9zbRyenaw"
    )
    assert calls[1].parent_id == calls[0].id


def test_log_call_with_feedback(client):
    p = log.log(name="parent")
    p.add_feedback(payload={"foo": "bar"})
    calls = client.get_calls(include_feedback=True)
    assert len(calls) == 1
    feedback = [f.payload for f in calls[0].feedback]
    assert len(feedback) == 1
    assert feedback[0] == {"foo": "bar"}
