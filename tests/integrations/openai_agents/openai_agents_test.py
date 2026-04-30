from unittest.mock import Mock

import agents
import pytest
from agents import Agent, GuardrailFunctionOutput, InputGuardrail, Runner
from agents.tracing import (
    AgentSpanData,
    GenerationSpanData,
    ResponseSpanData,
    Span,
    TaskSpanData,
    Trace,
    TurnSpanData,
)
from pydantic import BaseModel

from weave.integrations.integration_utilities import op_name_from_ref
from weave.integrations.openai_agents import openai_agents as oa_module
from weave.integrations.openai_agents.openai_agents import (
    WeaveTracingProcessor,
    _call_name,
    _is_task_span_data,
    _is_turn_span_data,
    _usage_to_metrics,
)
from weave.trace.weave_client import WeaveClient


@pytest.fixture
def setup_tests():
    # This is required because OpenAI by default adds its own trace processor which causes issues in the test.
    # We can't just add our trace processor with autopatching because it wont remove the OpenAI trace processor.
    # Instead, we manually set the trace processors to just be ours.  This simplifies testing.
    # However, by default the autopatching keeps the default OpenAI trace processor, and additionally installs the Weave processor.

    agents.set_trace_processors([WeaveTracingProcessor()])


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_agents_quickstart(client: WeaveClient, setup_tests) -> None:
    agent = Agent(name="Assistant", instructions="You are a helpful assistant")

    result = Runner.run_sync(agent, "Write a haiku about recursion in programming.")
    calls = client.get_calls()

    assert len(calls) == 4

    trace_root = calls[0]
    assert trace_root.inputs["name"] == "Agent workflow"
    assert trace_root.output["status"] == "completed"
    assert trace_root.output["metrics"] == {}
    assert trace_root.output["metadata"] == {}

    task_call = calls[1]
    assert op_name_from_ref(task_call.op_name) == "openai_agent_task"
    assert task_call.parent_id == trace_root.id
    assert task_call.inputs["name"] == "Agent workflow"
    assert task_call.output["output"] is None
    assert task_call.output["metrics"] == {
        "tokens": 60,
        "prompt_tokens": 43,
        "completion_tokens": 17,
    }
    assert task_call.output["metadata"] == {"name": "Agent workflow"}
    assert task_call.output["error"] is None

    agent_call = calls[2]
    assert agent_call.parent_id == task_call.id
    assert agent_call.inputs["name"] == "Assistant"
    assert agent_call.output["output"] is None
    assert agent_call.output["metrics"] == {}
    assert agent_call.output["metadata"] == {
        "tools": [],
        "handoffs": [],
        "output_type": "str",
    }
    assert agent_call.output["error"] is None

    turn_call = calls[3]
    assert op_name_from_ref(turn_call.op_name) == "openai_agent_turn"
    assert turn_call.parent_id == agent_call.id
    assert turn_call.inputs["name"] == "Assistant turn 1"
    assert turn_call.output["output"] is None
    assert turn_call.output["metrics"] == {
        "tokens": 60,
        "prompt_tokens": 43,
        "completion_tokens": 17,
    }
    assert turn_call.output["metadata"] == {
        "turn": 1,
        "agent_name": "Assistant",
    }
    assert turn_call.output["error"] is None


