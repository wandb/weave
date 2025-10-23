import pytest

import weave
from weave.trace.context import call_context
from weave.trace.serialization.serialize import to_json
from weave.trace.weave_client import RESERVED_SUMMARY_STATUS_COUNTS_KEY
from weave.trace_server import trace_server_interface as tsi


def test_call_attributes_read_only(client):
    @weave.op
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
    @weave.op
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
    @weave.op
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
    @weave.op
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


def test_set_view_inside_op(client):
    """Verify weave.set_view stores serialized content on op call summary."""
    markdown_view = weave.Content.from_text("# Report", mimetype="text/markdown")
    html_view = weave.Content.from_text("<p>Hi</p>", mimetype="text/html")

    @weave.op
    def my_op_with_views() -> str:
        """Op that attaches two views to its call summary.

        Returns:
            str: Constant string to keep output simple.

        Examples:
            >>> my_op_with_views()
            'ok'
        """
        weave.set_view("markdown", markdown_view)
        weave.set_view("html", html_view)
        return "ok"

    result = my_op_with_views()
    assert result == "ok"

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.summary["weave"] is not None
    assert "views" in call.summary["weave"]
    views = call.summary["weave"]["views"]
    assert len(views) == 2
    assert views["markdown"] == to_json(
        markdown_view,
        client._project_id(),
        client,
    )
    assert views["html"] == to_json(
        html_view,
        client._project_id(),
        client,
    )


def test_set_view_string_content(client):
    """Verify weave.set_view accepts raw string content."""

    @weave.op
    def op_with_string_view() -> None:
        """Attach a markdown view using plain string input."""
        weave.set_view("md", "# Report", extension="md")

    op_with_string_view()

    call = client.get_calls()[0]
    assert call.summary["weave"] is not None
    views = call.summary["weave"]["views"]
    stored = dict(views["md"])

    assert stored["_type"] == "CustomWeaveType"
    assert stored["weave_type"]["type"] == "weave.type_wrappers.Content.content.Content"
    assert stored["files"]["content"]
