"""Unit tests for GenAI agent schema models."""

import datetime

import pytest
from pydantic import ValidationError

from weave.trace_server.agents.schema import AgentSpanCHInsertable, NormalizedMessage


def test_normalized_message_requires_content_and_defaults_missing_role() -> None:
    with pytest.raises(ValidationError):
        NormalizedMessage()
    with pytest.raises(ValidationError):
        NormalizedMessage(role="user")

    assert NormalizedMessage(content="hello").role == ""

    msg = NormalizedMessage(role="assistant", content="")
    assert msg.finish_reason == ""


def test_agent_span_defaults_created_at_to_utc() -> None:
    span = AgentSpanCHInsertable(
        project_id="p1",
        trace_id="t1",
        span_id="s1",
        span_name="chat",
        started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )

    assert span.created_at.tzinfo is not None


def test_agent_span_output_type_is_literal() -> None:
    AgentSpanCHInsertable(
        project_id="p1",
        trace_id="t1",
        span_id="s1",
        span_name="chat",
        started_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        output_type="json",
    )

    with pytest.raises(ValidationError):
        AgentSpanCHInsertable.model_validate(
            {
                "project_id": "p1",
                "trace_id": "t1",
                "span_id": "s1",
                "span_name": "chat",
                "started_at": datetime.datetime(
                    2026, 1, 1, tzinfo=datetime.timezone.utc
                ),
                "output_type": "pdf",
            }
        )
