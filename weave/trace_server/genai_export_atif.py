"""Export GenAI chat projection messages as ATIF (Agent Trace Interchange Format).

Converts ``GenAIChatMessage`` rows produced from the ``genai_spans`` chat view
into an ``ATIFTrajectory`` (schema v1.5). This is the inverse direction of
``genai_ingest_atif`` — useful for exporting a stored conversation for
evaluation pipelines or external tools that consume ATIF.

Examples:
    Minimal user and agent turns:

    >>> from weave.trace_server.trace_server_interface import GenAIChatMessage
    >>> msgs = [
    ...     GenAIChatMessage(type="user_message", text="Hello"),
    ...     GenAIChatMessage(
    ...         type="agent_message", text="Hi!", input_tokens=1, output_tokens=2
    ...     ),
    ... ]
    >>> traj = chat_messages_to_atif(msgs, agent_name="bot", model="gpt-4")
    >>> traj.schema_version
    'ATIF-v1.5'
    >>> traj.agent.name
    'bot'
    >>> len(traj.steps)
    2
"""

from __future__ import annotations

import json

from weave.trace_server.trace_server_interface import (
    ATIFAgent,
    ATIFMetrics,
    ATIFObservation,
    ATIFObservationResult,
    ATIFStep,
    ATIFToolCall,
    ATIFTrajectory,
    GenAIChatMessage,
)


def _tool_arguments_for_atif(raw: str) -> str | dict:
    """If ``raw`` is a JSON object, return a dict; otherwise return ``raw``."""
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return raw


def chat_messages_to_atif(
    messages: list[GenAIChatMessage],
    agent_name: str = "",
    model: str = "",
    conversation_id: str = "",
) -> ATIFTrajectory:
    """Build an ATIF trajectory from a GenAI chat projection message list.

    Maps chat message types to ATIF steps:

    - ``user_message`` → ``source="user"``, ``message=text``
    - ``agent_message`` → ``source="agent"``, ``message=text``, optional
      ``ATIFMetrics`` from token fields
    - ``tool_call`` → ``source="agent"`` with ``tool_calls`` and ``observation``
      (``tool_arguments`` is passed through; JSON objects decode to ``dict``)
    - ``agent_start`` → ``source="system"`` with ``message=system_instructions``
      (only when ``system_instructions`` is non-empty)
    - ``agent_handoff`` → ``source="agent"``, ``message=text``
    - ``context_compacted`` → omitted (not represented in ATIF)

    Step indices are dense ``step_id`` values starting at 0.

    Args:
        messages: Ordered ``GenAIChatMessage`` list from the chat view.
        agent_name: Stored on ``ATIFTrajectory.agent.name``.
        model: Stored on ``ATIFTrajectory.agent.model_name``.
        conversation_id: Stored as ``ATIFTrajectory.session_id``.

    Returns:
        An ``ATIFTrajectory`` with ``schema_version="ATIF-v1.5"``.

    Examples:
        Tool call with JSON arguments and result:

        >>> from weave.trace_server.trace_server_interface import GenAIChatMessage
        >>> msgs = [
        ...     GenAIChatMessage(
        ...         type="tool_call",
        ...         tool_name="search",
        ...         tool_arguments='{"q": "x"}',
        ...         tool_result="ok",
        ...     ),
        ... ]
        >>> traj = chat_messages_to_atif(msgs)
        >>> traj.steps[0].tool_calls[0].function_name
        'search'
        >>> traj.steps[0].tool_calls[0].arguments
        {'q': 'x'}
        >>> traj.steps[0].observation.results[0].content
        'ok'
    """
    steps: list[ATIFStep] = []
    step_id = 0

    for msg in messages:
        if msg.type == "context_compacted":
            continue
        if msg.type == "user_message":
            steps.append(
                ATIFStep(
                    step_id=step_id,
                    source="user",
                    message=msg.text,
                )
            )
            step_id += 1
        elif msg.type == "agent_message":
            metrics = None
            if msg.input_tokens or msg.output_tokens:
                metrics = ATIFMetrics(
                    prompt_tokens=msg.input_tokens,
                    completion_tokens=msg.output_tokens,
                )
            steps.append(
                ATIFStep(
                    step_id=step_id,
                    source="agent",
                    message=msg.text,
                    metrics=metrics,
                )
            )
            step_id += 1
        elif msg.type == "tool_call":
            tool_call = ATIFToolCall(
                function_name=msg.tool_name,
                arguments=_tool_arguments_for_atif(msg.tool_arguments),
            )
            observation = ATIFObservation(
                results=[ATIFObservationResult(content=msg.tool_result)]
            )
            steps.append(
                ATIFStep(
                    step_id=step_id,
                    source="agent",
                    tool_calls=[tool_call],
                    observation=observation,
                )
            )
            step_id += 1
        elif msg.type == "agent_start":
            if msg.system_instructions:
                steps.append(
                    ATIFStep(
                        step_id=step_id,
                        source="system",
                        message=msg.system_instructions,
                    )
                )
                step_id += 1
        elif msg.type == "agent_handoff":
            steps.append(
                ATIFStep(
                    step_id=step_id,
                    source="agent",
                    message=msg.text,
                )
            )
            step_id += 1

    return ATIFTrajectory(
        schema_version="ATIF-v1.5",
        session_id=conversation_id,
        agent=ATIFAgent(name=agent_name, model_name=model),
        steps=steps,
    )
