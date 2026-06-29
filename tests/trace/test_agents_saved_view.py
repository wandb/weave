"""Tests for the AgentsSavedView builtin object class.

AgentsSavedView is persisted through the same generic obj_create / obj_read /
objs_query plumbing as every other builtin object class, so these tests focus
on the agents-specific contract: the per-tab discriminated definition
round-trips losslessly, views are listable by their builtin object class, and
the server rejects definitions for tabs we have not modeled yet (e.g. the
future dashboard tab) and malformed fields.
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
    # The discriminated union resolves to the concrete spans variant.
    assert type(view.definition).__name__ == "SpansViewDefinition"
    assert view.definition.tab == "spans"

    ref = weave.publish(view)

    # Allow ClickHouse eventual consistency to settle before reading.
    time.sleep(0.2)
    gotten = weave.ref(ref.uri).get()

    assert isinstance(gotten, base_objects.AgentsSavedView)
    # Full-object equality: the persisted view is byte-for-byte the same model.
    assert gotten.model_dump(by_alias=True) == view.model_dump(by_alias=True)
    assert type(gotten.definition).__name__ == "SpansViewDefinition"


def test_agents_saved_view_lists_by_class_with_each_tab(client: WeaveClient):
    """All three tab variants persist and are listable by their object class."""
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
        definition={
            "tab": "agents",
            "sort_field": "total_cost_usd",
            "hidden_agents": {"hide": ["noisy-agent"], "show": []},
        },
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
    # Nested models are stored with serialization annotations (_class_name,
    # _bases, _type), so pin the meaningful fields rather than the whole dict.
    conv_attr = by_tab["conversations"]["definition"]["conv_custom_attrs"][0]
    assert conv_attr["attr_id"] == "custom_attrs_int:retries"
    assert conv_attr["mode"] == "avg"


def test_agents_saved_view_definition_validation():
    """Backend-agnostic: the discriminated definition enforces its contract.

    Server-side enforcement on obj_create only runs on ClickHouse (the fake
    backend stores vals unvalidated), so the model-level guarantees are pinned
    here independently of the backend under test.
    """
    # Discriminates to the concrete per-tab variant.
    spans = base_objects.AgentsSavedView(label="s", definition={"tab": "spans"})
    assert type(spans.definition).__name__ == "SpansViewDefinition"
    conv = base_objects.AgentsSavedView(label="c", definition={"tab": "conversations"})
    assert type(conv.definition).__name__ == "ConversationsViewDefinition"
    agents = base_objects.AgentsSavedView(label="a", definition={"tab": "agents"})
    assert type(agents.definition).__name__ == "AgentsListViewDefinition"

    # A tab we have not modeled yet (the future dashboard tab) is rejected.
    with pytest.raises(ValidationError):
        base_objects.AgentsSavedView(label="d", definition={"tab": "dashboard"})

    # Invalid sort direction is rejected.
    with pytest.raises(ValidationError):
        base_objects.AgentsSavedView(
            label="bad",
            definition={"tab": "spans", "sort": {"field": "f", "sort": "sideways"}},
        )


def test_agents_saved_view_rejects_unmodeled_tab(client: WeaveClient):
    """The ClickHouse server rejects an unmodeled tab at obj_create time."""
    if not client_is_clickhouse(client):
        pytest.skip("builtin object class validation only runs on ClickHouse")
    with pytest.raises(ValidationError):
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": "dashboard_view",
                        # Bare val (no _class_name/_bases) so the server
                        # validates it against AgentsSavedView, mirroring the
                        # frontend create path.
                        "val": {
                            "label": "dashboard",
                            "definition": {"tab": "dashboard"},
                        },
                        "builtin_object_class": "AgentsSavedView",
                    }
                }
            )
        )


def test_agents_saved_view_rejects_bad_sort_direction(client: WeaveClient):
    if not client_is_clickhouse(client):
        pytest.skip("builtin object class validation only runs on ClickHouse")
    with pytest.raises(ValidationError):
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": "bad_sort_view",
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
