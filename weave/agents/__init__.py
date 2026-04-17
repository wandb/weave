"""Weave Agents SDK — trace, instrument, and analyze agent systems.

Setup::

    from weave.agents import setup_tracing, instrument

Instrumentors::

    from weave.agents.instrumentors import openai_agents, google_adk, claude

Span enrichment::

    from weave.agents import log_content, use_artifact, use_object
"""

from weave.agents.conversation import conversation
from weave.otel import (
    log_content,
    use_artifact,
    use_object,
)
from weave.otel import setup_tracing
from weave.otel import (
    instrument_openai_agents,
    instrument_google_adk,
    instrument_claude_agent_sdk,
)

# Lazy re-exports for OTel processors (avoid importing OTel at module load)
def __getattr__(name):
    """Lazy re-export OTel processors from weave.otel."""
    import weave.otel as _otel

    if name in {"SystemPromptInjector", "ConversationIdInjector",
                "ToolDefinitionsInjector", "LiveSpanProcessor"}:
        return getattr(_otel, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def instrument(provider, agents=None, conversation=None, **kwargs):
    """Auto-instrument agent frameworks.

    Args:
        provider: The OTel TracerProvider to use.
        agents: Optional list of agent objects to discover instructions/tools from.
        conversation: Optional conversation ID to link spans to.
        **kwargs: Additional arguments passed to the underlying instrumentor.

    Returns:
        The result of the instrumentation call.
    """
    from weave.otel.instrumentors.openai_agents import instrument as _inst

    return _inst(provider, agents=agents, conversation=conversation, **kwargs)


__all__ = [
    "conversation",
    "setup_tracing",
    "instrument",
    "log_content",
    "use_artifact",
    "use_object",
    "instrument_openai_agents",
    "instrument_google_adk",
    "instrument_claude_agent_sdk",
]
