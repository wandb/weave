"""
Weave integration for OpenAI Agents.

This module provides integration with the OpenAI Agents library, allowing
agent execution traces to be logged to Weave projects.

Example:
    ```python
    import weave
    from weave.integrations.openai_agents import install

    # Initialize Weave
    weave.init("my-project")

    # Install the Weave tracing processor
    weave_processor = install()

    # Create and run an agent
    agent = Agent.from_type(...)
    result = agent.run("Hello, world!")
    ```
"""

from weave.integrations.openai_agents.openai_agents import (
    WeaveTracingProcessor,
    install,
)

__all__ = ["WeaveTracingProcessor", "install"]
