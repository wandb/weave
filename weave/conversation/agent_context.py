"""Ambient agent-name override for OTel auto-instrumentation.

Auto-instrumentation integrations (``claude_agent_sdk``, ``openai_agents``, …)
each create their own ``invoke_agent`` OTel span and stamp ``gen_ai.agent.name``
on it. Some SDKs expose a native agent name (OpenAI Agents); others don't
(``claude_agent_sdk`` falls back to ``"claude_agent_sdk"``). ``agent_name_override``
lets a user name those auto-created spans for a block of work, regardless of
which integration produced them.

This is deliberately distinct from ``weave.conversation.start_turn(agent_name=...)``,
which *creates* a manual ``invoke_agent`` span. The override here only relabels a
span created elsewhere — it never creates a span of its own.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

# ``None`` means "no override" — integrations fall back to their native/default
# name. An active override is always a validated non-empty string.
_current_agent_name: ContextVar[str | None] = ContextVar(
    "weave_agent_name_override", default=None
)


@contextmanager
def agent_name_override(agent_name: str) -> Iterator[None]:
    """Name the OTel ``invoke_agent`` spans emitted within this block.

    Overrides the ``gen_ai.agent.name`` (and span name) that auto-instrumentation
    integrations stamp on their ``invoke_agent`` span::

        import weave
        from weave.conversation import agent_name_override

        weave.init("my-project")

        with agent_name_override("research_agent"):
            async for message in query(prompt="...", options=options):
                ...

    The name is resolved per span at creation, so concurrent async runs may each
    set their own name. Nested blocks restore the outer name on exit. Unlike
    ``start_turn(agent_name=...)`` this creates no span itself — it only relabels
    spans produced by the integration in scope.
    """
    if not isinstance(agent_name, str) or not agent_name.strip():
        raise ValueError("agent_name must be a non-empty string")
    token = _current_agent_name.set(agent_name)
    try:
        yield
    finally:
        _current_agent_name.reset(token)


def resolve_agent_name(default: str) -> str:
    """Return the ambient override if one is set, else ``default``.

    Precedence at an auto-instrumentation call site: explicit override >
    integration-native name (passed as ``default``) > integration default.
    """
    override = _current_agent_name.get()
    return override if override is not None else default
