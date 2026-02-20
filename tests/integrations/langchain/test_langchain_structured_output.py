"""Tests for LangChain structured output with Pydantic model classes.

These tests verify that the Weave LangChain integration handles non-JSON-serializable
objects (such as Pydantic model classes passed via with_structured_output) without
crashing. This is a regression test for https://github.com/wandb/weave/issues/4639.
"""

import datetime
from collections.abc import Generator
from uuid import uuid4

import pytest
from langchain_core.load import dumpd
from langchain_core.messages import HumanMessage
from langchain_core.tracers import Run
from pydantic import BaseModel, Field

from weave.integrations.langchain.langchain import WeaveTracer, langchain_patcher
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture(autouse=True)
def patch_langchain() -> Generator[None, None, None]:
    langchain_patcher.attempt_patch()
    yield
    langchain_patcher.undo_patch()


class Process(BaseModel):
    """A Pydantic model simulating structured output schema, as in the bug report."""

    canonical_process_name: str = Field(..., description="The canonical process")
    name: str = Field(..., description="The company specific alias")


def _run_tracer_lifecycle(
    client: WeaveClient,
    kwargs: dict,
) -> list:
    """Drive a WeaveTracer through a full on_chat_model_start → _finish_run cycle
    and return the recorded calls."""
    tracer = WeaveTracer()
    run_id = uuid4()
    messages = [[HumanMessage(content="test")]]

    tracer.on_chat_model_start(
        serialized={"name": "ChatOpenAI"},
        messages=messages,
        run_id=run_id,
        name="ChatOpenAI",
        **kwargs,
    )

    end_time = datetime.datetime.now(datetime.timezone.utc)
    end_run = Run(
        id=run_id,
        serialized={"name": "ChatOpenAI"},
        inputs={"messages": [[dumpd(msg) for msg in messages[0]]]},
        outputs={"generations": [{"text": "response"}]},
        extra=kwargs,
        events=[
            {"name": "start", "time": datetime.datetime.now(datetime.timezone.utc)},
            {"name": "end", "time": end_time},
        ],
        start_time=datetime.datetime.now(datetime.timezone.utc),
        end_time=end_time,
        run_type="llm",
        name="ChatOpenAI",
    )
    tracer._finish_run(end_run)

    return list(client.get_calls(filter=tsi.CallsFilter(trace_roots_only=True)))


@pytest.mark.skip_clickhouse_client
def test_tracer_traces_call_when_kwargs_contain_pydantic_model_class(
    client: WeaveClient,
) -> None:
    """
    Requirement: WeaveTracer must successfully trace LLM calls that use
                 with_structured_output(PydanticModel), without errors.
    Interface: WeaveTracer callback lifecycle (on_chat_model_start → finish)
    Given: kwargs containing a Pydantic model class (simulating with_structured_output)
    When: A full tracer start/end lifecycle completes
    Then: A trace call is recorded with both start and end times, no exception.
    """
    calls = _run_tracer_lifecycle(
        client,
        kwargs={"invocation_params": {"model": "gpt-4o-mini", "response_format": Process}},
    )

    assert len(calls) >= 1, "Expected at least one traced call"
    call = calls[0]
    assert call.started_at is not None
    assert call.ended_at is not None
    assert call.exception is None

    # The Pydantic model class should be serialized as its JSON schema
    extra = call.output["extra"]
    response_format = extra["invocation_params"]["response_format"]
    assert response_format["title"] == "Process"
    assert response_format["type"] == "object"
    assert "canonical_process_name" in response_format["properties"]
    assert "name" in response_format["properties"]


@pytest.mark.skip_clickhouse_client
def test_tracer_traces_call_when_kwargs_contain_arbitrary_non_serializable_objects(
    client: WeaveClient,
) -> None:
    """
    Requirement: WeaveTracer must be robust against ANY non-JSON-serializable
                 object in kwargs, not just Pydantic model classes.
    Interface: WeaveTracer callback lifecycle (on_chat_model_start → finish)
    Given: kwargs containing a custom class instance, a set, and a lambda
    When: A full tracer start/end lifecycle completes
    Then: A trace call is recorded with both start and end times, no exception.
    """

    class _Custom:
        pass

    calls = _run_tracer_lifecycle(
        client,
        kwargs={"custom_obj": _Custom(), "a_set": {1, 2, 3}, "a_lambda": lambda x: x},
    )

    assert len(calls) >= 1, "Expected at least one traced call"
    call = calls[0]
    assert call.started_at is not None
    assert call.ended_at is not None
    assert call.exception is None

    extra = call.output["extra"]
    # Sets are converted to lists
    assert sorted(extra["a_set"]) == [1, 2, 3]
    # Non-serializable objects fall back to their string repr
    assert isinstance(extra["custom_obj"], str)
    assert "_Custom" in extra["custom_obj"]
    assert isinstance(extra["a_lambda"], str)
    assert "lambda" in extra["a_lambda"]
