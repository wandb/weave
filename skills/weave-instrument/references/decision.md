# Choosing a strategy

Decide by the **span shape** the user wants and the **structure** of their code. Never decide by
recognizing a framework. The framework names below are *examples*; the source of truth is what the
*installed* Weave auto-instruments, which you check in step 3.

The invariant: detect the structure, choose the least-manual mechanism that emits the required shape,
then verify the emitted spans.

There are three mechanisms.

- **Session SDK** (`Turn`, `LLM`, `Tool`, `SubAgent`) is **universal**. It works for any agent,
  whether a custom loop, an unknown framework, or none, and it is always agent-shaped. Use it as the
  default whenever auto cannot be *proven* to emit the needed shape.
- **OTEL auto** (`weave.init()` alone) is an **optimization** for libraries that Weave recognizes. Use
  it only when the installed Weave auto-instruments the library *and* the shape it emits is the one
  wanted.
- **Raw OTEL export** applies when the app *already emits* OTel GenAI spans, whether from its own
  `TracerProvider` or from a third-party instrumentor such as OpenInference, OpenLLMetry, or Logfire.
  Point that pipeline at Weave's endpoint; no Weave SDK call is needed. This is also the fix when a
  global `TracerProvider` already exists, because `weave.init()` then backs off. See
  `otel_endpoint.md`.

## Procedure

1. **What shape is wanted?** An agent-shaped tree goes to the Agents tab. Flat model-call traces
   ("just my LLM calls") go to the Calls tab.
2. **What is the structure?** The turn boundary (one input maps to one cycle), the model calls, tool
   dispatch, sub-agents, and any streaming or concurrency. This is what you instrument, and it exists
   whatever the library is.
3. **Probe auto-coverage.** Do not rely on a memorized list; it can go stale. Check whether the
   installed Weave auto-instruments this library, and in what shape. In Python, read
   `weave.integrations.patch.INTEGRATION_MODULE_MAPPING`. In TypeScript, read `integrations/hooks.ts`
   or `Symbol.for('_weave_{cjs,esm}_instrumentations')`. Membership means "patchable", not
   "agent-shaped" or "active", so confirm with the span-shape check (SKILL.md step 4) wherever you can
   run it.
4. **Choose.** If coverage emits the wanted shape, use **OTEL auto** (`weave.init()` plus auth; do not
   also hand-wrap, or you double-log). If there is no coverage, an unknown library, or the wrong
   shape, use the **Session SDK** and map step 2. If the app already emits OTel GenAI spans or owns a
   `TracerProvider`, use **raw OTEL export** (`otel_endpoint.md`); `weave.init()` will not auto-attach
   to an existing provider. A **mixed** approach is normal: auto for the covered parts, and the
   Session SDK around bespoke orchestration.
5. **Verify the emitted spans** (SKILL.md step 4).

## Auto-coverage examples (illustrative, not an allow-list)

- **Agent-shaped, lands in the Agents tab, no extra code:** the OpenAI Agents SDK (Python
  `import agents` / Node `@openai/agents`), the Claude Agent SDK (Python `claude_agent_sdk` / Node
  `@anthropic-ai/claude-agent-sdk`), and Google ADK (`google.adk`, Python; with an import-order
  caveat).
- **Flat traces, land in the Calls tab:** plain LLM SDKs and framework hooks. In Python: `anthropic`,
  `mistralai`, `groq`, `litellm`, `cohere`, Google GenAI and Vertex, `huggingface_hub`, `instructor`,
  `langchain`, `llama_index`, `crewai`, `autogen`, `smolagents`, and `dspy`. In Node: `openai`,
  `@anthropic-ai/sdk`, and `@google/genai`. If you want agent shape from these, use the Session SDK.
- **Not covered, so use the Session SDK:** hand-rolled loops, any library not in the registry, and
  plain `openai` in Python under default settings (a gotcha; see `otel_auto.md`). Node plain `openai`
  *is* auto-captured, though ESM needs the preload flag.

## The Session SDK is universal, but it is a tree (not a graph)

The Session SDK models Session, then Turn (`invoke_agent`), then a set of LLM (`chat`), Tool
(`execute_tool`), and SubAgent (`invoke_agent`) spans. It covers loops, unknown frameworks, streaming
(hold the LLM span open, accumulate, then close it), sub-agents, async work (Python contextvars, or
TypeScript `runIsolated`), and post-hoc logging (`log_turn` / `log_session`, Python only; the TS SDK
has no `log*` batch functions).

State its limits; do not hide them. You project DAGs onto a tree. Parallel TypeScript model calls in
one async chain need `runIsolated`. Python thread or queue boundaries need explicit wrapping. And if
there is no observable boundary, that content cannot be captured, so flag it.

## When you are unsure

- "Agents tab", or "turns and tools": use the Session SDK, unless the probe proves the library
  auto-emits agent shape.
- "Just trace my LLM calls": use auto (`weave.init()`), and handle the Python plain-`openai` gotcha.
- On an auto-mapped agent framework: prefer auto, since it is less code and is robust to version
  changes. Use the Session SDK only for structure or attributes that auto does not emit.
