import os
import typing

import pytest
from weave.autopatch import autopatch, autopatch_openai, reset_autopatch
from weave.trace_server import trace_server_interface as tsi
from weave.weave_client import WeaveClient
import weave

from .crewai import crewai_patcher

@pytest.fixture
def only_patch_crewai():
    reset_autopatch()
    crewai_patcher.attempt_patch()
    autopatch_openai()

    try:
        yield  # This is where the test using this fixture will run
    finally:
        autopatch()  # Ensures future tests have the patch applied


class ResearchAgents:
    def __init__(self, search_tool):
        self.search_tool = search_tool


    def get_researcher_agent(self):
        from crewai import Agent

        researcher = Agent(
            role='Senior Researcher',
            goal='Uncover groundbreaking technologies in {topic}',
            verbose=True,
            memory=True,
            backstory=(
                "Driven by curiosity, you're at the forefront of"
                "innovation, eager to explore and share knowledge that could change"
                "the world."
            ),
            tools=[self.search_tool],
            allow_delegation=True
        )

        return researcher
    
    def get_writer_agent(self):
        from crewai import Agent

        writer = Agent(
            role='Writer',
            goal='Narrate compelling tech stories about {topic}',
            verbose=True,
            memory=True,
            backstory=(
                "With a flair for simplifying complex topics, you craft"
                "engaging narratives that captivate and educate, bringing new"
                "discoveries to light in an accessible manner."
            ),
            tools=[self.search_tool],
            allow_delegation=False
        )

        return writer
    

class ResearchTasks:
    def __init__(self, search_tool):
        self.search_tool = search_tool
    
    def get_write_task(self, writer):
        from crewai import Task

        # Writing task with language model configuration
        write_task = Task(
            description=(
                "Compose an insightful article on {topic}."
                "Focus on the latest trends and how it's impacting the industry."
                "This article should be easy to understand, engaging, and positive."
            ),
            expected_output='A 4 paragraph article on {topic} advancements formatted as markdown.',
            tools=[self.search_tool],
            agent=writer,
            async_execution=False,
            output_file='new-blog-post.md'  # Example of output customization
        ) 

        return write_task


def get_crew():
    from crewai import Crew, Process
    from crewai_tools import SerperDevTool

    search_tool = SerperDevTool()

    # Create Agents
    agents = ResearchAgents(search_tool)
    researcher = agents.get_researcher_agent()
    writer = agents.get_writer_agent()

    # Create Tasks
    tasks = ResearchTasks(search_tool)
    write_task = tasks.get_write_task(writer)

    # Forming the tech-focused crew with some enhanced configurations
    crew = Crew(
        agents=[researcher],
        tasks=[write_task],
        process=Process.sequential,  # Optional: Sequential task execution is default
        memory=True,
        cache=True,
        max_rpm=10,
        share_crew=True
    )

    return crew


def filter_body(r: typing.Any) -> typing.Any:
    r.body = ""
    return r


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_crew(client: WeaveClient, only_patch_crewai) -> None:
    openai_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    serper_key = os.environ.get("SERPER_API_KEY", "sk-DUMMY_KEY")

    crew = get_crew()
    _ = crew.kickoff(inputs={'topic': 'AI in astrophysics'})

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    calls = res.calls
    assert len(calls) == 5

    assert calls[0].inputs["messages"][0]["role"] == "user"
    assert calls[0].inputs["stop"] == ["\nObservation"]
    assert calls[0].inputs["temperature"] == 0.7
