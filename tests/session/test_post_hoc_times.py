"""Tests that streaming end() honors caller-supplied started_at / ended_at.

Pre-fix: LLM / SubAgent / Turn end() clobbered self.ended_at = now(), and
all four span classes' _end_otel_span calls omitted end_time_ns — so the
emitted OTel span carried now() regardless of what the SDK object held.
SubAgent.__enter__ did the same for started_at.

Post-fix: streaming end() emits OTel spans byte-identical to the batch
path (log_turn / log_session) for the same inputs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session.session import LLM, Session, SubAgent, Tool, Turn, log_turn


def _at(seconds_offset: int) -> datetime:
    """Deterministic datetime, distinct from now()."""
    return datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds_offset)


def _to_ns(timestamp: datetime) -> int:
    return int(timestamp.timestamp() * 1_000_000_000)


# (class_label, factory, otel_span_name) — factory accepts **kwargs so tests
# can pass started_at / ended_at or omit them.
CASES = [
    (
        "Tool",
        lambda **kwargs: Tool(name="test-tool", **kwargs),
        "execute_tool test-tool",
    ),
    (
        "LLM",
        lambda **kwargs: LLM(model="gpt-4o", **kwargs),
        "chat gpt-4o",
    ),
    (
        "SubAgent",
        lambda **kwargs: SubAgent(name="researcher", **kwargs),
        "invoke_agent researcher",
    ),
    (
        "Turn",
        lambda **kwargs: Turn(agent_name="weather-bot", **kwargs),
        "invoke_agent weather-bot",
    ),
]
CLASS_LABELS = [case[0] for case in CASES]


def _only_span(spans: list, span_name: str):
    matches = [span for span in spans if span.name == span_name]
    assert len(matches) == 1, [span.name for span in matches]
    return matches[0]


@pytest.mark.parametrize(
    ("_class_label", "factory", "_span_name"), CASES, ids=CLASS_LABELS
)
def test_end_preserves_caller_ended_at(_class_label, factory, _span_name) -> None:
    """``ended_at`` set by the caller survives ``end()``."""
    ended_at = _at(5)
    span_obj = factory(ended_at=ended_at)
    span_obj.end()
    assert span_obj.ended_at == ended_at


@pytest.mark.parametrize(
    ("_class_label", "factory", "span_name"), CASES, ids=CLASS_LABELS
)
def test_otel_span_times_match_caller_values(
    otel_spans: InMemorySpanExporter, _class_label, factory, span_name
) -> None:
    """Emitted OTel span's ``start_time`` and ``end_time`` match caller values."""
    started_at, ended_at = _at(0), _at(3)
    with Session(session_id="test-session"):
        span_obj = factory(started_at=started_at, ended_at=ended_at)
        with span_obj:
            pass
    finished_span = _only_span(otel_spans.get_finished_spans(), span_name)
    assert finished_span.start_time == _to_ns(started_at)
    assert finished_span.end_time == _to_ns(ended_at)


@pytest.mark.parametrize(
    ("_class_label", "factory", "_span_name"), CASES, ids=CLASS_LABELS
)
def test_end_defaults_ended_at_to_now(_class_label, factory, _span_name) -> None:
    """No caller-supplied ``ended_at`` → ``end()`` fills in ``now()``."""
    span_obj = factory()
    span_obj.end()
    assert span_obj.ended_at is not None


def test_streaming_matches_batch_for_llm(otel_spans: InMemorySpanExporter) -> None:
    """Streaming and ``log_turn`` produce byte-identical OTel chat spans.

    Pre-fix divergence: streaming emitted ``now()`` end_times while batch
    honored ``ended_at``. This pins both paths together.
    """
    started_at, ended_at = _at(0), _at(5)

    otel_spans.clear()
    with (
        Session(session_id="test-session"),
        Turn(agent_name="weather-bot", started_at=started_at, ended_at=ended_at),
    ):
        with LLM(
            model="gpt-4o",
            provider_name="openai",
            started_at=started_at,
            ended_at=ended_at,
        ):
            pass
    streaming_chat_span = _only_span(otel_spans.get_finished_spans(), "chat gpt-4o")

    otel_spans.clear()
    log_turn(
        session_id="test-session",
        agent_name="weather-bot",
        started_at=started_at,
        ended_at=ended_at,
        spans=[
            LLM(
                model="gpt-4o",
                provider_name="openai",
                started_at=started_at,
                ended_at=ended_at,
            )
        ],
    )
    batch_chat_span = _only_span(otel_spans.get_finished_spans(), "chat gpt-4o")

    assert (streaming_chat_span.start_time, streaming_chat_span.end_time) == (
        batch_chat_span.start_time,
        batch_chat_span.end_time,
    )
    assert streaming_chat_span.start_time == _to_ns(started_at)
    assert streaming_chat_span.end_time == _to_ns(ended_at)
