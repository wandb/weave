"""Tests that streaming end() honors caller-supplied ``started_at`` / ``ended_at``.

Before this PR:
- ``LLM.end()`` / ``SubAgent.end()`` / ``Turn.end()`` unconditionally clobbered
  ``self.ended_at = now()``, so a caller-set value was lost.
- All four span classes' ``_end_otel_span()`` calls omitted ``end_time_ns``,
  so the emitted OTel span carried ``now()`` as its end time regardless of
  what was on the SDK object.
- ``SubAgent.__enter__`` ignored ``self.started_at`` entirely — both clobbered
  the field with ``now()`` and never passed ``start_time_ns`` to OTel.

The batch path (``log_turn`` / ``log_session``) already honored timestamps
via ``_emit_span_now``. After this PR the streaming and batch paths emit
byte-identical spans for the same inputs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session.session import (
    LLM,
    Session,
    SubAgent,
    Tool,
    Turn,
    log_turn,
)


def _ts(seconds_offset: int) -> datetime:
    """A deterministic datetime far enough in the past that ``now()`` can't equal it."""
    return datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds_offset)


def _ns(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000_000)


def _find(spans: list, name_prefix: str):
    matches = [sp for sp in spans if sp.name.startswith(name_prefix)]
    assert len(matches) == 1, (
        f"expected 1 span with prefix {name_prefix!r}, got {[s.name for s in matches]}"
    )
    return matches[0]


# ---------------------------------------------------------------------------
# Streaming end() preserves caller-supplied ended_at
# ---------------------------------------------------------------------------


class TestEndedAtPreservedOnSdkObject:
    """Pydantic field round-trip: ``ended_at`` set by the caller survives ``end()``."""

    def test_tool(self) -> None:
        t = Tool(name="f", ended_at=_ts(5))
        t.end()
        assert t.ended_at == _ts(5)

    def test_llm(self) -> None:
        c = LLM(model="gpt-4o", ended_at=_ts(5))
        c.end()
        assert c.ended_at == _ts(5)

    def test_subagent(self) -> None:
        sa = SubAgent(name="x", ended_at=_ts(5))
        sa.end()
        assert sa.ended_at == _ts(5)

    def test_turn(self) -> None:
        t = Turn(agent_name="bot", ended_at=_ts(5))
        t.end()
        assert t.ended_at == _ts(5)


# ---------------------------------------------------------------------------
# Streaming OTel span carries the caller-supplied end_time
# ---------------------------------------------------------------------------


class TestOtelEndTimeMatchesEndedAt:
    """The emitted OTel span's ``end_time`` matches ``self.ended_at``, not ``now()``."""

    def test_tool(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"):
            t = Tool(name="f", started_at=_ts(0), ended_at=_ts(3))
            with t:
                pass
        span = _find(otel_spans.get_finished_spans(), "execute_tool")
        assert span.start_time == _ns(_ts(0))
        assert span.end_time == _ns(_ts(3))

    def test_llm(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"):
            c = LLM(model="gpt-4o", started_at=_ts(0), ended_at=_ts(3))
            with c:
                pass
        span = _find(otel_spans.get_finished_spans(), "chat")
        assert span.start_time == _ns(_ts(0))
        assert span.end_time == _ns(_ts(3))

    def test_subagent(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"), Turn(agent_name="bot") as turn:
            sa = SubAgent(name="x", started_at=_ts(0), ended_at=_ts(3))
            with sa:
                pass
            _ = turn  # silence "unused"
        spans = otel_spans.get_finished_spans()
        sa_span = next(
            sp
            for sp in spans
            if sp.name == "invoke_agent x"
            and sp.attributes.get("gen_ai.agent.name") == "x"
        )
        assert sa_span.start_time == _ns(_ts(0))
        assert sa_span.end_time == _ns(_ts(3))

    def test_turn(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(session_id="s"):
            t = Turn(agent_name="bot", started_at=_ts(0), ended_at=_ts(3))
            with t:
                pass
        span = _find(otel_spans.get_finished_spans(), "invoke_agent")
        assert span.start_time == _ns(_ts(0))
        assert span.end_time == _ns(_ts(3))


# ---------------------------------------------------------------------------
# Default (no caller-supplied timestamps) still works
# ---------------------------------------------------------------------------


class TestDefaultTimestampsStillWork:
    """When the caller doesn't supply ``ended_at``, ``end()`` fills in ``now()``."""

    def test_llm_ended_at_set_on_end(self) -> None:
        c = LLM(model="gpt-4o")
        c.end()
        assert c.ended_at is not None

    def test_subagent_ended_at_set_on_end(self) -> None:
        sa = SubAgent(name="x")
        sa.end()
        assert sa.ended_at is not None

    def test_turn_ended_at_set_on_end(self) -> None:
        t = Turn(agent_name="bot")
        t.end()
        assert t.ended_at is not None


# ---------------------------------------------------------------------------
# SubAgent.__enter__ now honors started_at (previously the odd one out)
# ---------------------------------------------------------------------------


class TestSubAgentEnterHonorsStartedAt:
    def test_preserves_existing_started_at(self) -> None:
        sa = SubAgent(name="x", started_at=_ts(0))
        with sa:
            pass
        assert sa.started_at == _ts(0)

    def test_sets_started_at_when_none(self) -> None:
        sa = SubAgent(name="x")
        with sa:
            pass
        assert sa.started_at is not None

    def test_otel_start_time_matches_started_at(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(session_id="s"), Turn(agent_name="bot"):
            sa = SubAgent(name="x", started_at=_ts(0), ended_at=_ts(2))
            with sa:
                pass
        spans = otel_spans.get_finished_spans()
        sa_span = next(sp for sp in spans if sp.name == "invoke_agent x")
        assert sa_span.start_time == _ns(_ts(0))


# ---------------------------------------------------------------------------
# Streaming == batch parity (the headline contract this PR establishes)
# ---------------------------------------------------------------------------


class TestStreamingMatchesBatch:
    """Same inputs through streaming vs ``log_turn`` produce identical spans.

    This is the regression test for the divergence that motivated the PR:
    pre-fix, streaming emitted ``now()`` end_times while batch honored
    ``ended_at``. The two paths now agree.
    """

    def test_llm_streaming_matches_log_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        started, ended = _ts(0), _ts(5)

        otel_spans.clear()
        with (
            Session(session_id="s"),
            Turn(agent_name="bot", started_at=started, ended_at=ended),
        ):
            llm = LLM(
                model="gpt-4o",
                provider_name="openai",
                started_at=started,
                ended_at=ended,
            )
            with llm:
                pass
        streaming_chat = _find(otel_spans.get_finished_spans(), "chat")
        streaming = (streaming_chat.start_time, streaming_chat.end_time)

        otel_spans.clear()
        log_turn(
            session_id="s",
            agent_name="bot",
            started_at=started,
            ended_at=ended,
            spans=[
                LLM(
                    model="gpt-4o",
                    provider_name="openai",
                    started_at=started,
                    ended_at=ended,
                )
            ],
        )
        batch_chat = _find(otel_spans.get_finished_spans(), "chat")
        batch = (batch_chat.start_time, batch_chat.end_time)

        assert streaming == batch
        assert streaming == (_ns(started), _ns(ended))
