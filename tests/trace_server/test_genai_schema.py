"""Unit tests for GenAI agent schema models."""

import datetime

import pytest
from pydantic import ValidationError

from weave.trace_server.agents.schema import AgentSpanCHInsertable, NormalizedMessage


def test_normalized_message_validation() -> None:
    """NormalizedMessage requires content; role defaults to "" when omitted (but
    cannot stand alone without content); finish_reason defaults to "".
    """
    with pytest.raises(ValidationError):
        NormalizedMessage()
    with pytest.raises(ValidationError):
        NormalizedMessage(role="user")

    assert NormalizedMessage(content="hello").role == ""
    assert NormalizedMessage(role="assistant", content="").finish_reason == ""


def test_agent_span_defaults_and_output_type_literal() -> None:
    """AgentSpanCHInsertable: created_at defaults to a tz-aware UTC value;
    output_type accepts the "json" literal but rejects an unknown value.
    """
    base = {
        "project_id": "p1",
        "trace_id": "t1",
        "span_id": "s1",
        "span_name": "chat",
        "started_at": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    }

    span = AgentSpanCHInsertable(**base)
    assert span.created_at.tzinfo is not None

    AgentSpanCHInsertable(**base, output_type="json")

    with pytest.raises(ValidationError):
        AgentSpanCHInsertable.model_validate({**base, "output_type": "pdf"})
