import asyncio

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


def get_flow_with_router_or():
    from crewai.flow.flow import Flow, listen, router, start, or_, and_
    from pydantic import BaseModel

    # Define structured state
    class SupportTicketState(BaseModel):
        ticket_id: str = ""
        customer_name: str = ""
        issue_description: str = ""
        category: str = ""
        priority: str = "medium"
        resolution: str = ""
        satisfaction_score: int = 0

    class CustomerSupportFlow(Flow[SupportTicketState]):
        @start()
        def receive_ticket(self):
            # In a real app, this might come from an API
            self.state.ticket_id = "TKT-12345"
            self.state.customer_name = "Alex Johnson"
            self.state.issue_description = "Unable to access premium features after payment"
            return "Ticket received"

        @listen(receive_ticket)
        def categorize_ticket(self, _):
            # Use a direct LLM call for categorization
            from crewai import LLM
            import os
            api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
            print(api_key)
            llm = LLM(model="openai/gpt-4o-mini", api_key=api_key)

            prompt = f"""
            Categorize the following customer support issue into one of these categories:
            - Billing
            - Account Access
            - Technical Issue
            - Feature Request
            - Other

            Issue: {self.state.issue_description}

            Return only the category name.
            """

            self.state.category = llm.call(prompt).strip()
            return self.state.category

        @router(categorize_ticket)
        def route_by_category(self, category):
            # Route to different handlers based on category
            return category.lower().replace(" ", "_")

        @listen("billing")
        def handle_billing_issue(self):
            # Handle billing-specific logic
            self.state.priority = "high"
            # More billing-specific processing...
            return "Billing issue handled"

        @listen("account_access")
        def handle_access_issue(self):
            # Handle access-specific logic
            self.state.priority = "high"
            # More access-specific processing...
            return "Access issue handled"
        
        @listen(or_("billing", "account_access"))
        def resolve_ticket(self, resolution_info):
            # Final resolution step
            self.state.resolution = f"Issue resolved: {resolution_info}"
            return self.state.resolution

    support_flow = CustomerSupportFlow()
    return support_flow


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

    # Rest is same as test_crewai_simple_crew


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
async def test_crewai_simple_crew_kickoff_async(client: WeaveClient) -> None:
    crew = get_crew()

    result = await crew.kickoff_async()

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    assert len(flattened_calls) == 7

    assert flattened_calls_to_names(flattened_calls) == [
        ("crewai.Crew.kickoff_async", 0),
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

    # Rest is same as test_crewai_simple_crew


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
async def test_crewai_simple_crew_kickoff_for_each_async(client: WeaveClient) -> None:
    crew = get_crew()

    result = await crew.kickoff_for_each_async(
        inputs=[{"input1": "input1"}, {"input2": "input2"}]
    )

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)
    print(flattened_calls_to_names(flattened_calls))

    assert len(flattened_calls) == 19

    assert flattened_calls_to_names(flattened_calls) == [
        ("crewai.Crew.kickoff_for_each_async", 0),
        ("crewai.Crew.kickoff_async", 1),
        ("crewai.Crew.kickoff", 2),
        ("crewai.Task.execute_sync", 3),
        ("crewai.Agent.execute_task", 4),
        ("crewai.LLM.call", 5),
        ("litellm.completion", 6),
        ("openai.chat.completions.create", 7),
        ("crewai.Agent.execute_task", 5),
        ("crewai.LLM.call", 6),
        ("litellm.completion", 7),
        ("openai.chat.completions.create", 8),
        ("crewai.Crew.kickoff_async", 1),
        ("crewai.Crew.kickoff", 2),
        ("crewai.Task.execute_sync", 3),
        ("crewai.Agent.execute_task", 4),
        ("crewai.LLM.call", 5),
        ("litellm.completion", 6),
        ("openai.chat.completions.create", 7),
    ]

    call_0, _ = flattened_calls[0]
    assert call_0.exception is None
    assert call_0.started_at < call_0.ended_at

    inputs = call_0.inputs
    assert inputs["inputs"] == [{"input1": "input1"}, {"input2": "input2"}]

    outputs = call_0.output
    assert len(outputs) == 2


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_simple_flow(client: WeaveClient) -> None:
    flow = get_flow_with_router_or()
    result = flow.kickoff()

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)
    
    assert len(flattened_calls) == 9
    assert flattened_calls_to_names(flattened_calls) == [('crewai.Flow.kickoff', 0), ('crewai.Flow.kickoff_async', 1), ('crewai.flow.flow.start', 2), ('crewai.flow.flow.listen', 2), ('crewai.LLM.call', 3), ('litellm.completion', 4), ('openai.chat.completions.create', 5), ('crewai.flow.flow.router', 2), ('crewai.flow.flow.listen', 2)]

    call_0, _ = flattened_calls[0]
    assert call_0.exception is None
    assert call_0.started_at < call_0.ended_at

    inputs = call_0.inputs
    # assert inputs["self"]["flow_id"] == "27d6c0f9-834f-4b4e-89e7-162469b8b3c9"
    assert inputs["self"]["state"]["priority"] == "medium"
    assert inputs["self"]["state"]["resolution"] == ""
    assert inputs["self"]["state"]["satisfaction_score"] == 0
    assert inputs["self"]["state"]["ticket_id"] == ""
    assert call_0.output == "Billing issue handled"

    # kickoff_async is same as kickoff

    call_1, _ = flattened_calls[1]
    assert call_1.exception is None
    assert call_1.started_at < call_1.ended_at

    inputs = call_1.inputs
    outputs = call_1.output
    print(inputs)
    print(outputs)
    

