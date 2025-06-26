import agents
import pytest
from agents import Agent, GuardrailFunctionOutput, InputGuardrail, Runner
from pydantic import BaseModel

from weave.integrations.openai_agents.openai_agents import WeaveTracingProcessor
from weave.trace.weave_client import WeaveClient

# TODO: Responses should be updated once we have patching for the new Responses API


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

    assert len(calls) == 3

    trace_root = calls[0]
    trace_root.inputs["name"] = "Agent workflow"
    trace_root.output["status"] = "completed"
    trace_root.output["metrics"] = {}
    trace_root.output["metadata"] = {}

    agent_call = calls[1]
    agent_call.inputs["name"] = "Assistant"
    agent_call.output["output"] = None
    agent_call.output["metrics"] = {}
    agent_call.output["metadata"] = {"tools": [], "handoffs": [], "output_type": "str"}
    agent_call.output["error"] = None

    response_call = calls[2]
    response_call.inputs["name"] = "Response"
    response_call.inputs["input"] = [
        {
            "content": "Write a haiku about recursion in programming.",
            "role": "user",
        }
    ]

    val = response_call.output["output"][0]
    assert val.role == "assistant"
    assert val.type == "message"
    assert val.status == "completed"
    assert (
        val.content[0].text
        == "Code calls to itself,  \nInfinite loops in silence,  \nPatterns emerge clear."
    )


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
