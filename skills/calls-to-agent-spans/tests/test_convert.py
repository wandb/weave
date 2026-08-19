"""Converter behavior a caller depends on: span shape, path inference, and write guards."""

from __future__ import annotations

import argparse

import pytest
import requests
from convert_calls_to_agent_spans import convert
from payload_paths import infer_mapping, last_user_message_text
from span_builder import build_spans


def _call(
    *,
    call_id: str,
    trace_id: str,
    op: str,
    parent_id: str = "",
    inputs: dict | None = None,
    output: object = None,
    attributes: dict | None = None,
    started_at: str = "2026-08-01T00:00:00Z",
) -> dict:
    return {
        "id": call_id,
        "trace_id": trace_id,
        "parent_id": parent_id,
        "op_name": f"weave:///e/p/op/{op}:digest",
        "started_at": started_at,
        "ended_at": started_at,
        "inputs": inputs or {},
        "output": output,
        "attributes": attributes or {},
    }


def test_turn_tree_and_write_guards():
    """A wrapper turn, a model-only root, history messages, and same-project writes."""
    mapping = {
        "conversation": ["attributes.sessionId", "inputs.session_id"],
        "user": ["inputs.message", "inputs.task", "inputs.prompt", "inputs.question"],
        "assistant": ["output.choices[0].message.content", "output.content", "output"],
    }
    orchestrator = _call(
        call_id="00000000-0000-0000-0000-000000000001",
        trace_id="11111111-1111-1111-1111-111111111111",
        op="orchestrator",
        inputs={"task": "summarize the pricing page"},
        output="orchestrated answer",
        attributes={"sessionId": "sess-a"},
    )
    tool = _call(
        call_id="00000000-0000-0000-0000-000000000002",
        trace_id=orchestrator["trace_id"],
        op="lookup_docs",
        parent_id=orchestrator["id"],
        inputs={"query": "pricing"},
        output={"hits": 1},
        started_at="2026-08-01T00:00:01Z",
    )
    model = _call(
        call_id="00000000-0000-0000-0000-000000000003",
        trace_id=orchestrator["trace_id"],
        op="anthropic_message",
        parent_id=orchestrator["id"],
        inputs={"prompt": "summarize the pricing page"},
        output={
            "model": "claude-sonnet-4-5",
            "content": [{"type": "text", "text": "anthropic reply"}],
            "usage": {"input_tokens": 300, "output_tokens": 45},
        },
        started_at="2026-08-01T00:00:02Z",
    )
    solo = _call(
        call_id="00000000-0000-0000-0000-000000000004",
        trace_id="22222222-2222-2222-2222-222222222222",
        op="openai_completion",
        inputs={"prompt": "question 0"},
        output={
            "model": "gpt-4o-2024-08-06",
            "choices": [{"message": {"content": "chat completions reply"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        },
        attributes={"sessionId": "sess-a"},
    )
    history = _call(
        call_id="00000000-0000-0000-0000-000000000005",
        trace_id="33333333-3333-3333-3333-333333333333",
        op="messages_agent",
        inputs={
            "session_id": "sess-b",
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "old reply"},
                {"role": "user", "content": "second"},
            ],
        },
        output={"choices": [{"message": {"content": "new reply"}}]},
    )
    no_session = _call(
        call_id="00000000-0000-0000-0000-000000000006",
        trace_id="44444444-4444-4444-4444-444444444444",
        op="responses_agent",
        inputs={"question": "what changed this week?"},
        output={
            "model": "gpt-5.2",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "weekly"}],
                }
            ],
        },
    )

    spans = {
        s["name"]: s
        for s in build_spans(
            [orchestrator, tool, model, solo, history, no_session], mapping
        )
    }
    turn = spans["invoke_agent orchestrator"]
    chat = spans["chat claude-sonnet-4-5"]
    tool_span = spans["execute_tool lookup_docs"]
    solo_span = spans["invoke_agent gpt-4o-2024-08-06"]
    hist = spans["invoke_agent messages_agent"]
    fallback = spans["invoke_agent gpt-5.2"]

    assert turn["attributes"]["weave.input.messages"] == (
        '[{"role": "user", "content": "summarize the pricing page"}]'
    )
    assert turn["attributes"]["weave.output.messages"] == (
        '[{"role": "assistant", "content": "anthropic reply"}]'
    )
    assert turn["attributes"]["weave.conversation.id"] == "sess-a"
    assert "weave.input.messages" not in chat["attributes"]
    assert chat["attributes"]["weave.conversation.id"] == "sess-a"
    assert chat["attributes"]["weave.usage.input_tokens"] == 300
    assert "weave.conversation.id" not in tool_span["attributes"]
    assert tool_span["attributes"]["weave.tool.call.arguments"] == '{"query": "pricing"}'
    assert solo_span["attributes"]["weave.operation.name"] == "invoke_agent"
    assert solo_span["attributes"]["weave.agent.name"] == "openai_completion"
    assert solo_span["attributes"]["weave.usage.input_tokens"] == 120
    assert hist["attributes"]["weave.input.messages"] == (
        '[{"role": "user", "content": "second"}]'
    )
    assert fallback["attributes"]["weave.conversation.id"] == no_session["trace_id"]

    sample = [orchestrator, solo, history, no_session]
    inferred = infer_mapping(sample, {"conversation": "", "user": "", "assistant": ""})
    assert "inputs.task" in inferred["user"]
    assert last_user_message_text(history) == "second"

    with pytest.raises(SystemExit, match="source project"):
        convert(
            requests.Session(),
            "https://trace.wandb.ai",
            argparse.Namespace(
                source_project="e/old",
                target_project="e/old",
                started_after="2026-08-01T00:00:00Z",
                started_before="",
                conversation_path="",
                user_path="",
                assistant_path="",
                dry_run=True,
                allow_existing=False,
            ),
        )
