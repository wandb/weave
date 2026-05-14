# Weave Node SDK — GenAI Tracing Module Design

**Status:** Draft
**Author:** TBD
**Last updated:** 2026-05-12
**Companion doc:** [`original_design_doc.md`](./original_design_doc.md) (Python SDK, `go/genai-tracing-for-wandb-agent`)

---

## 1. Goal

Add a TypeScript implementation of the Weave **GenAI session/turn/LLM/tool** tracing surface so Node-based agents can dual-write `genai_spans` to the Weave server and have their conversations appear in the Agents tab. This is the Node mirror of [`weave/session/`](../../weave/session/) in the Python SDK.

Like the Python implementation, the wire format is **OpenTelemetry spans carrying GenAI semantic-convention attributes**, sent to the `/agents/otel/v1/traces` endpoint on the trace server ([weave/trace/urls.py:11](../../weave/trace/urls.py#L11)). No new ingest path is needed.

**Primary audience.** Weave SDK users building agent frameworks by hand (or with frameworks that don't yet have native Weave instrumentation). WB Agent is one specific example, not the dominant consumer.

**Note on `pi-coding-agent` integration.** The existing [`src/integrations/piCodingAgent.ts`](./src/integrations/piCodingAgent.ts) currently posts to `/otel/v1/traces`, which is a known bug — it should target `/agents/otel/v1/traces` too. Refactoring it is **out of scope** for this project. When that refactor lands, piCodingAgent will consume the GenAI provider exposed by this module (`getWeaveTracer` from `src/genai/provider.ts`) and delete its own provider/exporter wiring.

This is purely additive — the existing `@op`, `WeaveClient`, and trace-server HTTP batch path remain unchanged.

---

## 2. Scope and non-goals

**In scope**

- Top-level entry points to start/end `Session`, `Turn`, `LLM`, `Tool`, `SubAgent`.
- A `LLM`-enrichment surface: `output`, `think`, `attachMedia`, `attachMediaUrl`, `record`, `start_tool` equivalents.
- Async-context-backed "current" lookups: `getCurrentSession`, `getCurrentTurn`, `getCurrentLLM`.
- Batch logging for "already-finished" work: `logTurn`, `logSession`.
- Wire-up of an `OTLPTraceExporter` + `BatchSpanProcessor` inside `init()`, plus a no-op fallback when `init()` was not called.
- Graceful flush hook so spans aren't dropped on process exit.

**Out of scope (v1)**

- Auto-instrumentation of openai / anthropic / vercel-ai SDK clients (a follow-up; the GenAI surface is the prerequisite).
- A replacement for the existing `@op` decorator; the two co-exist.
- A second wire format alongside OTel (no direct calls to the trace-server batch endpoint from this module).

---

## 3. Background

### Python reference

The Python SDK (audit, 2026-05-12):

- Classes: [`Session`, `Turn`, `LLM`, `Tool`, `SubAgent`](../../weave/session/session.py)
- Data models: [`Usage`, `Reasoning`, `Message`](../../weave/session/types.py)
- Top-level: `start_session`, `start_turn`, `start_llm`, `start_tool`, `start_subagent`, `end_*`, `log_turn`, `log_session`, `get_current_*` — all in [`weave/session/session.py`](../../weave/session/session.py)
- OTel setup: [`_setup_session_tracing()`](../../weave/trace/weave_init.py) configures `OTLPSpanExporter` + `BatchSpanProcessor` on `weave.init()`.
- Server side: `genai_otel_export()` and `extract_genai_span()` parse the inbound OTLP spans and insert into the ClickHouse `spans` table.

### Existing Node SDK state

- Entry: [`src/index.ts`](./src/index.ts). `init(project, settings)` is in [`src/clientApi.ts`](./src/clientApi.ts).
- Tracing primitive: `@op` decorator + `AsyncLocalStorage<CallStack>` in [`src/weaveClient.ts`](./src/weaveClient.ts).
- No GenAI/session surface yet. The pi-coding-agent integration ([`src/integrations/piCodingAgent.ts`](./src/integrations/piCodingAgent.ts)) is the **only** code in the SDK that uses OpenTelemetry today. Its provider/exporter/`beforeExit`-flush wiring is a useful reference, but we do **not** modify it. The new GenAI module lives at [`src/genai/`](./src/genai/) and is designed so piCodingAgent can later switch to it as a follow-up refactor.
- A GenAI semconv key bundle already exists at [`src/integrations/common/genai.ts`](./src/integrations/common/genai.ts) — reuse and extend.

### Confirmed design choices (from the user, 2026-05-12)

1. **Naming follows the Python code, not the original doc.** Class is `LLM`, top-level fn is `startLLM`, accessor is `getCurrentLLM`. (Doc had used `Step`/`startChat`.) Keeps the two SDKs aligned 1:1 for shared docs and easier migration.
2. **Manual `start()`/`end()` is the primary idiom.** No callback wrapper as the main surface. An `await using` chapter (§9) documents the future option once Node 22+ is a hard floor.
3. **`piCodingAgent` is not touched in this stack.** Its `/otel/v1/traces` URL is a known bug; the fix is a separate refactor. When that refactor happens, piCodingAgent will consume `getWeaveTracer` from this module.
4. **`BatchSpanProcessor` is the default; `SimpleSpanProcessor` and user-supplied processors are selectable via `init()`.** The OTLP **exporter** itself stays non-replaceable — must hit `/agents/otel/v1/traces`.
5. **Cross-module context uses `AsyncLocalStorage.enterWith` + restore-on-end** (Python contextvar parity). No `session.run(fn)` / `turn.run(fn)` helpers.
6. **`logTurn` / `logSession` deferred out of v1, but as the immediate follow-up PR**, not far-future.

---

## 4. Public API

### 4.1 Module layout

```
sdks/node/src/genai/
├── index.ts             // module-internal re-exports (consumed by src/index.ts)
├── types.ts             // Usage, Message, Reasoning, Modality, ...
├── semconv.ts           // GenAI OTel semconv constants + Weave resource attrs
├── provider.ts          // singleton TracerProvider + OTLP exporter → /agents/otel/v1/traces
├── flush.ts             // flushWeaveOTel() helper
├── session.ts           // Session class
├── turn.ts              // Turn class
├── llm.ts               // LLM class
├── tool.ts              // Tool class
├── subagent.ts          // SubAgent class
├── context.ts           // AsyncLocalStorage holders + getCurrent*
└── noop.ts              // no-op span / disabled-state helpers
```

**Not a subpackage.** The `weave` npm package keeps its current two entry points (`.` and `./instrument`). All new APIs are re-exported from the top-level [`src/index.ts`](./src/index.ts); no new subpath export (`weave/genai`, `weave/otel`, etc.) is introduced.

**Single `src/genai/` directory, no `src/otel/` split.** Every artifact in this PR stack is GenAI-specific: the semconv constants are the OTel **GenAI** semconv namespace, the provider emits exclusively to `/agents/otel/v1/traces` (the GenAI ingest endpoint), and the flush helper drives that one provider. piCodingAgent is itself a GenAI emitter, so "shared with piCodingAgent" is still GenAI sharing, not generic OTel sharing. A separate `src/otel/` directory would have been premature abstraction with no non-GenAI consumer to justify it.

**Semconv file relocation.** The existing [`src/integrations/common/genai.ts`](./src/integrations/common/genai.ts) is not integration-specific — it's the OTel GenAI semconv key namespace. It moves to `src/genai/semconv.ts` in **PR 1** alongside the new type definitions. New keys the new module needs (`gen_ai.input.messages`, `gen_ai.output.messages`, `weave.sdk.version`, `weave.sdk.language`) are added in the same PR.

Re-exports from [`src/index.ts`](./src/index.ts):

```ts
export {
  startSession, startTurn, startLLM, startTool, startSubagent,
  endSession, endTurn, endLLM,
  getCurrentSession, getCurrentTurn, getCurrentLLM,
  logTurn, logSession,
  Session, Turn, LLM, Tool, SubAgent,
  Usage, Message, Reasoning, Modality,
} from './genai';
```

### 4.2 Naming convention

| Python | TypeScript |
| :---- | :---- |
| `weave.start_session(agent_name="weather-bot", session_id="s1")` | `weave.startSession({ agentName: 'weather-bot', sessionId: 's1' })` |
| `step.usage = Usage(input_tokens=100)` | `llm.usage = { inputTokens: 100 }` |
| `session_id`, `agent_name`, `input_tokens` (snake_case kwargs) | `sessionId`, `agentName`, `inputTokens` (camelCase, single options object) |

Single-options-object form for >1 parameter; positional argument allowed for the one obvious required field (e.g. `tool.result = '75F'`). Matches existing `init(project, settings)` / `wrapOpenAI(client)` conventions.

### 4.3 Entry points

```ts
// init wires up the OTel pipeline (idempotent)
await weave.init('entity/project');

// Real-time, hierarchical
const session = await weave.startSession({ agentName: 'weather-bot', model: 'gpt-4o', sessionId: 's-1' });
const turn    = await session.startTurn({ agentName: 'weather-bot', model: 'gpt-4o' });
const llm     = await turn.llm({ model: 'gpt-4o', providerName: 'openai' });
const tool    = await llm.startTool({ name: 'get_weather', arguments: '{"city":"Tokyo"}' });

await tool.end({ result: '75F' });
await llm.end();
await turn.end();
await session.end();

// Real-time, top-level (reads AsyncLocalStorage current-turn / current-llm)
await weave.startSession({ agentName: 'weather-bot' });
await weave.startTurn({ userMessage: "What's the weather?" });
await weave.startLLM({ model: 'gpt-4o' });
// ...
await weave.endLLM();
await weave.endTurn();
await weave.endSession();

// Batch (no live spans needed — everything created+ended in one call)
await weave.logTurn({
  sessionId: 's-1',
  agentName: 'weather-bot',
  messages: [ { role: 'user', content: 'Hi' }, { role: 'assistant', content: 'Hello' } ],
  model: 'gpt-4o',
  steps: [ /* same shape as Python log_turn */ ],
});

// Context access
const s = weave.getCurrentSession();   // Session | undefined
const t = weave.getCurrentTurn();      // Turn | undefined
const l = weave.getCurrentLLM();       // LLM | undefined
```

### 4.4 `LLM` enrichment surface

```ts
class LLM {
  usage: Usage;                                          // assign directly
  reasoning: Reasoning;
  inputMessages: Message[];
  outputMessages: Message[];

  output(content: string): this;                         // append assistant text
  think(content: string): this;                          // set reasoning content
  attachMedia(opts: { content?: string; uri?: string; fileId?: string; mimeType?: string; modality: Modality }): this;
  attachMediaUrl(url: string, opts?: { modality?: Modality }): this;
  record(opts: { inputMessages?: Message[]; outputMessages?: Message[]; usage?: Usage; reasoning?: Reasoning }): this;

  startTool(opts: { name: string; arguments?: string; toolCallId?: string }): Promise<Tool>;
  startSubagent(opts: { name: string; model?: string }): Promise<SubAgent>;
  end(opts?: { error?: Error }): Promise<void>;
}
```

Following the Python decision, the three Python `attach_file` / `attach_image` / `attach_uri` methods are unified behind `attachMedia` + `attachMediaUrl` ([Python session.py:285](../../weave/session/session.py#L285)).

### 4.5 Why not classic "context managers"?

JavaScript has no `with` statement. Three plausible substitutes — we pick **manual `start/end`** as the primary surface:

- ✅ Imposes no Node-version floor.
- ✅ Works naturally for the cross-module case (start a turn in one module, end it in another) without forcing users to thread a callback through.
- ✅ Maps one-to-one to the Python `start_*`/`end_*` API, so the two SDKs stay in lockstep for shared docs and easier user migration.
- ⚠️ Burden on the user to `try/finally`. We mitigate with: (a) `end({ error })` accepting the caught error and setting span status correctly; (b) clear docs; (c) the `beforeExit` hook flushes any in-flight spans so the user at least sees them in the UI even if a `throw` escaped without an explicit `end()`.

See §9 for an `await using` chapter that uses the same classes once Node 22+ is a hard floor — that path costs ~2 LOC per class to enable.

---

## 5. Data models

Plain TypeScript types — no Zod, no class wrappers. Rationale: the SDK's existing wire-facing types ([`src/generated/traceServerApi.ts`](./src/generated/traceServerApi.ts)) are also plain interfaces, and Zod adds a runtime dep we don't pay anywhere else in the public API.

```ts
export type Role = 'user' | 'assistant' | 'system' | 'tool';
export type Modality = 'image' | 'audio' | 'video' | 'document';

export interface Message {
  role: Role;
  content?: string;
  toolCallId?: string;
  toolName?: string;
  parts?: MessagePart[];
}

export type MessagePart =
  | { type: 'text'; content: string }
  | { type: 'reasoning'; content: string }
  | { type: 'tool_call'; toolCallId: string; toolName: string; arguments?: string }
  | { type: 'tool_result'; toolCallId: string; result?: string }
  | { type: 'file'; fileId: string; mimeType?: string; modality: Modality }
  | { type: 'image_blob'; content: string; mimeType: string }            // base64
  | { type: 'uri'; uri: string; modality: Modality };

export interface Usage {
  inputTokens?: number;
  outputTokens?: number;
  reasoningTokens?: number;
  cacheCreationInputTokens?: number;
  cacheReadInputTokens?: number;
}

export interface Reasoning {
  content: string;
}
```

`Message.role` is mutually-exclusive with `parts` in the doc but is freely allowed in practice in the Python code — match that to avoid breaking parity.

---

## 6. OTel pipeline

### 6.1 Provider setup

The provider is a **process-wide singleton** in [`src/genai/provider.ts`](./src/genai/provider.ts), shared by every GenAI emitter in the SDK (the new Session/Turn/LLM classes today, a future piCodingAgent refactor tomorrow). The exporter always targets `/agents/otel/v1/traces` and is not user-replaceable; the **span processor**, however, is selectable via `init()`.

```ts
// src/genai/provider.ts (sketch)
export function getWeaveTracer(name: string): Tracer | NoopTracer {
  const client = getGlobalClient();
  if (!client) return NOOP_TRACER;                  // weave.init() not called → no-op

  if (!cached) {
    const [entity, project] = client.projectId.split('/');
    const endpoint  = `${client.traceServerApi.baseUrl}/agents/otel/v1/traces`;
    const apiKey    = getWandbConfigs().apiKey;
    const authHeader = `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`;

    const exporter = new OTLPTraceExporter({
      url: endpoint,
      headers: { Authorization: authHeader, project_id: client.projectId },
    });

    const processor = buildProcessor(exporter, client.settings.genai);  // see §6.1.1

    const provider = new BasicTracerProvider({
      resource: new Resource({ 'wandb.entity': entity, 'wandb.project': project }),
      spanProcessors: [processor],
    });

    process.once('beforeExit', () => provider.shutdown().catch(noop));
    cached = { provider };
  }
  return cached.provider.getTracer(name, SDK_VERSION);
}
```

A public **`flushWeaveOTel()`** helper delegates to `provider.forceFlush()` for tests and explicit-shutdown callers.

#### 6.1.1 Span-processor selection

Exposed in `weave.init()`:

```ts
await weave.init('entity/project', {
  genai: {
    spanProcessor: 'batch',                                  // default
    // OR: 'simple'
    // OR: SpanProcessor                                     // user-supplied instance
    batchOptions: {                                          // only when spanProcessor === 'batch'
      scheduledDelayMillis: 200,
      maxQueueSize: 2048,
      maxExportBatchSize: 512,
    },
  },
});
```

Selection rationale:

| Choice | When to use | Notes |
| :---- | :---- | :---- |
| `'batch'` (default) | Production agents, anything long-lived. | One HTTP POST per ~200 ms or ~512 spans. |
| `'simple'` | Tests, short-lived CLIs, deterministic-flush debugging. | One POST per span; trades throughput for predictability. |
| `SpanProcessor` instance | Power users who want a custom retry/queue or to fan out to multiple destinations. | Caller owns the processor lifecycle. |

The **exporter** stays non-configurable: it must hit `/agents/otel/v1/traces` for the server's `genai_otel_export` extractor to pick the spans up. A user-supplied `SpanProcessor` can wrap our exporter in whatever logic it wants but cannot replace it.

### 6.2 Span shape

| Concept | OTel span name | `gen_ai.operation.name` | Parent |
| :---- | :---- | :---- | :---- |
| Session | none — no span emitted | — | — |
| Turn | `invoke_agent` | `invoke_agent` | none (root → new trace) |
| LLM | `chat` | `chat` | current Turn |
| Tool | `execute_tool` | `execute_tool` | current LLM (if any) else current Turn |
| SubAgent | `invoke_agent` (nested) | `invoke_agent` | current Turn or LLM |

`Session` is **not** a span — it's a contextual grouping with a `conversation.id` attribute that gets attached to every emitted span underneath it. This matches the Python implementation and the server's `genai_conversations` materialized view.

### 6.3 Span hierarchy decision (tool nesting)

OTel GenAI semconv is **silent** on parent-child structure ([gen-ai-spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/), [gen-ai-agent-spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)). The Python SDK chose **flat by default, hierarchical if you nest**:

- `turn.tool()` makes the Tool a direct child of the Turn span (sibling of LLM).
- `llm.startTool()` makes the Tool a child of the LLM span.

We do the same. Implementation: `startTool` reads the current AsyncLocalStorage frame to pick its parent — if a `with`-equivalent `LLM` is on the stack it becomes parent, otherwise the `Turn`.

### 6.4 GenAI semconv attributes

Build on the relocated [`src/genai/semconv.ts`](./src/genai/semconv.ts). Keys we use:

- `gen_ai.conversation.id` — already in the file. Stamped on every span under a Session.
- `gen_ai.input.messages` / `gen_ai.output.messages` — **new**, added in PR 1. JSON-serialized message lists, matching Python.
- `wandb.entity`, `wandb.project` — resource attrs; already used in piCodingAgent.
- `weave.sdk.version`, `weave.sdk.language=node` — **new** resource attrs added in PR 2 for server-side fingerprinting (Q1 from §10.2, accepted).
- A `weave.session.*` namespace is reserved for future session-level metadata that doesn't fit GenAI semconv.

#### Message capture: attribute mode, not event mode

The OTel GenAI spec supports two encodings for messages: per-message events (`span.addEvent('gen_ai.user.message', ...)`) and bundled attributes (`gen_ai.input.messages` as a JSON string). **We use attribute mode**, matching the Python SDK ([weave/session/session_otel.py:225,229,318,324](../../weave/session/session_otel.py)). This is the load-bearing decision for cross-SDK parity:

- Same wire format → same `extract_genai_span()` server path handles both Python and TS clients.
- Same UI rendering — the Agents tab reads attributes, not events.
- piCodingAgent uses event mode for its own purposes (it's not bound to the Python SDK contract). We don't follow it here.

### 6.5 No-op when disabled

If `weave.init()` was never called, `getGlobalClient()` returns `undefined` and `getOrCreateGenAITracer()` returns a no-op tracer that creates non-recording spans. All `start*`/`end*`/`record`/`attach*` calls remain safe to invoke — they update local state but produce no network traffic. **No conditional logic at call sites is required**, matching the Python "no-op when tracing is off" design choice.

---

## 7. Context propagation

Reuse the existing `AsyncLocalStorage` pattern from `WeaveClient`. Three new stores (in [`src/genai/context.ts`](./src/genai/context.ts)):

```ts
const currentSession = new AsyncLocalStorage<Session>();
const currentTurn    = new AsyncLocalStorage<Turn>();
const currentLLM     = new AsyncLocalStorage<LLM>();
```

Top-level functions read these stores; `startTurn()` (no `session.` prefix) finds the parent via `currentSession.getStore()`, same for `startLLM()` and `startTool()`.

### 7.1 Semantics: `enterWith` + restore-on-end

Each `start*` calls `als.enterWith(this)` after capturing the previous value; the matching `end*` restores the previous value. This emulates Python's `ContextVar.set()` / `Token.reset()` behavior and keeps the two SDKs in lockstep:

```ts
class Turn {
  private _previousTurn?: Turn;

  static async create(opts: TurnOptions): Promise<Turn> {
    const turn = new Turn(opts);
    turn._previousTurn = currentTurn.getStore();
    currentTurn.enterWith(turn);
    return turn;
  }

  async end(opts?: { error?: Error }): Promise<void> {
    if (this._ended) return;                              // idempotent
    this._ended = true;
    if (opts?.error) this.span.recordException(opts.error);
    this.span.end();
    currentTurn.enterWith(this._previousTurn as Turn);    // restore
  }
}
```

The only behavioral quirk to know about: like Python contextvar, the new value propagates forward in the current async chain until `end()` runs. If a user starts a turn and never ends it, subsequent unrelated code on the same async chain will see that turn as `getCurrentTurn()`. This is exactly the Python behavior and we accept it — the `beforeExit` safety net (§8) auto-ends any turn left dangling.

### 7.2 Cross-module example (Pattern 4 in the original doc)

```ts
// dispatch.ts
const session = await weave.startSession({ agentName: 'wb-agent' });
const turn    = await weave.startTurn({ userMessage: prompt });
await runTurn();                                    // calls deep into other modules
await turn.end();
await session.end();

// loopingAgent.ts — no turn variable, no import from dispatch.ts
const llm = await weave.startLLM({ model: 'gpt-4o' });   // reads currentTurn via ALS
llm.output(response.text);
llm.usage = { inputTokens: 100, outputTokens: 50 };
await llm.end();
```

No `run(fn)` wrapper is needed; the implicit `enterWith` propagation handles cross-module lookup the same way Python's contextvar does.

---

## 8. Lifecycle & error handling

- **Span errors**: `end({ error })` sets `SpanStatusCode.ERROR` and records the exception via `span.recordException(error)`. If `end()` is called without an error, status is `OK` for LLM/Tool/SubAgent; `UNSET` for Turn (matches OTel default for "completed normally").
- **Auto-end on `beforeExit`**: a process-wide `beforeExit` handler walks every live `Turn`/`LLM`/`Tool` it tracked and force-ends them with a `weave.session.aborted = true` attribute. Then calls `provider.shutdown()`. This is the safety net for users who forgot `await session.end()`.
- **Reentrancy**: calling `end()` twice on the same instance is a no-op (idempotent), to match the `beforeExit` safety net plus user `try/finally`.
- **Background queue failures**: rely on OTel's `BatchSpanProcessor` retry semantics — no replication of the Weave SDK's "exit after 10 failures" rule.

---

## 9. Future directions

### 9.1 `await using` (TC39 Explicit Resource Management)

This is **not** the v1 surface but should land as a documented chapter once Node 22 is a hard floor. The same classes will implement `[Symbol.asyncDispose]`:

```ts
class Session {
  async [Symbol.asyncDispose]() { await this.end(); }
}
// then:
{
  await using session = await weave.startSession({ agentName: 'weather-bot' });
  await using turn    = await session.startTurn({ userMessage: 'Hi' });
  await using llm     = await turn.llm({ model: 'gpt-4o' });
  llm.output('hello');
}                                                    // implicit await llm.end(); await turn.end(); await session.end();
```

Constraints:

- Requires TypeScript ≥5.2 and Node ≥18.0.0 with `--harmony-explicit-resource-management`, default since Node 22.
- Our current `tsconfig.json` targets ES2022, so we'd need to bump `target` to `ES2023` or set `lib: ["esnext.disposable"]`. Worth doing as a follow-up PR when the floor moves.

The work to enable this is **two lines per class** (`[Symbol.asyncDispose]`), so it's a trivial follow-up — we just don't lead with it.

### 9.2 Publicly exposed OTLP exporter ("wrap, don't replace")

**Today.** A user-supplied `SpanProcessor` (via `settings.genai.spanProcessor`) fully owns the export pipeline — their processor receives spans directly and routes them wherever their own exporter says. This works for tests (`InMemorySpanExporter`) and for users who don't care about reaching the Weave Agents tab, but it leaves no clean path for *"I want custom queue/retry/fan-out logic **and** I want my spans to land in Weave."*

**Future.** Expose `buildOtlpExporter()` as a public helper (e.g. `getWeaveOTLPExporter()`). Users wanting custom processor logic could then wrap our exporter instead of replacing it:

```ts
const exporter = weave.getWeaveOTLPExporter();
const processor = new MyCustomBatchProcessor(exporter, { /* retry/queue opts */ });
await weave.init('entity/project', { genai: { spanProcessor: processor } });
```

**Why not now.** No user has asked for it; nothing in v1 needs it; adding it widens the public API surface (more support burden than the current branches). Deferred until a real use case shows up.

---

## 10. Resolved decisions and remaining open questions

### 10.1 Resolved (2026-05-12)

- **Naming.** Match Python: `LLM` class, `startLLM`, `getCurrentLLM`. Doc's `Step`/`Chat` not adopted.
- **Idiom.** Manual `start()` / `end({ error? })` primary. `await using` deferred to §9 chapter.
- **Session is not a span.** Client-side grouping only; `gen_ai.conversation.id` attribute propagates to every child span. Matches Python.
- **`logTurn` / `logSession`.** Deferred out of v1, but kept as the **immediate** follow-up PR (not far-future). See plan §11.
- **Cross-module context propagation.** Use `enterWith` + restore-on-end (§7.1). No `session.run(fn)` / `turn.run(fn)` helper. No feature gap identified.
- **Dedicated OTel exporter.** Hard requirement — must hit `/agents/otel/v1/traces`. User cannot replace the exporter. A user-installed `TracerProvider` is **not** reused; we always install our own.
- **Span-processor selection.** Exposed in `init()`: `'batch'` (default) / `'simple'` / user-supplied `SpanProcessor` instance. See §6.1.1.

### 10.2 Round 2 (resolved 2026-05-12)

- **Q1.** Resource attributes ✅ accepted — include `weave.sdk.version` and `weave.sdk.language=node`. Wired in PR 2 alongside the existing `wandb.entity` / `wandb.project` resource attrs.
- **Q2.** Message capture mode ✅ resolved — **attribute mode only**, matching Python. (My earlier "Python supports both" claim was incorrect; Python uses only the JSON-attribute encoding, never `span.add_event`. See §6.4.)
- **Q3.** `flushWeaveOTel()` ✅ exported from the top-level `weave` index (not gated behind a non-existent `weave/genai` subpath). Tests need it; production callers using `'simple'` processor or doing manual shutdown will need it too.

### 10.3 Still open

_(none right now — surface here if anything new comes up during PR 1.)_

---

## 11. Implementation plan

Each phase is sized for one reviewable PR (~50–700 LOC excluding tests). PRs land in order; each is functional on its own but the public API is gated until PR 4 to avoid half-built surface area appearing in published npm builds.

**v1 = PRs 1 through 5.** PR 6 (`logTurn`/`logSession`) and PR 7 (`await using` + polish) land as immediate follow-ups, not v1 blockers.

### PR 1 — Relocate semconv, add types and new semconv keys (~350 LOC) — **LANDED**

**Goal:** Land the shape of the world without any runtime behavior. Combines the semconv-file relocation (mechanical) with the new type definitions.

As shipped, PR 1 relocated the semconv file to `src/otel/semconv.ts` under a separate `src/otel/` folder. PR 2 collapsed that folder back into `src/genai/` as a course-correction (see PR 2's "Consolidation refactor" note below). End-state after PR 2: the file lives at `src/genai/semconv.ts`.

- Relocate the shared semconv file (mechanical, must land before any new consumer).
- **Add new types:** [`src/genai/types.ts`](./src/genai/types.ts) with `Message`, `MessagePart`, `Usage`, `Reasoning`, `Role`, `Modality`.
- **Extend the semconv file** with new keys: `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.usage.reasoning_tokens`, `weave.sdk.version`, `weave.sdk.language`, plus any token / cache keys missing from the current set.

**Touches piCodingAgent**: one import line. No behavior change.

### PR 2 — Shared GenAI OTel infrastructure (~400 LOC)

**Goal:** Process-wide singleton `TracerProvider` under [`src/genai/`](./src/genai/), shared by every GenAI emitter (the future piCodingAgent refactor will consume it too).

**Consolidation refactor (part of this PR).** PR 1 introduced a separate `src/otel/` folder, intended as "shared OTel infrastructure" potentially reusable by non-GenAI emitters. On reflection during PR 2 implementation, every artifact in this stack is GenAI-specific (semconv namespace, provider endpoint, flush helper), and the SDK has no non-GenAI OTel consumer to justify the split. PR 2 therefore collapses `src/otel/*` → `src/genai/*` as part of its diff: `semconv.ts` moves, the new provider/flush land directly under `src/genai/`, and piCodingAgent's import path updates one more time to `'../genai/semconv'`.

- Add [`src/genai/provider.ts`](./src/genai/provider.ts) — singleton from §6.1, targeting `/agents/otel/v1/traces`. Exports `getWeaveTracer(name)`. The `beforeExit` hook lives here too, to avoid a circular import with `flush.ts`.
- Add [`src/genai/flush.ts`](./src/genai/flush.ts) — `flushWeaveOTel()` helper, **re-exported from top-level [`src/index.ts`](./src/index.ts)** (per resolved Q3).
- Wire resource attrs: `wandb.entity`, `wandb.project`, `weave.sdk.version`, `weave.sdk.language='node'` (per resolved Q1).
- Extend `Settings` to accept the `settings.genai.spanProcessor` option (§6.1.1).
- The no-op fallback for "weave.init() not called" is implemented inline in `provider.ts` via a standalone `BasicTracerProvider` with `AlwaysOffSampler`. (The design previously listed `src/genai/noop.ts` here; that file is reserved for no-op **span helpers** consumed by PR 3 Session/Turn/LLM classes, if needed.)
- Tests: use `InMemorySpanExporter` (already pulled in by piCodingAgent tests). Assert singleton, resource attrs, user-supplied processor end-to-end, default + `'simple'` smoke, `flushWeaveOTel` behavior.

**Does NOT modify** `src/integrations/piCodingAgent.ts` semantics beyond the import-path update — endpoint and provider migration remain a separate out-of-scope refactor.

### PR 3 — Core classes: Session, Turn, LLM, Tool, SubAgent (manual start/end) (~700 LOC)

**Goal:** The real-time hierarchical surface, **chained form only** (`session.startTurn(...)`, `turn.llm(...)`, etc.). No top-level `weave.startLLM()` shortcuts yet — that comes in PR 4 once ALS is wired.

- Classes in `src/genai/{session,turn,llm,tool,subagent}.ts`.
- Each class:
  - Async `create()` factory that opens the OTel span via `getWeaveTracer('weave-genai')` from PR 2.
  - `end({ error? })` ends the span, sets status, idempotent.
  - Owns its child `start*` methods.
- Span name + attributes wired per §6.2 / §6.4.
- Tests: per-class, assert emitted span name + GenAI semconv attrs via `InMemorySpanExporter`.

**Definition of done:** can fully trace a turn end-to-end using the chained form. No ALS yet.

### PR 4 — Top-level entry points + AsyncLocalStorage context (~500 LOC)

**Goal:** Public API matches §4.3.

- Add [`src/genai/context.ts`](./src/genai/context.ts) with the three `AsyncLocalStorage` stores plus the `enterWith` + restore-on-end mechanism (§7.1).
- Wire each class's `create()` / `end()` to install / restore its ALS frame.
- Add `weave.startSession`, `startTurn`, `startLLM`, `startTool`, `startSubagent`, `endSession`, `endTurn`, `endLLM`, `getCurrentSession`, `getCurrentTurn`, `getCurrentLLM` and re-export from [`src/index.ts`](./src/index.ts).
- Tests: cross-module pattern (Pattern 4) — start a turn in fn A, attach an LLM in fn B, assert parent-child + ALS restore on end.

**Definition of done:** three of the four "patterns" from the Python doc work — context manager (TS equivalent via try/finally), manual start/end, cross-module via ALS. Batch is PR 6.

### PR 5 — LLM enrichment surface (~400 LOC)

**Goal:** the doc's "nice-to-have" methods.

- `llm.output(content)`, `llm.think(content)`.
- `llm.attachMedia({ content | uri | fileId, mimeType, modality })`, `llm.attachMediaUrl(url, { modality })`.
- `llm.record({ inputMessages?, outputMessages?, usage?, reasoning? })`.
- Tests: assertion of emitted span events / attributes matches Python output side-by-side.

**Definition of done:** v1 ready to ship — Patterns 1, 2, 4 fully working; data-recording surface complete.

---

### Follow-up PRs (post-v1, soon, not far-future)

#### PR 6 — Batch logging: `logTurn`, `logSession` (~300 LOC)

- Add [`src/genai/batch.ts`](./src/genai/batch.ts).
- Synthesize spans with explicit timestamps from user-supplied messages/steps, end them immediately, flush.
- Tests: ingest a known fixture, assert correct number of spans + correct conversation-id linkage.

**Definition of done:** Pattern 3 (imperative batch) works; users can backfill historical conversations.

#### PR 7 — Polish, examples, `await using` chapter (~200 LOC + docs)

- Examples directory: `examples/genai-tracing/{weather-bot,cross-module,batch-import}.ts`.
- README.md section for `weave.startSession(...)`.
- Add `[Symbol.asyncDispose]` to each class plus a feature-detect doc note (§9).
- Optional: a `wrapOpenAI`-style integration that auto-emits LLM spans inside the active turn (a natural follow-up but its own design problem).

---

## 12. References

- [Python design doc (`original_design_doc.md`)](./original_design_doc.md) — the source of truth for the data model and four usage patterns.
- [Python implementation: `weave/session/`](../../weave/session/)
- [Server-side OTel ingest: `weave/trace_server/opentelemetry/genai_extraction.py`](../../weave/trace_server/opentelemetry/genai_extraction.py)
- [ClickHouse schema migration: `weave/trace_server/migrations/030_add_agent_tables.up.sql`](../../weave/trace_server/migrations/030_add_agent_tables.up.sql)
- [OTel GenAI semconv — agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [OTel GenAI semconv — chat & execute_tool](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [Existing OTel pattern: `src/integrations/piCodingAgent.ts`](./src/integrations/piCodingAgent.ts)
- [Existing GenAI key bundle: `src/integrations/common/genai.ts`](./src/integrations/common/genai.ts)