@pytest.mark.skip(
    reason="This test works, but the order of requests to OpenAI can be mixed up (by the Agent framework).  This causes the test to fail more than reasonable in CI."
)
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_agents_quickstart_homework(
    client: WeaveClient, setup_tests
) -> None:
    class HomeworkOutput(BaseModel):
        is_homework: bool
        reasoning: str

    guardrail_agent = Agent(
        name="Guardrail check",
        instructions="Check if the user is asking about homework.",
        output_type=HomeworkOutput,
    )

    math_tutor_agent = Agent(
        name="Math Tutor",
        handoff_description="Specialist agent for math questions",
        instructions="You provide help with math problems. Explain your reasoning at each step and include examples",
    )

    history_tutor_agent = Agent(
        name="History Tutor",
        handoff_description="Specialist agent for historical questions",
        instructions="You provide assistance with historical queries. Explain important events and context clearly.",
    )

    async def homework_guardrail(ctx, agent, input_data):
        result = await Runner.run(guardrail_agent, input_data, context=ctx.context)
        final_output = result.final_output_as(HomeworkOutput)
        return GuardrailFunctionOutput(
            output_info=final_output,
            tripwire_triggered=not final_output.is_homework,
        )

    triage_agent = Agent(
        name="Triage Agent",
        instructions="You determine which agent to use based on the user's homework question",
        handoffs=[history_tutor_agent, math_tutor_agent],
        input_guardrails=[
            InputGuardrail(guardrail_function=homework_guardrail),
        ],
    )

    result = await Runner.run(
        triage_agent, "who was the first president of the united states?"
    )
    with pytest.raises(agents.exceptions.InputGuardrailTripwireTriggered):
        result = await Runner.run(triage_agent, "what is life")

    #####################
    ### Result1 Block ###
    #####################

    calls = client.get_calls()
    assert len(calls) == 14

    # ====================
    call0 = calls[0]
    assert call0.inputs["name"] == "Agent workflow"
    assert call0.output["status"] == "completed"
    assert call0.output["metrics"] == {}
    assert call0.output["metadata"] == {}

    # ====================
    call1 = calls[1]
    assert call1.inputs["name"] == "Triage Agent"
    assert call1.output["output"] is None
    assert call1.output["metrics"] == {}
    assert call1.output["metadata"]["tools"] == []
    assert call1.output["metadata"]["handoffs"] == ["History Tutor", "Math Tutor"]
    assert call1.output["metadata"]["output_type"] == "str"
    assert call1.output["error"] is None

    # ====================
    call2 = calls[2]
    assert call2.inputs["name"] == "homework_guardrail"
    assert call2.output["output"] is None
    assert call2.output["metrics"] == {}
    assert call2.output["metadata"] == {"triggered": False}
    assert call2.output["error"] is None

    # ====================
    call3 = calls[3]
    assert call3.inputs["name"] == "Guardrail check"
    assert call3.output["output"] is None
    assert call3.output["metrics"] == {}
    assert call3.output["metadata"]["tools"] == []
    assert call3.output["metadata"]["handoffs"] == []
    assert call3.output["metadata"]["output_type"] == "HomeworkOutput"
    assert call3.output["error"] is None

    # ====================
    call4 = calls[4]
    assert call4.inputs["name"] == "Response"
    assert (
        call4.inputs["input"][0]["content"]
        == "who was the first president of the united states?"
    )
    assert call4.inputs["input"][0]["role"] == "user"

    val4 = call4.output["output"][0]
    assert val4.name == "transfer_to_history_tutor"
    assert val4.type == "function_call"
    assert val4.status == "completed"

    # ====================
    call5 = calls[5]
    assert call5.inputs["name"] == "Handoff"
    assert call5.output["output"] is None
    assert call5.output["metrics"] == {}
    assert call5.output["metadata"]["from_agent"] == "Triage Agent"
    assert call5.output["metadata"]["to_agent"] == "History Tutor"
    assert call5.output["error"] is None

    # ====================
    call6 = calls[6]
    assert call6.inputs["name"] == "Response"
    assert (
        call6.inputs["input"][0]["content"]
        == "who was the first president of the united states?"
    )
    assert call6.inputs["input"][0]["role"] == "user"

    val6 = call6.output["output"][0]
    assert val6.role == "assistant"
    assert val6.type == "message"
    assert val6.status == "completed"

    # ====================
    call7 = calls[7]
    assert call7.inputs["name"] == "History Tutor"
    assert call7.output["output"] is None
    assert call7.output["metrics"] == {}
    assert call7.output["metadata"]["tools"] == []
    assert call7.output["metadata"]["handoffs"] == []
    assert call7.output["metadata"]["output_type"] == "str"
    assert call7.output["error"] is None

    # ====================
    call8 = calls[8]
    assert call8.inputs["name"] == "Response"
    assert (
        call8.inputs["input"][0]["content"]
        == "who was the first president of the united states?"
    )
    assert call8.inputs["input"][0]["role"] == "user"
    assert call8.inputs["input"][1]["name"] == "transfer_to_history_tutor"
    assert call8.inputs["input"][1]["type"] == "function_call"
    assert call8.inputs["input"][1]["status"] == "completed"

    val8 = call8.output["output"][0]
    assert val8.role == "assistant"
    assert val8.type == "message"
    assert val8.status == "completed"

    #####################
    ### Result2 Block ###
    #####################

    call9 = calls[9]
    assert call9.inputs["name"] == "Agent workflow"
    assert call9.output["status"] == "completed"
    assert call9.output["metrics"] == {}
    assert call9.output["metadata"] == {}

    # ====================
    call10 = calls[10]
    assert call10.inputs["name"] == "Triage Agent"
    assert call10.output["output"] is None
    assert call10.output["metrics"] == {}
    assert call10.output["metadata"]["tools"] == []
    assert call10.output["metadata"]["handoffs"] == ["History Tutor", "Math Tutor"]
    assert call10.output["metadata"]["output_type"] == "str"

    # ====================
    call11 = calls[11]
    assert call11.inputs["name"] == "homework_guardrail"
    assert call11.output["output"] is None
    assert call11.output["metrics"] == {}
    assert call11.output["metadata"]["triggered"] is True
    assert call11.output["error"] is None

    # ====================
    call12 = calls[12]
    assert call12.inputs["name"] == "Guardrail check"
    assert call12.output["output"] is None
    assert call12.output["metrics"] == {}
    assert call12.output["metadata"]["tools"] == []
    assert call12.output["metadata"]["handoffs"] == []
    assert call12.output["metadata"]["output_type"] == "HomeworkOutput"

    # ====================
    call13 = calls[13]
    assert call13.inputs["name"] == "Response"
    assert call13.inputs["input"][0]["content"] == "what is life"
    assert call13.inputs["input"][0]["role"] == "user"

    val13 = call13.output["output"][0]
    assert val13.role == "assistant"
    assert val13.type == "message"
    assert val13.status == "completed"


