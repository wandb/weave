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
    GenAIStructuredStep,
    GenAIStructuredToolCall,
    GenAIStructuredTurn,
)


def _new_id() -> str:
    """Generate a new random hex ID suitable for trace/span identifiers."""
    return uuid.uuid4().hex


def _to_normalized(msgs: list) -> list[NormalizedMessage]:
    """Convert GenAIStructuredMessage list to NormalizedMessage list."""
    return [
        NormalizedMessage(
            role=m.role,
            content=m.content,
            tool_call_id=m.tool_call_id,
            tool_name=m.tool_name,
        )
        for m in msgs
    ]


def _tool_call_spans(
    tool_calls: list[GenAIStructuredToolCall],
    *,
    project_id: str,
    trace_id: str,
    parent_span_id: str,
    conversation_id: str,
    conversation_name: str,
    provider_name: str,
    agent_name: str,
    base_time: datetime.datetime,
) -> list[GenAISpanCHInsertable]:
    """Create execute_tool spans for a list of tool calls."""
    spans: list[GenAISpanCHInsertable] = []
    for i, tc in enumerate(tool_calls):
        tc_span_id = _new_id()
        tc_start = base_time + datetime.timedelta(milliseconds=i + 1)
        tc_end = tc_start + datetime.timedelta(milliseconds=max(tc.duration_ms, 1))

        spans.append(
            GenAISpanCHInsertable(
                project_id=project_id,
                trace_id=trace_id,
                span_id=tc_span_id,
                parent_span_id=parent_span_id,
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
                tool_call_arguments=(
                    tc.arguments
                    if isinstance(tc.arguments, str)
                    else json.dumps(tc.arguments)
                ),
                tool_call_result=tc.result,
            )
        )
    return spans


def _step_to_spans(
    step: GenAIStructuredStep,
    *,
    project_id: str,
    trace_id: str,
    parent_span_id: str,
    conversation_id: str,
    conversation_name: str,
    fallback_provider: str,
    agent_name: str,
    step_index: int,
    turn_base_time: datetime.datetime,
    turn_end_time: datetime.datetime,
) -> list[GenAISpanCHInsertable]:
    """Convert one step (LLM call) into a chat span + tool call children."""
    provider = step.provider_name or fallback_provider
    model = step.model

    chat_start = step.started_at or (
        turn_base_time + datetime.timedelta(milliseconds=step_index * 100 + 1)
    )
    chat_end = step.ended_at or (
        turn_end_time - datetime.timedelta(milliseconds=(step_index + 1))
    )

    input_msgs = _to_normalized(step.input_messages)
    output_msgs = _to_normalized(step.output_messages)

    chat_span_id = _new_id()
    chat_span = GenAISpanCHInsertable(
        project_id=project_id,
        trace_id=trace_id,
        span_id=chat_span_id,
        parent_span_id=parent_span_id,
        span_name=f"chat {model}" if model else "chat",
        span_kind="CLIENT",
        started_at=chat_start,
        ended_at=chat_end,
        status_code="OK",
        operation_name="chat",
        provider_name=provider,
        agent_name=agent_name,
        request_model=model,
        response_model=model,
        input_tokens=step.input_tokens,
        output_tokens=step.output_tokens,
        total_tokens=step.input_tokens + step.output_tokens,
        reasoning_content=step.reasoning_content,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        input_messages=input_msgs,
        output_messages=output_msgs,
        system_instructions=list(step.system_instructions),
        finish_reasons=list(step.finish_reasons),
    )

    spans: list[GenAISpanCHInsertable] = [chat_span]

    # Tool calls within this step are children of the chat span.
    spans.extend(
        _tool_call_spans(
            step.tool_calls,
            project_id=project_id,
            trace_id=trace_id,
            parent_span_id=chat_span_id,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            provider_name=provider,
            agent_name=agent_name,
            base_time=chat_start,
        )
    )

    return spans


