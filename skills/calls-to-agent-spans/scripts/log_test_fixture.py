"""Log classic weave calls in several shapes, to give the converter something to convert.

    WANDB_API_KEY=... FIXTURE_PROJECT=entity/project python scripts/log_test_fixture.py

Set WANDB_BASE_URL and WF_TRACE_SERVER_URL as well when targeting anything but SaaS.
"""

import os
import uuid

import weave

weave.init(os.environ["FIXTURE_PROJECT"])


# Shape 1: plain string in, plain string out, session id in attributes.
@weave.op
def chat_agent(message: str) -> str:
    return f"Here is the answer to: {message}"


@weave.op
def openai_completion(prompt: str) -> dict:
    return {
        "model": "gpt-4o-2024-08-06",
        "choices": [
            {
                "message": {"role": "assistant", "content": "chat completions reply"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "prompt_tokens_details": {"cached_tokens": 64},
        },
    }


# Shape 2: OpenAI message-list in, choices out, session id in inputs.
@weave.op
def messages_agent(messages: list, session_id: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "reply from the message-list agent",
                }
            }
        ]
    }


# Shape 3: tool-using orchestrator, anthropic-style usage.
@weave.op
def orchestrator(task: str) -> str:
    lookup_docs("pricing")
    anthropic_message(task)
    return "orchestrated answer"


@weave.op
def lookup_docs(query: str) -> dict:
    return {"hits": [{"title": "Pricing", "score": 0.91}], "count": 1}


@weave.op
def anthropic_message(prompt: str) -> dict:
    return {
        "model": "claude-sonnet-4-5",
        "content": [{"type": "text", "text": "anthropic reply"}],
        "usage": {
            "input_tokens": 300,
            "output_tokens": 45,
            "cache_read_input_tokens": 128,
        },
    }


# Shape 4: Responses API, reply nested in an output list.
@weave.op
def responses_agent(question: str) -> dict:
    return {
        "model": "gpt-5.2",
        "output": [
            {"type": "reasoning", "content": []},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "responses api reply"}],
            },
        ],
        "usage": {
            "input_tokens": 500,
            "output_tokens": 60,
            "output_tokens_details": {"reasoning_tokens": 22},
        },
    }


def main() -> None:
    session_a, session_b = (
        f"sess-{uuid.uuid4().hex[:8]}",
        f"sess-{uuid.uuid4().hex[:8]}",
    )
    for turn in range(3):
        with weave.attributes({"sessionId": session_a}):
            chat_agent(f"question {turn} about the S-curve")
            openai_completion(f"question {turn}")
    for turn in range(2):
        messages_agent(
            [{"role": "user", "content": f"list {turn} things"}], session_id=session_b
        )
    with weave.attributes({"conversation_id": session_a}):
        orchestrator("summarize the pricing page")
    # No conversation key anywhere: exercises the trace-per-conversation fallback.
    responses_agent("what changed this week?")
    print("logged")


if __name__ == "__main__":
    main()
