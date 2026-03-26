"""Convert OpenHands event streams to the native structured conversation
format for ingest into ``genai_spans``.

OpenHands uses an immutable, typed event framework where events are appended
to a log. A logical "turn" starts with a user ``MessageEvent`` and ends when
the next user message arrives (or the stream ends).

Mapping summary:
  - ``session_id``                    -> ``conversation_id``
  - ``MessageEvent(source=user)``     -> starts a new turn with user message
  - ``ActionEvent(source=agent)``     -> tool call within current turn
  - ``ObservationEvent``              -> tool result, matched by ``tool_call_id``
  - ``MessageEvent(source=agent)``    -> assistant response in current turn
  - ``SystemPromptEvent``             -> ``system_instructions``
"""

import json

from weave.trace_server.trace_server_interface import (
    GenAIConversationIngestReq,
    GenAIOpenHandsIngestReq,
    GenAIStructuredMessage,
    GenAIStructuredToolCall,
    GenAIStructuredTurn,
    OpenHandsEvent,
)


def _parse_arguments(args: str | dict) -> str:
    """Normalize tool call arguments to a JSON string."""
    if isinstance(args, dict):
        return json.dumps(args)
    return args


def _flush_turn(
    user_messages: list[GenAIStructuredMessage],
    agent_messages: list[GenAIStructuredMessage],
    pending_tool_calls: dict[str, GenAIStructuredToolCall],
    completed_tool_calls: list[GenAIStructuredToolCall],
    system_instructions: list[str],
    agent_name: str,
) -> GenAIStructuredTurn:
    """Build a turn from accumulated events."""
    all_tool_calls = list(completed_tool_calls) + list(pending_tool_calls.values())
    messages = list(user_messages) + list(agent_messages)

    return GenAIStructuredTurn(
        messages=messages,
        tool_calls=all_tool_calls,
        agent_name=agent_name,
        system_instructions=system_instructions,
    )


def _process_action(
    event: OpenHandsEvent,
    pending_tool_calls: dict[str, GenAIStructuredToolCall],
) -> None:
    """Register a tool call action, to be resolved later by an observation."""
    tc = GenAIStructuredToolCall(
        tool_name=event.tool_name,
        arguments=_parse_arguments(event.arguments),
    )
    key = event.tool_call_id or str(event.id)
    pending_tool_calls[key] = tc


def _process_observation(
    event: OpenHandsEvent,
    pending_tool_calls: dict[str, GenAIStructuredToolCall],
    completed_tool_calls: list[GenAIStructuredToolCall],
) -> None:
    """Match an observation to its action and move it to completed."""
    key = event.tool_call_id or str(event.action_id)
    tc = pending_tool_calls.pop(key, None)
    if tc is not None:
        tc.result = event.observation_content or event.content
        completed_tool_calls.append(tc)
    else:
        completed_tool_calls.append(
            GenAIStructuredToolCall(
                tool_name=event.tool_name or "unknown",
                result=event.observation_content or event.content,
            )
        )


def openhands_to_conversation_req(
    req: GenAIOpenHandsIngestReq,
) -> GenAIConversationIngestReq:
    """Convert an OpenHands event stream into a ``GenAIConversationIngestReq``.

    Args:
        req: The OpenHands ingest request containing the event list.

    Returns:
        A native structured conversation ingest request.
    """
    agent_name = req.agent_name
    turns: list[GenAIStructuredTurn] = []

    user_msgs: list[GenAIStructuredMessage] = []
    agent_msgs: list[GenAIStructuredMessage] = []
    pending_tool_calls: dict[str, GenAIStructuredToolCall] = {}
    completed_tool_calls: list[GenAIStructuredToolCall] = []
    system_instructions: list[str] = []
    has_content = False

    for event in req.events:
        if event.event_type == "system_prompt":
            if event.system_prompt:
                system_instructions.append(event.system_prompt)
            continue

        if event.event_type == "message" and event.source == "user":
            # Flush previous turn
            if has_content:
                turns.append(
                    _flush_turn(
                        user_msgs, agent_msgs, pending_tool_calls,
                        completed_tool_calls, system_instructions, agent_name,
                    )
                )
                user_msgs = []
                agent_msgs = []
                pending_tool_calls = {}
                completed_tool_calls = []
                system_instructions = []

            if event.content:
                user_msgs.append(
                    GenAIStructuredMessage(role="user", content=event.content)
                )
            has_content = True
            continue

        if event.event_type == "message" and event.source in {"agent", "environment"}:
            if event.content:
                agent_msgs.append(
                    GenAIStructuredMessage(role="assistant", content=event.content)
                )
            has_content = True
            continue

        if event.event_type == "action":
            _process_action(event, pending_tool_calls)
            has_content = True
            continue

        if event.event_type == "observation":
            _process_observation(event, pending_tool_calls, completed_tool_calls)
            has_content = True
            continue

    # Flush the last turn
    if has_content:
        turns.append(
            _flush_turn(
                user_msgs, agent_msgs, pending_tool_calls,
                completed_tool_calls, system_instructions, agent_name,
            )
        )

    return GenAIConversationIngestReq(
        project_id=req.project_id,
        conversation_id=req.session_id,
        conversation_name=req.conversation_name,
        provider_name=req.provider_name,
        agent_name=agent_name,
        turns=turns,
    )
