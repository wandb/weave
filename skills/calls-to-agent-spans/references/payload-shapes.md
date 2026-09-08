# Classic payload shapes this converter handles

Each example is one call and the span produced from that same call. Weave ops have no fixed signature, so the converter keeps a candidate path list per role and each call takes the first path that yields text.

Messages are written only when the call is a turn root. A `chat` span below has messages only because that call *is* the root.

If a project's payloads match none of the candidates, add the path to `CONVERSATION_PATHS`, `USER_TEXT_PATHS`, or `ASSISTANT_TEXT_PATHS` in `scripts/payload_paths.py`, or pass it once with `--conversation-path`, `--user-path`, `--assistant-path`. A path is dotted, and a trailing `[i]` indexes a list.

## Plain text

```json
{
  "attributes": {"sessionId": "sess-plain"},
  "inputs": {"message": "question 0 about the S-curve"},
  "output": "Here is the answer to: question 0 about the S-curve"
}
```

Becomes `invoke_agent chat_agent` with `weave.conversation.id = sess-plain`, user message `question 0 about the S-curve`, assistant reply `Here is the answer to: question 0 about the S-curve`.

## OpenAI message list, session id in inputs

```json
{
  "inputs": {
    "messages": [{"role": "user", "content": "list 0 things"}],
    "session_id": "sess-msgs"
  },
  "output": {
    "choices": [{"message": {"role": "assistant", "content": "reply from the message-list agent"}}]
  }
}
```

Becomes `invoke_agent messages_agent`. The last `role=user` message is the turn text, not `messages[-1]` (that is often the assistant once the list is a history).

## OpenAI chat completions (root is the model call)

```json
{
  "attributes": {"sessionId": "sess-plain"},
  "inputs": {"prompt": "question 0"},
  "output": {
    "model": "gpt-4o-2024-08-06",
    "choices": [{"message": {"role": "assistant", "content": "chat completions reply"}, "finish_reason": "stop"}],
    "usage": {
      "prompt_tokens": 120,
      "completion_tokens": 30,
      "prompt_tokens_details": {"cached_tokens": 64}
    }
  }
}
```

Becomes `invoke_agent gpt-4o-2024-08-06` with `weave.agent.name = openai_completion`. A root that names a model is still the turn. Tokens stay on this span so conversation cost is visible.

## Anthropic message (child of an orchestrator)

```json
{
  "inputs": {"prompt": "summarize the pricing page"},
  "output": {
    "model": "claude-sonnet-4-5",
    "content": [{"type": "text", "text": "anthropic reply"}],
    "usage": {"input_tokens": 300, "output_tokens": 45, "cache_read_input_tokens": 128}
  }
}
```

Becomes `chat claude-sonnet-4-5` with conversation id, tokens, and no messages. The turn root carries the user text and this child's reply.

## OpenAI Responses API

```json
{
  "inputs": {"question": "what changed this week?"},
  "output": {
    "model": "gpt-5.2",
    "output": [
      {"type": "reasoning", "content": []},
      {"type": "message", "content": [{"type": "output_text", "text": "responses api reply"}]}
    ],
    "usage": {
      "input_tokens": 500,
      "output_tokens": 60,
      "output_tokens_details": {"reasoning_tokens": 22}
    }
  }
}
```

Becomes `invoke_agent gpt-5.2` with `weave.agent.name = responses_agent` and the Responses `output` list flattened to assistant text.

## Tool call

```json
{
  "inputs": {"query": "pricing"},
  "output": {"hits": [{"title": "Pricing", "score": 0.91}], "count": 1}
}
```

Becomes `execute_tool lookup_docs` with arguments and result, and no conversation id.
