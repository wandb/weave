"""Unit tests for ScoreAgentSpansEvent."""

from __future__ import annotations

import datetime

from weave.trace_server.agents.kafka_events import (
    EmbedAgentSpansEvent,
    ScoreAgentSpansEvent,
)
from weave.trace_server.agents.schema import AgentSpanCHInsertable

_STARTED_AT = datetime.datetime(2024, 1, 1, 11, 0, 0)
_ENDED_AT = datetime.datetime(2024, 1, 1, 12, 0, 0)


def test_from_row() -> None:
    """A finished root span yields a turn_ended event; a child span yields None."""
    root_row = AgentSpanCHInsertable(
        project_id="p",
        trace_id="tr",
        span_id="root",
        parent_span_id="",
        span_name="root",
        status_code="OK",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
        conversation_id="c",
        operation_name="invoke_agent",
        wb_user_id="u",
        agent_name="coding-agent",
    )
    event = ScoreAgentSpansEvent.from_row(root_row, "acme")
    assert event == ScoreAgentSpansEvent(
        event_type="weave.genai.turn_ended",
        status_code="OK",
        project_id="p",
        entity_name="acme",
        trace_id="tr",
        span_id="root",
        parent_span_id=None,
        conversation_id="c",
        operation_name="invoke_agent",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
        wb_user_id="u",
        agent_name="coding-agent",
    )
    assert EmbedAgentSpansEvent.from_row(root_row, "acme") == EmbedAgentSpansEvent(
        event_type="weave.genai.turn_ended",
        status_code="OK",
        project_id="p",
        entity_name="acme",
        trace_id="tr",
        span_id="root",
        parent_span_id=None,
        conversation_id="c",
        operation_name="invoke_agent",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
        wb_user_id="u",
        agent_name="coding-agent",
    )
    # The row itself carries no entity, so an unstamped event has none: consumers
    # that route by entity have to treat that as unroutable, not as allowed.
    assert EmbedAgentSpansEvent.from_row(root_row).entity_name is None

    # An unattributed span reports no identity rather than an empty string, and a
    # payload written before the turn facts existed still parses, so a consumer
    # reading a queue across this change sees None and not a validation error.
    anonymous = EmbedAgentSpansEvent.from_row(
        root_row.model_copy(update={"wb_user_id": "", "agent_name": ""})
    )
    assert (anonymous.wb_user_id, anonymous.agent_name) == (None, None)
    legacy = EmbedAgentSpansEvent.model_validate_json(
        event.model_dump_json(
            exclude={"started_at", "ended_at", "wb_user_id", "agent_name"}
        )
    )
    assert (legacy.started_at, legacy.ended_at, legacy.wb_user_id) == (None, None, None)

    child_row = AgentSpanCHInsertable(
        project_id="p",
        trace_id="tr",
        span_id="child",
        parent_span_id="root",
        span_name="child",
        started_at=_STARTED_AT,
        ended_at=_ENDED_AT,
    )
    assert ScoreAgentSpansEvent.from_row(child_row) is None
    assert EmbedAgentSpansEvent.from_row(child_row) is None
