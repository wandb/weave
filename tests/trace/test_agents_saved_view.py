"""Tests for the AgentsSavedView builtin object class.

AgentsSavedView is persisted through the same generic obj_create / obj_read /
objs_query plumbing as every other builtin object class, so these tests focus
on the agents-specific contract: the flat per-tab definition round-trips
losslessly, views are listable by their builtin object class and filterable by
`definition.tab`, `tab` is free-form (the set of tabs is owned by the
frontend), and field shapes (e.g. sort direction) are still validated.
"""

import time

import pytest
from pydantic import ValidationError

import weave
from tests.trace.util import client_is_clickhouse
from weave.trace import base_objects
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi

# A fully-populated spans-tab view exercising every table-tab field.
SPANS_DEFINITION = {
    "tab": "spans",
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
    assert view.definition.tab == "spans"

    ref = weave.publish(view)

    # Allow ClickHouse eventual consistency to settle before reading.
    time.sleep(0.2)
    gotten = weave.ref(ref.uri).get()

    assert isinstance(gotten, base_objects.AgentsSavedView)
    # Full-object equality: the persisted view is byte-for-byte the same model.
    assert gotten.model_dump(by_alias=True) == view.model_dump(by_alias=True)


def test_agents_saved_view_lists_by_class_and_tab(client: WeaveClient):
    """Views persist and are listable by object class, filterable by tab."""
    spans = base_objects.AgentsSavedView(label="spans view", definition={"tab": "spans"})
    conversations = base_objects.AgentsSavedView(
        label="conversations view",
        definition={
            "tab": "conversations",
            "conv_custom_attrs": [
                {"attr_id": "custom_attrs_int:retries", "mode": "avg"}
            ],
        },
    )
    agents = base_objects.AgentsSavedView(
        label="agents view",
        definition={"tab": "agents", "sort_field": "total_cost_usd"},
    )

    for view in (spans, conversations, agents):
        weave.publish(view)

    time.sleep(0.2)
    res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["AgentsSavedView"]},
            }
        )
    )

    by_tab = {obj.val["definition"]["tab"]: obj.val for obj in res.objs}
    assert sorted(by_tab) == ["agents", "conversations", "spans"]
    assert by_tab["agents"]["label"] == "agents view"
    assert by_tab["agents"]["definition"]["sort_field"] == "total_cost_usd"
    conv_attr = by_tab["conversations"]["definition"]["conv_custom_attrs"][0]
    assert conv_attr["attr_id"] == "custom_attrs_int:retries"
    assert conv_attr["mode"] == "avg"


def test_agents_saved_view_tab_is_free_form():
    """`tab` accepts any string — the tab set lives in the frontend, so the
    backend must not reject tabs it hasn't heard of (e.g. a future dashboard).
    """
    view = base_objects.AgentsSavedView(
        label="future tab", definition={"tab": "dashboard"}
    )
    assert view.definition.tab == "dashboard"


def test_agents_saved_view_validates_field_shapes():
    """Field shapes are still validated even though `tab` is free-form."""
    with pytest.raises(ValidationError):
        base_objects.AgentsSavedView(
            label="bad",
            definition={"tab": "spans", "sort": {"field": "f", "sort": "sideways"}},
        )


def test_agents_saved_view_server_rejects_bad_field_shape(client: WeaveClient):
    """The ClickHouse server rejects a malformed field at obj_create time."""
    if not client_is_clickhouse(client):
        pytest.skip("builtin object class validation only runs on ClickHouse")
    with pytest.raises(ValidationError):
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": "bad_sort_view",
                        # Bare val (no _class_name/_bases) so the server
                        # validates it against AgentsSavedView, mirroring the
                        # frontend create path.
                        "val": {
                            "label": "bad sort",
                            "definition": {
                                "tab": "spans",
                                "sort": {"field": "duration_ms", "sort": "sideways"},
                            },
                        },
                        "builtin_object_class": "AgentsSavedView",
                    }
                }
            )
        )