def test_tracing_processor_cleanup(client: WeaveClient) -> None:
    processor = WeaveTracingProcessor()

    # Mock Trace
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_1"
    trace.name = "test_trace"

    # Start Trace
    processor.on_trace_start(trace)
    assert "trace_1" in processor._trace_calls
    assert "trace_1" in processor._trace_data

    # Mock Span
    # We use the real AgentSpanData class if available via import, but wrapped in a mock
    # to allow setting attributes easily if needed, or just use a mock that passes spec check.
    span_data = Mock(spec=AgentSpanData)
    span_data.type = "agent"
    span_data.name = "test_agent"
    span_data.tools = []
    span_data.handoffs = []
    span_data.output_type = "str"
    # Attributes that might be accessed:
    span_data.model_dump = Mock(return_value={})

    span = Mock(spec=Span)
    span.trace_id = "trace_1"
    span.span_id = "span_1"
    span.parent_id = None
    span.span_data = span_data
    span.error = None

    # We need to trick isinstance(span.span_data, AgentSpanData) to return True.
    # Since we imported AgentSpanData, we can set __class__ on the mock or use the real object if possible.
    # Let's try to use the real object for span_data if it's a Pydantic model.
    # If AgentSpanData is a TypedDict or Pydantic model, we can try to instantiate it.
    # But to be safe against signature mismatch in this environment, we'll use side_effect on isinstance
    # OR, more robustly, we can just use a Mock and patch 'weave.integrations.openai_agents.openai_agents.AgentSpanData'
    # But that's hard since it's imported.

    # Simpler: Just set the __class__ of the mock to AgentSpanData
    span_data.__class__ = AgentSpanData

    # Start Span
    processor.on_span_start(span)
    assert "span_1" in processor._span_calls

    # End Span
    processor.on_span_end(span)
    assert "span_1" not in processor._span_calls

    # End Trace
    processor.on_trace_end(trace)
    assert "trace_1" not in processor._trace_calls
    assert "trace_1" not in processor._trace_data
    assert "trace_1" not in processor._ended_traces

    # Test Shutdown/Flush Cleanup
    # Re-populate
    processor.on_trace_start(trace)
    assert "trace_1" in processor._trace_calls

    processor.force_flush()
    assert len(processor._trace_calls) == 0
    assert len(processor._trace_data) == 0

    # Re-populate
    processor.on_trace_start(trace)
    processor.shutdown()
    assert len(processor._trace_calls) == 0
    assert len(processor._trace_data) == 0


