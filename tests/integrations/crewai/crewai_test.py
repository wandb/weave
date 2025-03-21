import pytest

from weave.integrations.integration_utilities import (
    flatten_calls,
    flattened_calls_to_names,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter


def get_crew():
    from crewai import Agent, Crew, Process, Task

    researcher = Agent(
        role="Market Research Specialist",
        goal="Find comprehensive market data on emerging technologies",
        backstory="You are an expert at discovering market trends and gathering data.",
    )

    research_task = Task(
        description="Research the current market landscape for AI-powered healthcare solutions",
        expected_output="Comprehensive market data including key players, market size, and growth trends",
        agent=researcher,
    )

    crew = Crew(
        agents=[researcher],
        tasks=[research_task],
        process=Process.sequential,
        verbose=True,
    )

    return crew


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_crewai_simple_crew(client: WeaveClient) -> None:
    crew = get_crew()
    _ = crew.kickoff()

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    assert len(flattened_calls) == 6

    assert flattened_calls_to_names(flattened_calls) == [
        ("crewai.Crew.kickoff", 0),
        ("crewai.Task.execute_sync", 1),
        ("crewai.Agent.execute_task", 2),
        ("crewai.LLM.call", 3),
        ("litellm.completion", 4),
        ("openai.chat.completions.create", 5),
    ]

    call_0, _ = flattened_calls[0]
    assert call_0.exception is None
    assert call_0.started_at < call_0.ended_at

    inputs = call_0.inputs
    assert inputs["self"]["cache"] == True
    assert len(inputs["self"]["tasks"]) == 1
    assert len(inputs["self"]["agents"]) == 1
    assert inputs["self"]["process"] == "sequential"
    assert inputs["self"]["verbose"] == True
    assert inputs["self"]["memory"] == False

    outputs = call_0.output
    assert (
        "The market landscape for AI-powered healthcare solutions is rapidly evolving, "
        in outputs.raw
    )
    assert outputs._class_name == "CrewOutput"

    summary = call_0.summary
    assert summary["usage"]["gpt-4o-mini-2024-07-18"]["prompt_tokens"] == 187
    assert summary["usage"]["gpt-4o-mini-2024-07-18"]["completion_tokens"] == 666
    assert summary["usage"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 853

    call_1, _ = flattened_calls[1]
    assert call_1.exception is None
    assert call_1.started_at < call_1.ended_at

    inputs = call_1.inputs
    assert inputs["self"]["type"] == "Task"
    assert (
        inputs["self"]["description"]
        == "'Research the current market landscape for AI-powered healthcare solutions'"
    )
    assert (
        inputs["self"]["expected_output"]
        == "'Comprehensive market data including key players, market size, and growth trends'"
    )
    assert inputs["self"]["agent.role"] == "Market Research Specialist"
    assert inputs["agent"]["type"] == "Agent"

    outputs = call_1.output
    assert (
        "The market landscape for AI-powered healthcare solutions is rapidly evolving, "
        in outputs.raw
    )
    assert outputs._class_name == "TaskOutput"

    call_2, _ = flattened_calls[2]
    assert call_2.exception is None
    assert call_2.started_at < call_2.ended_at

    inputs = call_2.inputs
    assert inputs["self"]["type"] == "Agent"
    assert inputs["self"]["role"] == "'Market Research Specialist'"
    assert (
        inputs["self"]["goal"]
        == "'Find comprehensive market data on emerging technologies'"
    )
    assert (
        inputs["self"]["backstory"]
        == "'You are an expert at discovering market trends and gathering data.'"
    )
    assert inputs["self"]["max_iter"] == "25"
    assert inputs["task"]["type"] == "Task"
    assert inputs["context"] == ""
    assert inputs["tools"] == []

    outputs = call_2.output
    assert "In summary, as the AI in healthcare market continues to develop" in outputs

    call_3, _ = flattened_calls[3]
    assert call_3.exception is None
    assert call_3.started_at < call_3.ended_at

    inputs = call_3.inputs
    assert len(inputs["messages"]) == 2
    assert inputs["messages"][0]["role"] == "system"
    assert "You are Market Research Specialist" in inputs["messages"][0]["content"]
    assert inputs["messages"][1]["role"] == "user"

    assert "I now can give a great answer  \nFinal Answer:" in call_3.output

    call_4, _ = flattened_calls[4]
    assert call_4.exception is None
    assert call_4.started_at < call_4.ended_at

    inputs = call_4.inputs
    assert inputs["model"] == "gpt-4o-mini"
    assert inputs["stop"] == ["\nObservation:"]

    outputs = call_4.output
    assert outputs["choices"][0]["message"]["role"] == "assistant"
    assert outputs["usage"]["completion_tokens"] == 666
    assert outputs["usage"]["prompt_tokens"] == 187
    assert outputs["usage"]["total_tokens"] == 853

    call_5, _ = flattened_calls[5]
    assert call_5.exception is None
    assert call_5.started_at < call_5.ended_at

    assert len(call_5.inputs["messages"]) == 2
    assert call_5.inputs["messages"][0]["role"] == "system"
    assert call_5.inputs["messages"][1]["role"] == "user"

    assert (
        "I now can give a great answer  \nFinal Answer:"
        in call_5.output["choices"][0]["message"]["content"]
    )


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_crewai_simple_crew_kickoff_for_each(client: WeaveClient) -> None:
    crew = get_crew()
    _ = crew.kickoff_for_each(inputs=[{"input1": "input1"}, {"input2": "input2"}])

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    assert len(flattened_calls) == 13
    print(flattened_calls_to_names(flattened_calls))

    assert flattened_calls_to_names(flattened_calls) == [
        ("crewai.Crew.kickoff_for_each", 0),
        ("crewai.Crew.kickoff", 1),
        ("crewai.Task.execute_sync", 2),
        ("crewai.Agent.execute_task", 3),
        ("crewai.LLM.call", 4),
        ("litellm.completion", 5),
        ("openai.chat.completions.create", 6),
        ("crewai.Crew.kickoff", 1),
        ("crewai.Task.execute_sync", 2),
        ("crewai.Agent.execute_task", 3),
        ("crewai.LLM.call", 4),
        ("litellm.completion", 5),
        ("openai.chat.completions.create", 6),
    ]

    call_0, _ = flattened_calls[0]
    assert call_0.exception is None
    assert call_0.started_at < call_0.ended_at

    inputs = call_0.inputs
    assert inputs["inputs"] == [{"input1": "input1"}, {"input2": "input2"}]

    outputs = call_0.output
    assert len(outputs) == 2
