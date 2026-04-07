"""Weave Agents SDK — trace, instrument, and analyze agent systems.

Two SDK tiers:

Tier 1 — Auto-instrumentations (patch known frameworks)::

    from weave.agents import setup_tracing
    from weave.agents.instrumentors.openai_agents import instrument
    provider = setup_tracing(service_name="my-agent", project="my-project")
    instrument(provider, agents=[agent], conversation="session-1")

Tier 2 — Context managers (custom code, evals, agent loops)::

    import weave
    with weave.agent("my-agent", version="1.0") as a:
        with weave.chat(model="gpt-4") as c:
            c.input_messages([...])
            response = my_llm_call(...)
            c.output_message(response)

Span enrichment::

    from weave.agents import log_content, use_artifact, use_object
"""

from typing import Any

# Tier 1: OTel setup and instrumentors
from weave.otel import (
    log_content,
    setup_tracing,
    use_artifact,
    use_object,
)

# Tier 2: Context managers (emit OTel under the hood)
from weave.otel.context_managers import agent, chat, tool


# Lazy re-exports for instrumentor shortcuts and processors
def __getattr__(name: str) -> Any:
    """Lazy re-export from weave.otel."""
    import weave.otel as _otel

    if name in {
        "SystemPromptInjector",
        "ConversationIdInjector",
        "ToolDefinitionsInjector",
        "LiveSpanProcessor",
        "instrument_openai_agents",
        "instrument_google_adk",
        "instrument_claude_agent_sdk",
    }:
        return getattr(_otel, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def instrument(
    provider: Any, agents: Any = None, conversation: Any = None, **kwargs: Any
) -> Any:
    """Auto-instrument agent frameworks (Tier 1).

    Args:
        provider: The OTel TracerProvider to use.
        agents: Optional list of agent objects to discover instructions/tools from.
        conversation: Optional conversation ID to link spans to.
        **kwargs: Additional arguments passed to the underlying instrumentor.
    """
    from weave.otel.instrumentors.openai_agents import instrument as _inst

    return _inst(provider, agents=agents, conversation=conversation, **kwargs)


__all__ = [
    "agent",
    "chat",
    "instrument",
    "log_content",
    "setup_tracing",
    "tool",
    "use_artifact",
    "use_object",
]