def test_response_spans_are_skipped(client: WeaveClient) -> None:
    """Test that ResponseSpanData spans are skipped to prevent double-tracking.

    Response spans should not be tracked because the openai.responses.create
    call (from OpenAI SDK integration) already captures this data.
    """
    processor = WeaveTracingProcessor()

    # Mock Trace
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_1"
    trace.name = "test_trace"

    # Start Trace
    processor.on_trace_start(trace)
    assert "trace_1" in processor._trace_calls
    assert "trace_1" in processor._trace_data

    # Mock ResponseSpanData
    response_span_data = Mock(spec=ResponseSpanData)
    response_span_data.type = "response"
    response_span_data.input = [{"role": "user", "content": "test"}]
    response_span_data.response = Mock()
    response_span_data.response.output = [{"role": "assistant", "content": "response"}]
    response_span_data.response.metadata = {}
    response_span_data.response.usage = None
    response_span_data.response.model_dump = Mock(return_value={})
    response_span_data.__class__ = ResponseSpanData

    response_span = Mock(spec=Span)
    response_span.trace_id = "trace_1"
    response_span.span_id = "response_span_1"
    response_span.parent_id = None
    response_span.span_data = response_span_data
    response_span.error = None

    # Start Response Span - should be skipped
    processor.on_span_start(response_span)
    # Response spans are deferred to on_span_end, so not checked here

    # End Response Span - should be skipped entirely
    processor.on_span_end(response_span)

    # Verify that NO call was created for the Response span
    assert "response_span_1" not in processor._span_calls

    # Clean up
    processor.on_trace_end(trace)
    assert "trace_1" not in processor._trace_calls
    assert "trace_1" not in processor._trace_data


def test_newer_agent_task_and_turn_fields_prevent_unknown_blocks(
    client: WeaveClient,
) -> None:
    """Task/turn span fields are required to avoid Unknown blocks in newer SDKs."""
    processor = WeaveTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_real"
    trace.name = "test_trace_real"
    processor.on_trace_start(trace)

    task_span = Mock(spec=Span)
    task_span.trace_id = trace.trace_id
    task_span.span_id = "task_span_real"
    task_span.parent_id = None
    task_span.span_data = TaskSpanData(
        name="Runner task",
        usage={"input_tokens": 0, "output_tokens": 5, "total_tokens": 5},
        metadata={"session_id": "session-1"},
    )
    task_span.error = None
    processor.on_span_start(task_span)

    turn_span = Mock(spec=Span)
    turn_span.trace_id = trace.trace_id
    turn_span.span_id = "turn_span_real"
    turn_span.parent_id = task_span.span_id
    turn_span.span_data = TurnSpanData(
        turn=2,
        agent_name="Assistant",
        usage={"input_tokens": 7, "output_tokens": 11},
        metadata={"callback": "session_input"},
    )
    turn_span.error = None
    processor.on_span_start(turn_span)

    processor.on_span_end(turn_span)
    processor.on_span_end(task_span)
    processor.on_trace_end(trace)

    trace_call, task_call, turn_call = client.get_calls()

    assert op_name_from_ref(task_call.op_name) == "openai_agent_task"
    assert task_call.parent_id == trace_call.id
    assert task_call.inputs["name"] == "Runner task"
    assert task_call.output["metrics"] == {
        "tokens": 5,
        "prompt_tokens": 0,
        "completion_tokens": 5,
    }
    assert task_call.output["metadata"] == {
        "name": "Runner task",
        "session_id": "session-1",
    }

    assert op_name_from_ref(turn_call.op_name) == "openai_agent_turn"
    assert turn_call.parent_id == task_call.id
    assert turn_call.inputs["name"] == "Assistant turn 2"
    assert turn_call.output["metrics"] == {
        "tokens": 18,
        "prompt_tokens": 7,
        "completion_tokens": 11,
    }
    assert turn_call.output["metadata"] == {
        "turn": 2,
        "agent_name": "Assistant",
        "callback": "session_input",
    }


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (None, {}),
        ({}, {}),
        (
            {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
            {"tokens": 7, "prompt_tokens": 3, "completion_tokens": 4},
        ),
        (
            {"input_tokens": 3, "output_tokens": 4},
            {"tokens": 7, "prompt_tokens": 3, "completion_tokens": 4},
        ),
        (
            {"input_tokens": 3},
            {"tokens": 3, "prompt_tokens": 3, "completion_tokens": None},
        ),
        (
            {"output_tokens": 4},
            {"tokens": 4, "prompt_tokens": None, "completion_tokens": 4},
        ),
    ],
)
def test_usage_to_metrics_branches(client: WeaveClient, usage, expected) -> None:
    assert _usage_to_metrics(usage) == expected


