# Session SDK: TypeScript / Node

Run `npm install weave` (the package is `weave`). All calls are safe no-ops before `init()`.

**Two gotchas:**

1. **There is no `new Turn()`.** The classes (`Session`, `Turn`, `LLM`, `Tool`, `SubAgent`) are
   exported as **types only**, so create spans with the `start*` functions:
   `weave.startSession/startTurn/startLLM/startTool/startSubagent()`. The class names are still fine in
   type annotations.
2. **`init` is async.** Call `await weave.init('entity/project')` before any traced work. For auth, set
   `WANDB_API_KEY`, or call `await weave.login(apiKey)` once. The user does this; never hard-code a
   key.

## Canonical pattern (try/finally, because JS has no `with`, so close in `finally`)

```ts
import * as weave from 'weave';
await weave.init('entity/project');

const session = weave.startSession({agentName: 'research-bot'});
try {
  const turn = weave.startTurn({model: 'gpt-4o-mini', userMessage: prompt}); // one Turn per user input
  try {
    let toolCalls = [];
    const llm = weave.startLLM({model: 'gpt-4o-mini', providerName: 'openai'});
    try {
      const resp = await openai.chat.completions.create({
        model,
        messages,
        tools,
      });
      const msg = resp.choices[0].message;
      toolCalls = msg.tool_calls ?? [];
      llm.output(msg.content ?? '');
      llm.record({
        usage: {
          inputTokens: resp.usage?.prompt_tokens,
          outputTokens: resp.usage?.completion_tokens,
        },
      });
    } finally {
      llm.end();
    }

    for (const tc of toolCalls) {
      const tool = weave.startTool({
        name: tc.function.name,
        args: tc.function.arguments,
        toolCallId: tc.id,
      });
      try {
        tool.result = await runTool(JSON.parse(tc.function.arguments));
      } finally {
        tool.end();
      }
    }
  } finally {
    turn.end();
  }
} finally {
  session.end();
}
```

**Parent resolution (async context):** `startTurn` nests under the active session. `startLLM` nests
under the active turn, and **throws** if there is none. `startTool` and `startSubagent` nest under the
active LLM if one is open, otherwise under the turn. `startSubagent({name, model})` nests a delegated
agent.

**LLM helpers:** `.output(content)`, `.think(content)`, and `.record({usage?, reasoning?})` set
fields. Leave `llm.inputMessages` empty on a normal text turn: the user text belongs on
`startTurn({userMessage})`. Copying the conversation history onto the LLM span restacks it in the
Agents tab. Use `inputMessages` only when you need to attach media to a user message that lives on
the LLM span. `.attachMedia({...})` and `.attachMediaUrl(url, {modality})` attach media. `usage` is
camelCase (`{inputTokens, outputTokens, ...}`), unlike Python's snake_case. See `span-shape.md`.

**Concurrency:** the default context is process-wide, so concurrent sessions clash. Wrap each one in
`await weave.runIsolated(async () => { ... })` for parallel agents, such as a server's concurrent
requests.

**Flushing:** spans are batched and flushed on exit. For a short-lived process, call
`await weave.flushOTel()` before exiting.

**ESM vs CJS:** this affects only *auto-instrumentation* (plain `openai`, `anthropic`, and so on), not
these Session SDK calls. CommonJS auto-activates on `import 'weave'`. **ESM must launch with
`node --import=weave/instrument your-entry.mjs`**.
