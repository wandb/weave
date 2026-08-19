# Classic payload shapes and what they convert to

Every example below is a real call logged by `scripts/log_test_fixture.py` and the span the
converter actually produced from it. Weave ops have no fixed signature, so the converter keeps a
candidate path list per role and each call takes the first path that yields text for that call.

## The mapping inferred from these calls

```json
{
  "conversation": [
    "attributes.sessionId",
    "attributes.conversation_id",
    "inputs.session_id"
  ],
  "user": [
    "inputs.message",
    "inputs.messages[-1].content",
    "inputs.prompt",
    "inputs.question"
  ],
  "assistant": [
    "output.choices[0].message.content",
    "output.output",
    "output"
  ]
}
```

## Plain text in, plain text out

The simplest shape: a string argument, a string return, and the session id stamped with `weave.attributes`.

Call:

```json
{
  "attributes": {
    "sessionId": "sess-0b8adafd"
  },
  "inputs": {
    "message": "question 0 about the S-curve"
  },
  "output": "Here is the answer to: question 0 about the S-curve"
}
```

Span `invoke_agent chat_agent`:

```json
{
  "weave.operation.name": "invoke_agent",
  "weave.conversation.id": "sess-0b8adafd",
  "weave.agent.name": "chat_agent",
  "weave.input.messages": "[{\"role\": \"user\", \"content\": \"question 2 about the S-curve\"}]",
  "weave.output.messages": "[{\"role\": \"assistant\", \"content\": \"Here is the answer to: question 2 about the S-curve\"}]"
}
```

## OpenAI message list in, choices out

The session id is an ordinary op argument rather than an attribute, and the reply is nested in `choices`.

Call:

```json
{
  "inputs": {
    "messages": [
      {
        "role": "user",
        "content": "list 0 things"
      }
    ],
    "session_id": "sess-e7f14f5f"
  },
  "output": {
    "choices": [
      {
        "message": {
          "role": "assistant",
          "content": "reply from the message-list agent"
        }
      }
    ]
  }
}
```

Span `invoke_agent messages_agent`:

```json
{
  "weave.operation.name": "invoke_agent",
  "weave.conversation.id": "sess-e7f14f5f",
  "weave.agent.name": "messages_agent",
  "weave.input.messages": "[{\"role\": \"user\", \"content\": \"list 1 things\"}]",
  "weave.output.messages": "[{\"role\": \"assistant\", \"content\": \"reply from the message-list agent\"}]"
}
```

## OpenAI chat completions payload

Cached tokens arrive under `prompt_tokens_details`, which is why the token reader probes nested detail objects.

Call:

```json
{
  "attributes": {
    "sessionId": "sess-0b8adafd"
  },
  "inputs": {
    "prompt": "question 0"
  },
  "output": {
    "model": "gpt-4o-2024-08-06",
    "choices": [
      {
        "message": {
          "role": "assistant",
          "content": "chat completions reply"
        },
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 120,
      "completion_tokens": 30,
      "prompt_tokens_details": {
        "cached_tokens": 64
      }
    }
  }
}
```

Span `chat gpt-4o-2024-08-06`:

```json
{
  "weave.operation.name": "chat",
  "weave.conversation.id": "sess-0b8adafd",
  "weave.request.model": "gpt-4o-2024-08-06",
  "weave.response.model": "gpt-4o-2024-08-06",
  "weave.provider.name": "openai",
  "weave.usage.input_tokens": 120,
  "weave.usage.output_tokens": 30,
  "weave.usage.cache_read.input_tokens": 64,
  "weave.input.messages": "[{\"role\": \"user\", \"content\": \"question 2\"}]",
  "weave.output.messages": "[{\"role\": \"assistant\", \"content\": \"chat completions reply\"}]"
}
```

## Anthropic message payload

Different token key names entirely, and cache reads are a top-level field rather than a nested detail.

Call:

```json
{
  "attributes": {
    "conversation_id": "sess-0b8adafd"
  },
  "inputs": {
    "prompt": "summarize the pricing page"
  },
  "output": {
    "model": "claude-sonnet-4-5",
    "content": [
      {
        "type": "text",
        "text": "anthropic reply"
      }
    ],
    "usage": {
      "input_tokens": 300,
      "output_tokens": 45,
      "cache_read_input_tokens": 128
    }
  }
}
```

Span `chat claude-sonnet-4-5`:

```json
{
  "weave.operation.name": "chat",
  "weave.conversation.id": "sess-0b8adafd",
  "weave.request.model": "claude-sonnet-4-5",
  "weave.response.model": "claude-sonnet-4-5",
  "weave.provider.name": "anthropic",
  "weave.usage.input_tokens": 300,
  "weave.usage.output_tokens": 45,
  "weave.usage.cache_read.input_tokens": 128
}
```

## OpenAI Responses API payload

The reply is buried in an `output` list beside reasoning items, and reasoning tokens are a nested detail.

Call:

```json
{
  "inputs": {
    "question": "what changed this week?"
  },
  "output": {
    "model": "gpt-5.2",
    "output": [
      {
        "type": "reasoning",
        "content": []
      },
      {
        "type": "message",
        "content": [
          {
            "type": "output_text",
            "text": "responses api reply"
          }
        ]
      }
    ],
    "usage": {
      "input_tokens": 500,
      "output_tokens": 60,
      "output_tokens_details": {
        "reasoning_tokens": 22
      }
    }
  }
}
```

Span `chat gpt-5.2`:

```json
{
  "weave.operation.name": "chat",
  "weave.conversation.id": "01a01816-5b24-7f95-8971-99d78de82ff5",
  "weave.request.model": "gpt-5.2",
  "weave.response.model": "gpt-5.2",
  "weave.provider.name": "openai",
  "weave.usage.input_tokens": 500,
  "weave.usage.output_tokens": 60,
  "weave.usage.reasoning_tokens": 22,
  "weave.input.messages": "[{\"role\": \"user\", \"content\": \"what changed this week?\"}]",
  "weave.output.messages": "[{\"role\": \"assistant\", \"content\": \"responses api reply\"}]"
}
```

## A tool call

Childless and naming no model, so it becomes `execute_tool`. Its arguments and result are fetched in a second, narrow pass.

Call:

```json
{
  "attributes": {
    "conversation_id": "sess-0b8adafd"
  },
  "inputs": {
    "query": "pricing"
  },
  "output": {
    "hits": [
      {
        "title": "Pricing",
        "score": 0.91
      }
    ],
    "count": 1
  }
}
```

Span `execute_tool lookup_docs`:

```json
{
  "weave.operation.name": "execute_tool",
  "weave.tool.name": "lookup_docs",
  "weave.tool.call.id": "01a01816-5b23-7f52-b20c-6f2fe57a4275",
  "weave.tool.call.arguments": "{\"query\": \"pricing\"}",
  "weave.tool.call.result": "{\"hits\": [{\"title\": \"Pricing\", \"score\": 0.91}], \"count\": 1}"
}
```

## Adding a shape

If a project's payloads match none of the candidates, add the path to `CONVERSATION_PATHS`,
`USER_TEXT_PATHS`, or `ASSISTANT_TEXT_PATHS` in the converter, or pass it once with
`--conversation-path`, `--user-path`, `--assistant-path`. A path is dotted, and a trailing
`[i]` on a step indexes into a list, so `output.choices[0].message.content` and
`inputs.messages[-1].content` both work.