@pytest.mark.parametrize(
    ("turn", "agent_name", "expected"),
    [
        (1, "Assistant", "Assistant turn 1"),
        (2, None, "Turn 2"),
        (None, "Helper", "Helper turn"),
        (None, None, "Turn"),
    ],
)
def test_call_name_for_turn_span_branches(
    client: WeaveClient, turn, agent_name, expected
) -> None:
    span_data = Mock(spec=TurnSpanData)
    span_data.name = None
    span_data.turn = turn
    span_data.agent_name = agent_name
    span_data.__class__ = TurnSpanData

    span = Mock(spec=Span)
    span.span_data = span_data

    assert _call_name(span) == expected


def test_task_and_turn_log_data_handle_missing_optional_fields(
    client: WeaveClient,
) -> None:
    """Task/turn spans with missing optional fields produce empty metrics and
    only the metadata they actually carry. Exercises the False branches of the
    isinstance/getattr guards in _task_log_data and _turn_log_data.
    """
    processor = WeaveTracingProcessor()

    task_span_data = TaskSpanData(name="placeholder")
    task_span_data.name = None
    task_span_data.metadata = "not-a-dict"
    task_span_data.usage = None
    task_span = Mock(spec=Span)
    task_span.span_data = task_span_data

    task_log = processor._task_log_data(task_span)
    assert task_log["metadata"] == {}
    assert task_log["metrics"] == {}

    turn_span_data = TurnSpanData(turn=1, agent_name="placeholder")
    turn_span_data.turn = None
    turn_span_data.agent_name = None
    turn_span_data.metadata = None
    turn_span_data.usage = None
    turn_span = Mock(spec=Span)
    turn_span.span_data = turn_span_data

    turn_log = processor._turn_log_data(turn_span)
    assert turn_log["metadata"] == {}
    assert turn_log["metrics"] == {}
    assert _call_name(turn_span) == "Turn"


def test_generation_log_data_uses_usage_metrics(client: WeaveClient) -> None:
    """_generation_log_data delegates token-metric assembly to _usage_to_metrics."""
    span_data = GenerationSpanData(
        input=[{"role": "user", "content": "hi"}],
        output=[{"role": "assistant", "content": "hello"}],
        model="gpt-4o",
        model_config={"temperature": 0.0},
        usage={"input_tokens": 5, "output_tokens": 7},
    )
    span = Mock(spec=Span)
    span.span_data = span_data

    result = WeaveTracingProcessor()._generation_log_data(span)
    assert result["inputs"] == {"input": [{"role": "user", "content": "hi"}]}
    assert result["outputs"] == {"output": [{"role": "assistant", "content": "hello"}]}
    assert result["metadata"] == {
        "model": "gpt-4o",
        "model_config": {"temperature": 0.0},
    }
    assert result["metrics"] == {
        "tokens": 12,
        "prompt_tokens": 5,
        "completion_tokens": 7,
    }


def test_optional_span_classes_absent_falls_back_to_unknown(
    client: WeaveClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When TaskSpanData/TurnSpanData failed to import (older SDK), the
    isinstance helpers must short-circuit to False and _log_data must fall
    through to the Unknown branch instead of erroring on isinstance(None).
    """
    monkeypatch.setattr(oa_module, "TaskSpanData", None)
    monkeypatch.setattr(oa_module, "TurnSpanData", None)

    sentinel = object()
    assert _is_task_span_data(sentinel) is False
    assert _is_turn_span_data(sentinel) is False

    class UnknownSpanData:
        type = "unknown"
        name = None

    span = Mock(spec=Span)
    span.trace_id = "trace_legacy"
    span.span_id = "span_legacy"
    span.parent_id = None
    span_data = UnknownSpanData()
    span.span_data = span_data
    span.error = None

    assert _call_name(span) == "Unknown"

    processor = WeaveTracingProcessor()
    log_data = processor._log_data(span)
    assert log_data == {
        "inputs": {},
        "outputs": {},
        "metadata": {},
        "metrics": {},
        "error": None,
    }
