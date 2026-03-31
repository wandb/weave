"""Convert structured conversation data into GenAISpanCHInsertable rows.

The structured ingest API accepts conversations described as a sequence of
turns (user messages, assistant responses, tool calls) and produces the same
``genai_spans`` rows that the OTel extraction pipeline would, so all existing
read paths — conversation list, chat view, search — work unchanged.
"""

import datetime
import json
import uuid

from weave.trace_server.genai_schema import (
    GenAISpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.trace_server_interface import (
    GenAIConversationIngestReq,
    GenAIConversationIngestRes,
    GenAIStructuredTurn,
)


def _new_id() -> str:
    """Generate a new random hex ID suitable for trace/span identifiers."""
    return uuid.uuid4().hex


def _turn_to_spans(
    turn: GenAIStructuredTurn,
    *,
    project_id: str,
    conversation_id: str,
    conversation_name: str,
    provider_name: str,
    fallback_agent_name: str,
    turn_index: int,
) -> tuple[str, list[GenAISpanCHInsertable]]:
    """Convert a single structured turn into one or more GenAI span rows.

    Returns:
        (trace_id, list_of_spans)
    """
    trace_id = turn.trace_id or _new_id()
    root_span_id = _new_id()
    now = datetime.datetime.now(datetime.timezone.utc)
    base_time = turn.started_at or (now + datetime.timedelta(seconds=turn_index))
    agent_name = turn.agent_name or fallback_agent_name

    input_msgs: list[NormalizedMessage] = []
    output_msgs: list[NormalizedMessage] = []
    system_instructions: list[str] = list(turn.system_instructions)

    for msg in turn.messages:
        nm = NormalizedMessage(
            role=msg.role,
            content=msg.content,
            tool_call_id=msg.tool_call_id,
            tool_name=msg.tool_name,
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

    root_span = GenAISpanCHInsertable(
        project_id=project_id,
        trace_id=trace_id,
        span_id=root_span_id,
        span_name=f"invoke_agent {agent_name}" if agent_name else "invoke_agent",
        span_kind="INTERNAL",
        started_at=base_time,
        ended_at=end_time,
        status_code="OK",
        operation_name="invoke_agent",
        provider_name=provider_name,
        agent_name=agent_name,
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

    spans: list[GenAISpanCHInsertable] = [root_span]

    # Create a chat span for the LLM call within this turn.
    # In OTel-instrumented agents, each LLM call is a separate chat span.
    # The structured ingest emulates this so model-level analytics work.
    if turn.model or output_msgs:
        chat_span_id = _new_id()
        chat_start = base_time + datetime.timedelta(microseconds=500)
        chat_end = end_time - datetime.timedelta(microseconds=500)
        chat_span = GenAISpanCHInsertable(
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
            provider_name=provider_name,
            agent_name=agent_name,
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

        tool_span = GenAISpanCHInsertable(
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
            provider_name=provider_name,
            agent_name=agent_name,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            tool_name=tc.tool_name,
            tool_call_id=_new_id(),
            tool_call_arguments=tc.arguments if isinstance(tc.arguments, str) else json.dumps(tc.arguments),
            tool_call_result=tc.result,
        )
        spans.append(tool_span)

    return trace_id, spans


def structured_turns_to_spans(
    req: GenAIConversationIngestReq,
) -> tuple[str, list[str], list[GenAISpanCHInsertable]]:
    """Convert a structured conversation ingest request into span rows.

    Args:
        req: The structured conversation ingest request.

    Returns:
        (conversation_id, trace_ids, spans) ready for batch insert.
    """
    conversation_id = req.conversation_id or _new_id()
    all_spans: list[GenAISpanCHInsertable] = []
    trace_ids: list[str] = []

    for idx, turn in enumerate(req.turns):
        trace_id, spans = _turn_to_spans(
            turn,
            project_id=req.project_id,
            conversation_id=conversation_id,
            conversation_name=req.conversation_name,
            provider_name=req.provider_name,
            fallback_agent_name=req.agent_name,
            turn_index=idx,
        )
        trace_ids.append(trace_id)
        all_spans.extend(spans)

    return conversation_id, trace_ids, all_spans


def build_conversation_ingest_response(
    conversation_id: str,
    trace_ids: list[str],
    spans: list[GenAISpanCHInsertable],
) -> GenAIConversationIngestRes:
    """Build the API response for a structured conversation ingest."""
    return GenAIConversationIngestRes(
        conversation_id=conversation_id,
        trace_ids=trace_ids,
        span_count=len(spans),
    )
