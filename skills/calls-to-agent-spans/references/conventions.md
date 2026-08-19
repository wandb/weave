# Agents-tab span conventions

The Agents tab renders a span tree. A populated field is a rendering instruction, not optional metadata. Empty is often load-bearing.

`weave.*` is the canonical key. Each attribute also accepts a `gen_ai.*` alias. If both are present, `weave.*` wins.

The attribute registry (every canonical key, type, and alias) is [`weave/trace_server/agents/semconv.py`](https://github.com/wandb/weave/blob/master/weave/trace_server/agents/semconv.py). Read it when you need a key that is not in the example below. It is not a rendering guide.

## Contracts the tab depends on

1. **A turn is one trace.** The root is `invoke_agent`. Children are `chat` or `execute_tool`. There is no separate turn id.
2. **Conversation id belongs on the turn and on model calls.** Conversation list totals tokens and cost from spans that carry the id. Tokens live on `chat` (or on a root that is itself the model call). Leave the id off those spans and cost reads empty while the thread still looks full. Tool spans leave it empty.
3. **Messages only on the turn root.** The thread is built from the tree. Filling `input_messages` / `output_messages` / `system_instructions` / `tool_definitions` on a child restacks history under the first turn.
4. **Name is `{operation} {subject}`.** The tab reads the agent label from an `invoke_agent ` prefix and the tool name from an `execute_tool ` prefix when the dedicated fields are missing.
5. **Healthy status is unset, not ok.** Marking everything OK makes converted data look annotated in a way live traces are not.
6. **Cost is derived.** The product prices `input` / `output` / cache tokens against the span's model. There is no cost attribute to set.

## One complete turn

One conversation, one turn, three spans. Fields that must stay empty are omitted, not set to `""`.

```json
{
  "conversation_id": "sess-weather",
  "spans": [
    {
      "name": "invoke_agent weather-bot",
      "kind": "INTERNAL",
      "status": "UNSET",
      "attributes": {
        "weave.operation.name": "invoke_agent",
        "weave.conversation.id": "sess-weather",
        "weave.conversation.name": "Tokyo weather",
        "weave.agent.name": "weather-bot",
        "weave.agent.id": "weather-bot-v3",
        "weave.agent.description": "Answers weather questions",
        "weave.agent.version": "3",
        "weave.request.model": "gpt-4o-2024-08-06",
        "weave.response.model": "gpt-4o-2024-08-06",
        "weave.input.messages": "[{\"role\": \"user\", \"content\": \"weather in Tokyo?\"}]",
        "weave.output.messages": "[{\"role\": \"assistant\", \"content\": \"75F and sunny.\"}]"
      }
    },
    {
      "name": "chat gpt-4o-2024-08-06",
      "kind": "CLIENT",
      "status": "UNSET",
      "attributes": {
        "weave.operation.name": "chat",
        "weave.conversation.id": "sess-weather",
        "weave.provider.name": "openai",
        "weave.request.model": "gpt-4o-2024-08-06",
        "weave.response.model": "gpt-4o-2024-08-06",
        "weave.response.id": "chatcmpl-abc",
        "weave.usage.input_tokens": 120,
        "weave.usage.output_tokens": 30,
        "weave.usage.reasoning_tokens": 8,
        "weave.usage.cache_read.input_tokens": 64,
        "weave.usage.cache_creation.input_tokens": 16,
        "weave.reasoning_content": "Need a weather tool call, then answer.",
        "weave.request.temperature": 0.2,
        "weave.request.max_tokens": 512,
        "weave.request.top_p": 1.0,
        "weave.request.frequency_penalty": 0.0,
        "weave.request.presence_penalty": 0.0,
        "weave.request.seed": 7,
        "weave.request.stop_sequences": ["END"],
        "weave.request.choice.count": 1,
        "weave.response.finish_reasons": ["stop"],
        "weave.output.type": "text",
        "weave.server.address": "api.openai.com",
        "weave.server.port": 443
      }
    },
    {
      "name": "execute_tool get_weather",
      "kind": "INTERNAL",
      "status": "UNSET",
      "attributes": {
        "weave.operation.name": "execute_tool",
        "weave.tool.name": "get_weather",
        "weave.tool.type": "function",
        "weave.tool.call.id": "call_1",
        "weave.tool.description": "Current weather for a city",
        "weave.tool.call.arguments": "{\"city\": \"Tokyo\"}",
        "weave.tool.call.result": "{\"temp_f\": 75, \"conditions\": \"sunny\"}"
      }
    }
  ]
}
```

Omitted on purpose on every span in that tree: `weave.input.messages` and `weave.output.messages` on `chat` and `execute_tool`; `weave.system_instructions`; `weave.tool.definitions`; `weave.conversation.id` on the tool; token columns on the turn root and the tool.

## Attribute inventory

Every registry key. `omit` means leave it unset. `set` is the example value role.

| Canonical key | Alias (first) | invoke_agent | chat | execute_tool |
| --- | --- | --- | --- | --- |
| `weave.operation.name` | `gen_ai.operation.name` | set | set | set |
| `weave.provider.name` | `gen_ai.provider.name` | omit | set | omit |
| `weave.system` | `gen_ai.system` | omit (deprecated; use provider) | omit | omit |
| `weave.agent.name` | `gen_ai.agent.name` | set | omit | omit |
| `weave.agent.id` | `gen_ai.agent.id` | optional | omit | omit |
| `weave.agent.description` | `gen_ai.agent.description` | optional | omit | omit |
| `weave.agent.version` | `gen_ai.agent.version` | optional | omit | omit |
| `weave.request.model` | `gen_ai.request.model` | answering model | set | omit |
| `weave.response.model` | `gen_ai.response.model` | answering model | set | omit |
| `weave.response.id` | `gen_ai.response.id` | omit | optional | omit |
| `weave.usage.input_tokens` | `gen_ai.usage.input_tokens` | omit | set | omit |
| `weave.usage.output_tokens` | `gen_ai.usage.output_tokens` | omit | set | omit |
| `weave.usage.reasoning_tokens` | `gen_ai.usage.reasoning.output_tokens` | omit | optional | omit |
| `weave.usage.cache_creation.input_tokens` | `gen_ai.usage.cache_creation.input_tokens` | omit | optional | omit |
| `weave.usage.cache_read.input_tokens` | `gen_ai.usage.cache_read.input_tokens` | omit | optional | omit |
| `weave.conversation.id` | `gen_ai.conversation.id` | set | set | omit |
| `weave.conversation.name` | `gen_ai.conversation.name` | optional | omit | omit |
| `weave.tool.name` | `gen_ai.tool.name` | omit | omit | set |
| `weave.tool.type` | `gen_ai.tool.type` | omit | omit | optional |
| `weave.tool.call.id` | `gen_ai.tool.call.id` | omit | omit | set |
| `weave.tool.description` | `gen_ai.tool.description` | omit | omit | optional |
| `weave.tool.definitions` | `gen_ai.tool.definitions` | omit | omit | omit |
| `weave.tool.call.arguments` | `gen_ai.tool.call.arguments` | omit | omit | set |
| `weave.tool.call.result` | `gen_ai.tool.call.result` | omit | omit | set |
| `weave.request.temperature` | `gen_ai.request.temperature` | omit | optional | omit |
| `weave.request.max_tokens` | `gen_ai.request.max_tokens` | omit | optional | omit |
| `weave.request.top_p` | `gen_ai.request.top_p` | omit | optional | omit |
| `weave.request.frequency_penalty` | `gen_ai.request.frequency_penalty` | omit | optional | omit |
| `weave.request.presence_penalty` | `gen_ai.request.presence_penalty` | omit | optional | omit |
| `weave.request.seed` | `gen_ai.request.seed` | omit | optional | omit |
| `weave.request.stop_sequences` | `gen_ai.request.stop_sequences` | omit | optional | omit |
| `weave.request.choice.count` | `gen_ai.request.choice.count` | omit | optional | omit |
| `weave.response.finish_reasons` | `gen_ai.response.finish_reasons` | omit | optional | omit |
| `weave.output.type` | `gen_ai.output.type` | omit | optional | omit |
| `weave.input.messages` | `gen_ai.input.messages` | user turn only | omit | omit |
| `weave.output.messages` | `gen_ai.output.messages` | assistant reply only | omit | omit |
| `weave.system_instructions` | `gen_ai.system_instructions` | omit | omit | omit |
| `weave.completion` | `gen_ai.completion` | omit (deprecated) | omit | omit |
| `weave.error.type` | `error.type` | only on failure | only on failure | only on failure |
| `weave.server.address` | `server.address` | omit | optional | omit |
| `weave.server.port` | `server.port` | omit | optional | omit |
| `weave.reasoning_content` | (weave only) | omit | optional | omit |

Optional overlays, set only when the source actually has them. Do not invent values.

| Canonical key | When |
| --- | --- |
| `weave.compaction.summary` / `items_before` / `items_after` | a context-compaction event |
| `weave.content_refs` / `artifact_refs` / `object_refs` | uploaded or linked media |
| `weave.eval.run_id` / `predict_and_score_call_id` / `kind` / `row_digest` / `example_id` / `trial_index` / `evaluation_name` | the turn is part of an evaluation |
| `weave.parent_call.id` / `weave.parent_call.trace_id` | this span started under a live `@weave.op` call |

Reasoning-token aliases also recognized on ingest: `gen_ai.usage.reasoning_tokens`, `gen_ai.usage.experimental.reasoning_tokens`. Cache-read aliases: `gen_ai.usage.prompt_tokens_details.cached_tokens`, `gen_ai.usage.input_tokens_details.cached_tokens`, `prompt_tokens_details.cached_tokens`.
