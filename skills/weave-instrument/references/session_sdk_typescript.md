# Conversation SDK — TypeScript / Node (formerly Session SDK)

Run `npm install weave` (the package is `weave`). Calls made before `init()` are safe no-ops, but
initialization state is not a per-turn consent gate: once a process is initialized, every later span
is eligible for export.

**Two gotchas:**

1. **There is no `new Turn()`.** The classes (`Conversation`, `Turn`, `LLM`, `Tool`, `SubAgent`) are
   exported as **types only**, so create spans with the `start*` functions:
   `weave.startConversation/startTurn/startLLM/startTool/startSubagent()`. The class names are still
   fine in type annotations. `startSession` remains as a deprecated alias for `startConversation`.
2. **`init` is async.** Call `await weave.init('entity/project')` before any traced work. For auth, set
   `WANDB_API_KEY`, or call `await weave.login(apiKey)` once. The user does this; never hard-code a
   key.

## Canonical pattern

Gate tracing before creating a conversation or turn. A metadata-only policy must also keep content
out of auto-instrumented provider spans; omitting it only from Conversation SDK fields is insufficient
if another patcher still captures the provider request.

```ts
import * as weave from 'weave';

function asError(value: unknown): Error {
  return value instanceof Error ? value : new Error(String(value));
}

await weave.init('entity/project');

async function handleTurn(
  prompt: string,
  sharingWithWandbAllowed: boolean
): Promise<string> {
  if (!sharingWithWandbAllowed) {
    return await runAgentWithoutTracing(prompt);
  }

  let answer = '';
  const conversation = weave.startConversation({agentName: 'research-bot'});
  try {
    const turn = weave.startTurn({model: 'gpt-4o-mini'}); // one Turn per user input
    let turnError: Error | undefined;
    try {
      let toolCalls = [];
      const llm = weave.startLLM({
        model: 'gpt-4o-mini',
        providerName: 'openai',
      });
      let llmError: Error | undefined;
      try {
        llm.inputMessages = [{role: 'user', content: prompt}];
        const resp = await openai.chat.completions.create({
          model,
          messages,
          tools,
        });
        const msg = resp.choices[0].message;
        answer = msg.content ?? '';
        toolCalls = msg.tool_calls ?? [];
        llm.output(answer);
        llm.record({
          usage: {
            inputTokens: resp.usage?.prompt_tokens,
            outputTokens: resp.usage?.completion_tokens,
          },
        });
      } catch (error) {
        llmError = asError(error);
        throw error;
      } finally {
        llm.end({error: llmError});
      }

      for (const tc of toolCalls) {
        const tool = weave.startTool({
          name: tc.function.name,
          args: tc.function.arguments,
          toolCallId: tc.id,
        });
        let toolError: Error | undefined;
        try {
          const result = await runTool(JSON.parse(tc.function.arguments));
          tool.result = typeof result === 'string' ? result : JSON.stringify(result);
        } catch (error) {
          toolError = asError(error);
          throw error;
        } finally {
          tool.end({error: toolError});
        }
      }
    } catch (error) {
      turnError = asError(error);
      throw error;
    } finally {
      turn.end({error: turnError});
    }
  } finally {
    conversation.end();
  }

  return answer;
}
```

`finally` guarantees closure, but it does not infer failure status. Pass thrown errors to
`end({error})` as above. If a runner returns `errored`, `timed_out`, or `cancelled` as data instead of
throwing, record that returned terminal state with `turn.setAttributes(...)` before `turn.end()`;
otherwise the trace looks successful. The Node Conversation SDK has no `includeContent` option, so a
metadata-only path must avoid assigning content and must disable or redact any provider patcher that
would capture it. For ESM, do not preload `weave/instrument` on a Conversation-SDK-only path that needs
per-turn denial. If an auto-patcher cannot be disabled, enforce the policy in a filtering span
processor/exporter or isolate tracing in another process, then prove the denied path exports zero
spans.

**Parent resolution (async context):** `startTurn` nests under the active conversation. `startLLM` nests
under the active turn, and **throws** if there is none. `startTool` and `startSubagent` nest under the
active LLM if one is open, otherwise under the turn. `startSubagent({name, model})` nests a delegated
agent.

Create Tool spans around the live `runTool(...)` dispatch, not by replaying tool records after the
runner finishes. Post-hoc spans need explicit original start/end times and still cannot recover
exceptions, timeouts, or cancellations that the transcript omitted.

**LLM helpers:** `llm.inputMessages` and `outputMessages` take a `Message[]` (`{role, content}`).
`.output(content)`, `.think(content)`, and `.record({inputMessages?, outputMessages?, usage?,
reasoning?})` set fields. `.attachMedia({...})` and `.attachMediaUrl(url, {modality})` attach media.
Note that `usage` is camelCase (`{inputTokens, outputTokens, ...}`), unlike Python's snake_case.

**Concurrency:** the default context is process-wide, so concurrent conversations clash. Wrap each one in
`await weave.runIsolated(async () => { ... })` for parallel agents, such as a server's concurrent
requests.

**Flushing:** spans are batched and flushed on exit. For a short-lived process, call
`await weave.flushOTel()` before exiting.

**ESM vs CJS:** this affects only *auto-instrumentation* (plain `openai`, `anthropic`, and so on), not
these Conversation SDK calls. CommonJS auto-activates on `import 'weave'`. **ESM must launch with
`node --import=weave/instrument your-entry.mjs`**.
