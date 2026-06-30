"""Tests for the AgentsSavedView builtin object class.

AgentsSavedView is persisted through the same generic obj_create / obj_read /
objs_query plumbing as every other builtin object class, so these tests focus
on the agents-specific contract: a fully-populated definition round-trips
losslessly through the real backend, and views are listable by their builtin
object class and filterable by `definition.view_type`.
"""

import weave
from weave.trace import base_objects
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi

# A fully-populated spans view exercising every table-view field.
SPANS_DEFINITION = {
    "view_type": "spans",
    "time_window": {"unit": "hour", "quantity": 24, "start_ms": 1700000000000},
    "sort": {"field": "duration_ms", "sort": "desc"},
    "filters": {"agent_name": "planner"},
    "numeric_ranges": {"duration_ms": {"min": 100.0, "max": 5000.0}},
    "cols": {"hide": ["span_id"], "show": ["agent_id"]},
    "custom_cols": ["custom_attrs_string:gen_ai.request.model"],
    "view": "split",
    "volume_collapsed": True,
}


def test_agents_saved_view_roundtrip(client: WeaveClient):
    view = base_objects.AgentsSavedView(
        label="Slow planner spans",
        definition=SPANS_DEFINITION,
    )
    ref = weave.publish(view)
    gotten = weave.ref(ref.uri).get()

    assert isinstance(gotten, base_objects.AgentsSavedView)
    # Full-object equality: the persisted view is byte-for-byte the same model.
    assert gotten.model_dump(by_alias=True) == view.model_dump(by_alias=True)


def test_agents_saved_view_lists_by_class_and_view_type(client: WeaveClient):
    """Views persist and are listable by object class, keyed by view_type."""
    spans = base_objects.AgentsSavedView(
        label="spans view", definition={"view_type": "spans"}
    )
    conversations = base_objects.AgentsSavedView(
        label="conversations view",
        definition={
            "view_type": "conversations",
            "conv_custom_attrs": [
                {"attr_id": "custom_attrs_int:retries", "mode": "avg"}
            ],
        },
    )
    agents = base_objects.AgentsSavedView(
        label="agents view",
        definition={"view_type": "agents", "sort_field": "total_cost_usd"},
    )

    for view in (spans, conversations, agents):
        weave.publish(view)

    res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["AgentsSavedView"]},
            }
        )
    )

    by_view_type = {obj.val["definition"]["view_type"]: obj.val for obj in res.objs}
    assert sorted(by_view_type) == ["agents", "conversations", "spans"]
    assert by_view_type["agents"]["label"] == "agents view"
    assert by_view_type["agents"]["definition"]["sort_field"] == "total_cost_usd"
    conv_attr = by_view_type["conversations"]["definition"]["conv_custom_attrs"][0]
    assert conv_attr["attr_id"] == "custom_attrs_int:retries"
    assert conv_attr["mode"] == "avg"
