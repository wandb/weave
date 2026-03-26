"""Convert ATIF (Agent Trace Interchange Format) trajectories to the native
structured conversation format for ingest into ``genai_spans``.

ATIF is a JSON-based specification (schema v1.4) that logs the complete
interaction history of autonomous LLM agents as a flat sequence of steps.

Mapping summary:
  - ``Trajectory.session_id``  -> ``conversation_id``
  - ``Trajectory.agent.name``  -> ``agent_name``
  - ``Trajectory.agent.model_name`` -> ``model``
  - Steps with ``source="user"`` start a new turn
  - Steps with ``source="agent"`` contribute assistant text, tool calls, metrics
  - Consecutive agent steps between user steps are grouped into a single turn
"""

import json

from weave.trace_server.trace_server_interface import (
    ATIFStep,
    GenAIATIFIngestReq,
    GenAIConversationIngestReq,
    GenAIStructuredMessage,
    GenAIStructuredToolCall,
    GenAIStructuredTurn,
)


def _parse_arguments(args: str | dict) -> str:
    """Normalize tool call arguments to a JSON string."""
    if isinstance(args, dict):
        return json.dumps(args)
    return args


def _step_to_tool_calls(step: ATIFStep) -> list[GenAIStructuredToolCall]:
    """Extract tool calls from an ATIF step, matching observations by ID."""
    if not step.tool_calls:
        return []

    result_map: dict[str, str] = {}
    if step.observation:
        for obs in step.observation.results:
            if obs.source_call_id:
                result_map[obs.source_call_id] = obs.content

    calls: list[GenAIStructuredToolCall] = []
    for tc in step.tool_calls:
        result = result_map.get(tc.tool_call_id, "")
        calls.append(
            GenAIStructuredToolCall(
                tool_name=tc.function_name,
                arguments=_parse_arguments(tc.arguments),
                result=result,
            )
        )
    return calls


def _flush_turn(
    user_messages: list[GenAIStructuredMessage],
    agent_messages: list[GenAIStructuredMessage],
    tool_calls: list[GenAIStructuredToolCall],
    input_tokens: int,
    output_tokens: int,
    reasoning_content: str,
    model: str,
    agent_name: str,
    system_instructions: list[str],
) -> GenAIStructuredTurn:
    """Build a GenAIStructuredTurn from accumulated step data."""
    messages = list(user_messages) + list(agent_messages)
    return GenAIStructuredTurn(
        messages=messages,
        tool_calls=tool_calls,
        agent_name=agent_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_content=reasoning_content,
        system_instructions=system_instructions,
    )


def atif_to_conversation_req(req: GenAIATIFIngestReq) -> GenAIConversationIngestReq:
    """Convert an ATIF trajectory into a ``GenAIConversationIngestReq``.

    Args:
        req: The ATIF ingest request containing the trajectory and metadata.

    Returns:
        A native structured conversation ingest request.
    """
    traj = req.trajectory
    model = traj.agent.model_name
    agent_name = traj.agent.name

    turns: list[GenAIStructuredTurn] = []

    user_msgs: list[GenAIStructuredMessage] = []
    agent_msgs: list[GenAIStructuredMessage] = []
    tool_calls: list[GenAIStructuredToolCall] = []
    input_tokens = 0
    output_tokens = 0
    reasoning_content = ""
    system_instructions: list[str] = []

    has_content = False

    for step in traj.steps:
        if step.source == "system":
            if step.message:
                system_instructions.append(step.message)
            continue

        if step.source == "user":
            # Flush previous turn if there's accumulated content
            if has_content:
                turns.append(
                    _flush_turn(
                        user_msgs, agent_msgs, tool_calls,
                        input_tokens, output_tokens, reasoning_content,
                        model, agent_name, system_instructions,
                    )
                )
                user_msgs = []
                agent_msgs = []
                tool_calls = []
                input_tokens = 0
                output_tokens = 0
                reasoning_content = ""
                system_instructions = []

            if step.message:
                user_msgs.append(
                    GenAIStructuredMessage(role="user", content=step.message)
                )
            has_content = True
            continue

        # source == "agent"
        if step.message:
            agent_msgs.append(
                GenAIStructuredMessage(role="assistant", content=step.message)
            )

        if step.reasoning_content and not reasoning_content:
            reasoning_content = step.reasoning_content

        tool_calls.extend(_step_to_tool_calls(step))

        if step.metrics:
            input_tokens += step.metrics.prompt_tokens
            output_tokens += step.metrics.completion_tokens

        has_content = True

    # Flush the last turn
    if has_content:
        turns.append(
            _flush_turn(
                user_msgs, agent_msgs, tool_calls,
                input_tokens, output_tokens, reasoning_content,
                model, agent_name, system_instructions,
            )
        )

    return GenAIConversationIngestReq(
        project_id=req.project_id,
        conversation_id=traj.session_id,
        conversation_name=req.conversation_name,
        provider_name=req.provider_name,
        agent_name=agent_name,
        turns=turns,
    )
