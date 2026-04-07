"""Convert structured conversation data into span insertable rows.

The structured ingest API accepts conversations described as a sequence of
turns (user messages, assistant responses, tool calls) and produces the same
``genai_spans`` rows that the OTel extraction pipeline would, so all existing
read paths — conversation list, chat view, search — work unchanged.
"""

import datetime
import json
import uuid

from weave.trace_server.agent_schema import (
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.agent_types import (
    AgentConversationIngestReq,
    AgentConversationIngestRes,
    AgentStructuredTurn,
)


def _new_id() -> str:
    """Generate a new random hex ID suitable for trace/span identifiers."""
    return uuid.uuid4().hex


_MODEL_PROVIDER_PREFIXES: dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "chatgpt": "openai",
    "gemini": "google",
    "gemma": "google",
}


def _provider_from_model(model: str) -> str:
    """Infer the LLM provider from a model name prefix."""
    if not model:
        return ""
    m = model.lower()
    for prefix, provider in _MODEL_PROVIDER_PREFIXES.items():
        if m.startswith(prefix):
            return provider
    return ""


def _turn_to_spans(
    turn: AgentStructuredTurn,
    *,
    project_id: str,
    conversation_id: str,
    conversation_name: str,
    provider_name: str,
    fallback_agent_name: str,
    fallback_agent_version: str,
    turn_index: int,
) -> tuple[str, list[AgentSpanCHInsertable]]:
    """Convert a single structured turn into one or more GenAI span rows.

    Returns:
        (trace_id, list_of_spans)
    """
    trace_id = turn.trace_id or _new_id()
    root_span_id = _new_id()
    now = datetime.datetime.now(datetime.timezone.utc)
    base_time = turn.started_at or (now + datetime.timedelta(seconds=turn_index))
    agent_name = turn.agent_name or fallback_agent_name
    agent_version = turn.agent_version or fallback_agent_version

    input_msgs: list[NormalizedMessage] = []
    output_msgs: list[NormalizedMessage] = []
    system_instructions: list[str] = list(turn.system_instructions)

    for msg in turn.messages:
        nm = NormalizedMessage(
            role=msg.role,
            content=msg.content,
            name=getattr(msg, "name", "") or "",
        )
        if msg.role == "user":
            input_msgs.append(nm)
        elif msg.role == "system":
            system_instructions.append(msg.content)
        elif msg.role in {"assistant", "tool"}:
            output_msgs.append(nm)

    end_time = turn.ended_at or (
        base_time + datetime.timedelta(milliseconds=max(1, turn_index))
    )

    effective_provider = provider_name or _provider_from_model(turn.model)

    root_span = AgentSpanCHInsertable(
        project_id=project_id,
        trace_id=trace_id,
        span_id=root_span_id,
        span_name=f"invoke_agent {agent_name}" if agent_name else "invoke_agent",
        span_kind="INTERNAL",
        started_at=base_time,
        ended_at=end_time,
        status_code="OK",
        operation_name="invoke_agent",
        provider_name=effective_provider,
        agent_name=agent_name,
        agent_version=agent_version,
        request_model=turn.model,
        response_model=turn.model,
        input_tokens=turn.input_tokens,
        output_tokens=turn.output_tokens,
        total_tokens=turn.input_tokens + turn.output_tokens,
        reasoning_content=turn.reasoning_content,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        input_messages=input_msgs,
        output_messages=output_msgs,
        system_instructions=system_instructions,
    )

    spans: list[AgentSpanCHInsertable] = [root_span]

    # Create a chat span for the LLM call within this turn.
    # In OTel-instrumented agents, each LLM call is a separate chat span.
    # The structured ingest emulates this so model-level analytics work.
    if turn.model or output_msgs:
        chat_span_id = _new_id()
        chat_start = base_time + datetime.timedelta(microseconds=500)
        chat_end = end_time - datetime.timedelta(microseconds=500)
        chat_span = AgentSpanCHInsertable(
            project_id=project_id,
            trace_id=trace_id,
            span_id=chat_span_id,
            parent_span_id=root_span_id,
            span_name=f"chat {turn.model}" if turn.model else "chat",
            span_kind="CLIENT",
            started_at=chat_start,
            ended_at=chat_end,
            status_code="OK",
            operation_name="chat",
            provider_name=effective_provider,
            agent_name=agent_name,
            agent_version=agent_version,
            request_model=turn.model,
            response_model=turn.model,
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            total_tokens=turn.input_tokens + turn.output_tokens,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            input_messages=input_msgs,
            output_messages=output_msgs,
        )
        spans.append(chat_span)

    for i, tc in enumerate(turn.tool_calls):
        tc_span_id = _new_id()
        tc_start = base_time + datetime.timedelta(milliseconds=i + 1)
        tc_end = tc_start + datetime.timedelta(milliseconds=max(tc.duration_ms, 1))

        tool_span = AgentSpanCHInsertable(
            project_id=project_id,
            trace_id=trace_id,
            span_id=tc_span_id,
            parent_span_id=root_span_id,
            span_name=f"execute_tool {tc.tool_name}",
            span_kind="INTERNAL",
            started_at=tc_start,
            ended_at=tc_end,
            status_code="OK",
            operation_name="execute_tool",
            provider_name=effective_provider,
            agent_name=agent_name,
            agent_version=agent_version,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            tool_name=tc.tool_name,
            tool_call_id=_new_id(),
            tool_call_arguments=tc.arguments
            if isinstance(tc.arguments, str)
            else json.dumps(tc.arguments),
            tool_call_result=tc.result,
        )
        spans.append(tool_span)

    return trace_id, spans


def structured_turns_to_spans(
    req: AgentConversationIngestReq,
) -> tuple[str, list[str], list[AgentSpanCHInsertable]]:
    """Convert a structured conversation ingest request into span rows.

    Args:
        req: The structured conversation ingest request.

    Returns:
        (conversation_id, trace_ids, spans) ready for batch insert.
    """
    conversation_id = req.conversation_id or _new_id()
    all_spans: list[AgentSpanCHInsertable] = []
    trace_ids: list[str] = []

    for idx, turn in enumerate(req.turns):
        trace_id, spans = _turn_to_spans(
            turn,
            project_id=req.project_id,
            conversation_id=conversation_id,
            conversation_name=req.conversation_name,
            provider_name=req.provider_name,
            fallback_agent_name=req.agent_name,
            fallback_agent_version=req.agent_version,
            turn_index=idx,
        )
        trace_ids.append(trace_id)
        all_spans.extend(spans)

    return conversation_id, trace_ids, all_spans


def build_conversation_ingest_response(
    conversation_id: str,
    trace_ids: list[str],
    spans: list[AgentSpanCHInsertable],
) -> AgentConversationIngestRes:
    """Build the API response for a structured conversation ingest."""
    return AgentConversationIngestRes(
        conversation_id=conversation_id,
        trace_ids=trace_ids,
        span_count=len(spans),
    )