def _turn_to_spans(
    turn: GenAIStructuredTurn,
    *,
    project_id: str,
    conversation_id: str,
    conversation_name: str,
    provider_name: str,
    fallback_agent_name: str,
    turn_index: int,
) -> tuple[str, str, list[GenAISpanCHInsertable]]:
    """Convert a single structured turn into one or more GenAI span rows.

    When ``turn.parent_span_id`` is set (along with ``turn.trace_id``),
    the root ``invoke_agent`` span is skipped — only child spans (steps,
    tool calls) are created under the provided parent.  This enables
    incremental per-step flushing without duplicating the root span.

    Returns:
        (trace_id, root_span_id, list_of_spans)
    """
    trace_id = turn.trace_id or _new_id()
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

    # Incremental mode: parent_span_id is set — skip root span creation,
    # only produce child spans under the existing parent.
    if turn.parent_span_id and turn.trace_id:
        root_span_id = turn.parent_span_id
        spans: list[GenAISpanCHInsertable] = []
    else:
        # Full mode: create the root invoke_agent span.
        root_span_id = _new_id()

        if turn.steps:
            total_input = sum(s.input_tokens for s in turn.steps)
            total_output = sum(s.output_tokens for s in turn.steps)
            root_model = turn.model or (turn.steps[0].model if turn.steps else "")
        else:
            total_input = turn.input_tokens
            total_output = turn.output_tokens
            root_model = turn.model

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
            request_model=root_model,
            response_model=root_model,
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_input + total_output,
            reasoning_content=turn.reasoning_content,
            conversation_id=conversation_id,
            conversation_name=conversation_name,
            input_messages=input_msgs,
            output_messages=output_msgs,
            system_instructions=system_instructions,
        )
        spans = [root_span]

    if turn.steps:
        # Step-level mode: each step becomes a chat span with its own tools.
        for i, step in enumerate(turn.steps):
            spans.extend(
                _step_to_spans(
                    step,
                    project_id=project_id,
                    trace_id=trace_id,
                    parent_span_id=root_span_id,
                    conversation_id=conversation_id,
                    conversation_name=conversation_name,
                    fallback_provider=provider_name,
                    agent_name=agent_name,
                    step_index=i,
                    turn_base_time=base_time,
                    turn_end_time=end_time,
                )
            )
    else:
        # Flat mode (backward compatible): single chat span + flat tool calls.
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

        spans.extend(
            _tool_call_spans(
                turn.tool_calls,
                project_id=project_id,
                trace_id=trace_id,
                parent_span_id=root_span_id,
                conversation_id=conversation_id,
                conversation_name=conversation_name,
                provider_name=provider_name,
                agent_name=agent_name,
                base_time=base_time,
            )
        )

    return trace_id, root_span_id, spans


def structured_turns_to_spans(
    req: GenAIConversationIngestReq,
) -> tuple[str, list[str], list[str], list[GenAISpanCHInsertable]]:
    """Convert a structured conversation ingest request into span rows.

    Args:
        req: The structured conversation ingest request.

    Returns:
        (conversation_id, trace_ids, root_span_ids, spans) ready for batch insert.
    """
    conversation_id = req.conversation_id or _new_id()
    all_spans: list[GenAISpanCHInsertable] = []
    trace_ids: list[str] = []
    root_span_ids: list[str] = []

    for idx, turn in enumerate(req.turns):
        trace_id, root_span_id, spans = _turn_to_spans(
            turn,
            project_id=req.project_id,
            conversation_id=conversation_id,
            conversation_name=req.conversation_name,
            provider_name=req.provider_name,
            fallback_agent_name=req.agent_name,
            turn_index=idx,
        )
        trace_ids.append(trace_id)
        root_span_ids.append(root_span_id)
        all_spans.extend(spans)

    return conversation_id, trace_ids, root_span_ids, all_spans


def build_conversation_ingest_response(
    conversation_id: str,
    trace_ids: list[str],
    root_span_ids: list[str],
    spans: list[GenAISpanCHInsertable],
) -> GenAIConversationIngestRes:
    """Build the API response for a structured conversation ingest."""
    return GenAIConversationIngestRes(
        conversation_id=conversation_id,
        trace_ids=trace_ids,
        root_span_ids=root_span_ids,
        span_count=len(spans),
    )
