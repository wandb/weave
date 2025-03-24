# CrewAI

TODO: add correct colab link
<a target="_blank" href="https://colab.research.google.com/github/wandb/examples/blob/master/weave/docs/quickstart_crewai.ipynb">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

CrewAI is a lean, lightning-fast Python framework built entirely from scratch—completely independent of LangChain or other agent frameworks. CrewAI empowers developers with both high-level simplicity ([Crews](https://docs.crewai.com/guides/crews/first-crew)) and precise low-level control ([Flows](https://docs.crewai.com/guides/flows/first-flow)), ideal for creating autonomous AI agents tailored to any scenario. Learn more about [CrewAI here](https://docs.crewai.com/introduction).


When working with AI agents, debugging and monitoring their interactions is crucial. CrewAI applications often consist of multiple agents working together, making it essential to understand how they collaborate and communicate. Weave simplifies this process by automatically capturing traces for your CrewAI applications, enabling you to monitor and analyze your agents' performance and interactions.

The integration supports both Crews and Flows.

## Getting Started with Crew

To get started, simply call `weave.init()` at the beginning of your script. The argument in weave.init() is a project name where the traces will be logged.

```python
import weave
from crewai import Agent, Task, Crew, LLM, Process

# Initialize Weave with your project name
# highlight-next-line
weave.init("crewai_demo")

# Create an LLM with a temperature of 0 to ensure deterministic outputs
llm = LLM(model="gpt-4o-mini", temperature=0)

# Create agents
researcher = Agent(
    role='Research Analyst',
    goal='Find and analyze the best investment opportunities',
    backstory='Expert in financial analysis and market research',
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

writer = Agent(
    role='Report Writer',
    goal='Write clear and concise investment reports',
    backstory='Experienced in creating detailed financial reports',
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

# Create tasks
research_task = Task(
    description='Deep research on the {topic}',
    expected_output='Comprehensive market data including key players, market size, and growth trends.',
    agent=researcher
)

writing_task = Task(
    description='Write a detailed report based on the research',
    expected_output='The report should be easy to read and understand. Use bullet points where applicable.',
    agent=writer
)

# Create a crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    verbose=True,
    process=Process.sequential,
)

# Run the crew
result = crew.kickoff(inputs={"topic": "AI in material science"})
print(result)
```

Weave will track and log all calls made through the CrewAI library, including agent interactions, task executions, and LLM calls. You can view the traces in the Weave web interface.

[![crew_trace.png](imgs/crewai/crew.png)](https://wandb.ai/ayut/crewai_demo/weave/traces?filter=%7B%22opVersionRefs%22%3A%5B%22weave%3A%2F%2F%2Fayut%2Fcrewai_demo%2Fop%2Fcrewai.Crew.kickoff%3A*%22%5D%7D&peekPath=%2Fayut%2Fcrewai_demo%2Fcalls%2F0195c7ac-bd52-7390-95a7-309370e9e058%3FhideTraceTree%3D0&cols=%7B%22wb_run_id%22%3Afalse%2C%22attributes.weave.client_version%22%3Afalse%2C%22attributes.weave.os_name%22%3Afalse%2C%22attributes.weave.os_release%22%3Afalse%2C%22attributes.weave.os_version%22%3Afalse%2C%22attributes.weave.source%22%3Afalse%2C%22attributes.weave.sys_version%22%3Afalse%7D)

:::note
CrewAI provides several methods for better control over the kickoff process: `kickoff()`, `kickoff_for_each()`, `kickoff_async()`, and `kickoff_for_each_async()`. The integration supports logging traces from all these methods.
:::

