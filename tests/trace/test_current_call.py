import pytest

import weave
from weave.trace.context import call_context
from weave.trace.weave_client import RESERVED_SUMMARY_STATUS_COUNTS_KEY
from weave.trace_server import trace_server_interface as tsi


def test_call_attributes_read_only(client):
    @weave.op()
    def my_op():
        call = call_context.get_current_call()
        with pytest.raises(TypeError):
            call.attributes["new"] = "value"
        return 1

    my_op()
    calls = list(client.get_calls())
    assert len(calls) == 1
    assert "new" not in calls[0].attributes


def test_call_summary_editable(client):
    @weave.op()
    def my_op():
        call = call_context.get_current_call()
        call.summary["foo"] = 1
        call.summary["bar"] = 2
        return "done"

    my_op()
    calls = list(client.get_calls())
    assert len(calls) == 1
    summary = calls[0].summary
    assert summary["foo"] == 1
    assert summary["bar"] == 2
    assert summary[RESERVED_SUMMARY_STATUS_COUNTS_KEY][tsi.TraceStatus.SUCCESS] == 1


def test_call_attributes_update_and_delete_forbidden(client):
    @weave.op()
    def my_op():
        call = call_context.get_current_call()
        with pytest.raises(TypeError):
            call.attributes.update({"extra": 1})
        with pytest.raises(TypeError):
            del call.attributes["weave"]
        return 1

    with weave.attributes({"env": "prod"}):
        my_op()
    calls = list(client.get_calls())
    assert len(calls) == 1
    # Original attribute is preserved
    assert calls[0].attributes["env"] == "prod"
    assert "extra" not in calls[0].attributes


def test_call_summary_deep_merge(client):
    @weave.op()
    def my_op():
        call = call_context.get_current_call()
        call.summary["nested"] = {"foo": 1}
        return "done"

    my_op()
    calls = list(client.get_calls())
    assert len(calls) == 1
    summary = calls[0].summary
    assert summary["nested"]["foo"] == 1
    assert summary[RESERVED_SUMMARY_STATUS_COUNTS_KEY][tsi.TraceStatus.SUCCESS] == 1
