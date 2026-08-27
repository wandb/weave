"""Serialization JSON Schema for the agent chat feedback projection."""

from weave.trace_server.agents.types import AgentChatFeedback
from weave.trace_server.trace_server_common import FEEDBACK_QUERY_FIELDS


def test_agent_chat_feedback_fields_match_query_projection() -> None:
    assert set(AgentChatFeedback.model_fields) == set(FEEDBACK_QUERY_FIELDS)


def test_agent_chat_feedback_serialization_requires_every_property() -> None:
    schema = AgentChatFeedback.model_json_schema(mode="serialization")
    props = set(schema.get("properties") or {})
    required = set(schema.get("required") or [])
    assert required == props


def test_agent_chat_feedback_validation_does_not_require_scorer_columns() -> None:
    schema = AgentChatFeedback.model_json_schema(mode="validation")
    required = set(schema.get("required") or [])
    assert "scorer_tags" not in required
    assert required == {"id", "feedback_type", "weave_ref", "payload"}


def test_agent_chat_feedback_constructor_and_dump_keep_defaults() -> None:
    row = AgentChatFeedback(
        id="f1",
        feedback_type="reaction",
        weave_ref="weave:///entity/project/call/c1",
        payload={"emoji": "👍"},
    )
    dumped = row.model_dump()
    assert dumped["creator"] is None
    assert dumped["created_at"] is None
    assert dumped["wb_user_id"] is None
    assert dumped["scorer_tags"] == []
    assert dumped["scorer_tag_reasons"] == {}
    assert dumped["scorer_ratings"] == {}
