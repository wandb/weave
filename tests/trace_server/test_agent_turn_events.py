"""Unit tests for the turn-ended event helpers."""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from weave.trace_server.agents.events import AgentTurnEndedEvent
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.agents.turn_events import (
    build_turn_ended_events,
    emit_turn_ended_events,
)

_LATER = datetime.datetime(2024, 1, 1, 12, 0, 0)


def _make_row(
    *,
    span_id: str = "s",
    parent_span_id: str = "",
    trace_id: str = "t",
    ended_at: datetime.datetime | None = None,
    **kwargs,
) -> AgentSpanCHInsertable:
    return AgentSpanCHInsertable(
        project_id="p",
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        span_name="n",
        started_at=datetime.datetime(2024, 1, 1, 11, 0, 0),
        ended_at=ended_at if ended_at is not None else datetime.datetime(1970, 1, 1),
        **kwargs,
    )


def test_build_events_skips_non_root_spans() -> None:
    rows = [_make_row(parent_span_id="root", ended_at=_LATER)]
    assert build_turn_ended_events(rows, "p") == []


def test_build_events_skips_unfinished_root_spans() -> None:
    rows = [_make_row(parent_span_id="")]  # ended_at defaults to epoch
    assert build_turn_ended_events(rows, "p") == []


def test_build_events_emits_for_completed_root_span() -> None:
    rows = [
        _make_row(
            span_id="root",
            parent_span_id="",
            trace_id="tr",
            ended_at=_LATER,
            conversation_id="c",
            agent_name="a",
            operation_name="invoke_agent",
            request_model="gpt-5",
        )
    ]
    events = build_turn_ended_events(rows, "p")
    assert len(events) == 1
    e = events[0]
    assert e.project_id == "p"
    assert e.trace_id == "tr"
    assert e.root_span_id == "root"
    assert e.conversation_id == "c"
    assert e.agent_name == "a"
    assert e.operation_name == "invoke_agent"
    assert e.request_model == "gpt-5"
    assert e.ended_at_ns == int(_LATER.timestamp() * 1_000_000_000)


def test_emit_events_produces_and_flushes() -> None:
    producer = MagicMock()
    rows = [_make_row(parent_span_id="", ended_at=_LATER)]

    count = emit_turn_ended_events(producer, rows, "p")

    assert count == 1
    producer.produce_agent_turn_ended.assert_called_once()
    event_arg = producer.produce_agent_turn_ended.call_args.args[0]
    assert isinstance(event_arg, AgentTurnEndedEvent)
    producer.flush.assert_called_once_with(0)


def test_emit_events_noop_when_no_qualifying_spans() -> None:
    producer = MagicMock()
    rows = [_make_row(parent_span_id="child", ended_at=_LATER)]

    count = emit_turn_ended_events(producer, rows, "p")

    assert count == 0
    producer.produce_agent_turn_ended.assert_not_called()
    producer.flush.assert_not_called()
