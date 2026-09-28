"""`build_completion_span` must give each completion source its own agent identity."""

import datetime

import pytest

from weave.trace_server.agents.completion_spans import (
    INSIGHTS_JUDGE_AGENT_NAME,
    INSIGHTS_NAMER_AGENT_NAME,
    PLAYGROUND_AGENT_NAME,
    SIGNALS_AGENT_NAME,
    build_completion_span,
)
from weave.trace_server.trace_server_interface import CompletionsCreateRequestInputs

STARTED_AT = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
ENDED_AT = STARTED_AT + datetime.timedelta(seconds=1)


@pytest.mark.parametrize(
    ("source", "expected_agent_name"),
    [
        ("playground", PLAYGROUND_AGENT_NAME),
        ("signals", SIGNALS_AGENT_NAME),
        ("insights_cluster", INSIGHTS_NAMER_AGENT_NAME),
        ("insights_worker", INSIGHTS_JUDGE_AGENT_NAME),
        (None, PLAYGROUND_AGENT_NAME),
        ("unrecognized", PLAYGROUND_AGENT_NAME),
    ],
)
def test_agent_name_is_keyed_on_source(
    source: str | None, expected_agent_name: str
) -> None:
    """Each known source gets its own `agent_name`/`span_name`; an unknown one
    still degrades to the playground identity rather than raising.
    """
    span = build_completion_span(
        project_id="p1",
        trace_id="t1",
        span_id="s1",
        conversation_id="c1",
        conversation_name="conv",
        started_at=STARTED_AT,
        ended_at=ENDED_AT,
        provider_name="openai",
        model_name="gpt-4o-mini",
        request_inputs=CompletionsCreateRequestInputs(
            model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
        ),
        response={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        wb_user_id="u1",
        retention_days=30,
        source=source,
    )

    assert (span.agent_name, span.span_name) == (
        expected_agent_name,
        expected_agent_name,
    )
    assert span.custom_attrs_string["weave.source"] == (source or "playground")


def test_insights_namer_and_judge_are_never_the_same_identity() -> None:
    """The two insights sources must not collapse onto one agent, or a UI/query
    scoped to one insights role would surface the other's traffic instead.
    """
    assert INSIGHTS_NAMER_AGENT_NAME not in {
        PLAYGROUND_AGENT_NAME,
        SIGNALS_AGENT_NAME,
        INSIGHTS_JUDGE_AGENT_NAME,
    }
