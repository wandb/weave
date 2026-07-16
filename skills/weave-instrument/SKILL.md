---
name: weave-instrument
description: >-
  Add Weave (Weights & Biases) observability to an LLM or agent codebase. This covers calling
  `weave.init()`, setting up authentication, and choosing between OTEL auto-instrumentation and the
  explicit Conversation SDK agent-logging APIs (Turn, LLM, Tool, SubAgent), based on the libraries the code
  already uses. Works for Python and TypeScript/Node. Use this whenever the user wants to instrument,
  trace, or add observability, logging, or monitoring to an agent, chatbot, RAG pipeline, or LLM app.
  This includes phrasings like "log my agent to weave", "add agent tracing", "get my agent into the
  Weave Agents tab", "instrument this with the weave session sdk", "trace my tool calls", or "set up
  weave logging", even when the user does not name a specific API.
---

# Weave Instrument

Your job is to add Weave tracing to someone's LLM or agent code so their runs show up in the W&B Weave
UI. Fit the approach to their codebase instead of applying a one-size-fits-all template.

This skill works for any agent, whatever libraries it uses or none at all. Choose the approach based
on two things:

- the telemetry *shape* the user wants;
- the *structure* of their code.

Never choose based on whether you recognize the framework. There are two mechanisms, and one of them
always applies when tracing is allowed.

1. **Conversation SDK (formerly Session SDK)** is the universal path. You wrap the agent's own structure
   with `Turn`, `LLM`, `Tool`, and `SubAgent` spans. It works for any agent, whether a custom loop, an
   unknown framework, or one that Weave does not map, and it always produces agent-shaped traces. Use
   it whenever you cannot *prove* that auto-instrumentation emits the shape the user needs.
2. **OTEL auto-instrumentation** is an optimization for libraries that Weave already recognizes.
   `weave.init()` alone captures them, with no per-call code. Use it only when the installed version of
   Weave auto-instruments the user's library *and* the shape it emits is the one they want.

Both paths produce OTEL spans. Agent-shaped spans land in Weave's **Agents** tab; flat call traces
land in the **Calls** tab. The choice between the Conversation SDK and OTEL auto-instrumentation is driven
by the shape you need and the structure of the code, not by framework identity. See
`references/decision.md` for the full procedure.

## Reference material (read the one you need)

Keep this file in context, and open a reference only when you reach the step that needs it. Each one is
a precise, source-grounded cheat-sheet. Do not reconstruct the API from memory: the surface is new and
easy to get subtly wrong.

- `references/decision.md` is the full decision procedure (shape, then structure, then probe, then
  strategy) and the coverage examples. Read it during "Choose a strategy" below.
- `references/session_sdk_python.md` covers the Python Session SDK: the classes, the context-manager
  pattern, the batch path, and the data types. Read it when instrumenting Python with the Session SDK.
- `references/session_sdk_typescript.md` covers the TypeScript Session SDK: the `start*` functions, the
  try/finally pattern, async init, and concurrency. Read it when instrumenting TypeScript or Node.
- `references/otel_auto.md` covers the OTEL auto path: what `weave.init()` captures on its own, the
  default-mode gotchas, and the framework caveats. Read it when OTEL auto is the chosen strategy.
- `references/otel_endpoint.md` covers exporting OTEL directly to Weave's endpoint (the raw-OTEL
  path): the environment-variable config, and how to add Weave's exporter to an app's own
  `TracerProvider`. Read it when the app already emits OTel spans or owns its OTel setup.

## Workflow

Work through these steps in order. Steps 1 and 4 always run. Use your judgement for steps 2 and 3.

### 1. Establish the connection (always; confirm before editing widely)

A user's traces need three things:

1. the package installed;
2. credentials present;
3. a `weave.init()` call.

Settle these first. There is no point instrumenting code that cannot authenticate.

- **Install or confirm the package.** In Python, the package is `weave` on PyPI (`pip install weave`,
  or add it to their manifest). The current Conversation SDK names and `set_attributes` need
  `weave>=0.53.0`; older v0.52 builds use deprecated Session aliases. In Node, run
  `npm install weave`. The OTEL dependencies ship bundled in both, so the user adds nothing extra.
- **Authentication is the user's job, not yours, so never handle their key.** A W&B API key is a
  secret, and it must not enter your context or the repo. Tell the user to authenticate in their own
  terminal: set `WANDB_API_KEY` (from https://wandb.ai/authorize), or run `wandb login` (Python) or
  `await weave.login(key)` once (Node). You may check *that* a key is reachable (the env var is set,
  or `~/.netrc` has an `api.wandb.ai` entry), but never read or print its value, and never write it
  into source code or into a committed `.env`.
- **Get the project name.** Ask for it as `entity/project`, or as just `project` to use their default
  entity. Show them the URL their traces will land at up front,
  `https://wandb.ai/<entity>/<project>/weave`, so there are no surprises about where the data goes.
- **Add `weave.init("entity/project")` once** at each real entry point: the `main()` function, the
  server startup, or the top of a script. Do not put it inside a hot loop. In Python:
  `import weave; weave.init("entity/project")`. In Node: `await weave.init('entity/project')`. It is
  async, so you must await it before any traced work. If the app installs its own global
  `TracerProvider`, `weave.init()` backs off and will not export to Weave; add Weave's exporter to
  their provider instead (see `references/otel_endpoint.md`). The calls are safe no-ops when init or
  auth is missing, so leaving instrumentation in place never breaks their program.

Before touching many files, state the plan in a sentence or two ("I'll use the Conversation SDK to wrap
your agent loop in `agent.py`, and add `weave.init` in `main.py`") and let the user redirect you.
Instrumenting edits their source, so a quick checkpoint beats a large surprise diff.

### 2. Survey the codebase

You cannot choose a strategy without knowing what they run. Find the following.

- **The languages:** Python, TypeScript/Node, or both.
- **The LLM and agent libraries.** Grep the imports and read the dependency manifest, and note the
  *exact* package. The names differ by language, so check the manifest that applies. Step 3 is where
  you resolve whether the installed Weave auto-instruments each one, and whether it emits agent shape
  or flat calls, so do not assume from the name.
  - Python (`pyproject.toml` / `requirements.txt`): `openai`, `anthropic`, `langchain`,
    `openai-agents` (`import agents`), `claude_agent_sdk`, `google.adk`, `crewai`, `llama_index`, and
    so on.
  - TypeScript (`package.json`): `openai`, `@anthropic-ai/sdk`, `@google/genai`, `@openai/agents`,
    `@anthropic-ai/claude-agent-sdk`, `langchain`, `llamaindex`, and so on.
- **The agent's shape.** Is there a hand-rolled loop (a `while` that calls the model, dispatches
  tools, and repeats)? Where is each model call? Where are tools dispatched? Is there delegation to
  sub-agents? These map directly onto `Turn`, `LLM`, `Tool`, and `SubAgent`.
- **Existing OTel or telemetry.** Look for any `TracerProvider`, `opentelemetry` setup, or a competing
  tracing vendor. This affects where you place init, and whether auto-capture already flows somewhere.

### 3. Choose a strategy, then instrument

Open `references/decision.md` for the full procedure. The short version is to decide by shape, probe
for coverage, and fall back to the universal path.

1. **What shape does the user want?** An agent-shaped tree (the Agents tab), or flat model-call traces
   (the Calls tab)?
2. **What is the agent's structure?** The turn boundary, the model calls, tool dispatch, sub-agents,
   and any streaming or concurrency. This is what you will instrument, and it exists whatever the
   library is.
3. **Probe auto-coverage.** Does the *installed* Weave auto-instrument their library (read the
   registry: `INTEGRATION_MODULE_MAPPING` in Python, `integrations/hooks.ts` in TypeScript), and does
   it emit the shape from step 1? Do not trust a memorized framework list.
4. **Choose.** If auto-coverage emits the wanted shape, use **OTEL auto** (`weave.init()` alone; do
   not also hand-wrap, or you will double-log). Otherwise, use the **Conversation SDK** and map the
   structure from step 2. If the app already emits OTel spans or owns a `TracerProvider`, use **raw
   OTEL export** (`references/otel_endpoint.md`). A mixed approach is normal. Apply any caveats that
   `references/otel_auto.md` triggers (the gotcha lookup).

When you instrument with the Conversation SDK, the mapping is the heart of the work.

- **`Turn`** is one cycle of the top-level agent loop handling one user input, and it opens its own
  trace root. Wrap the loop body, not the whole program.
- **`LLM`** is one model API call. Wrap the call site, and record the input messages, the output, and
  the token usage when it is available.
- **`Tool`** is one tool or function execution. Wrap the dispatch, and record the name, the arguments,
  and the result.
- **`SubAgent`** is a delegated or nested agent invocation. Wrap the sub-call.

Map to the agent's *real* semantic boundaries. Not every helper function is a `Tool`, and a retry of
one model call is still one `LLM`. Over-instrumenting produces noisy, misleading traces.

**Never change behavior.** This is instrumentation, so the program must do exactly what it did before.
Preserve return values and exceptions. Keep spans closed on every path. Python context managers and
TypeScript try/finally do this for you, so use them rather than bare `start`/`end` calls, which can
leak an open span when an exception is raised. Do not reorder the user's logic or gate it on a span. If
you cannot wrap cleanly without restructuring their code, prefer the batch path (Python `log_turn` or
`log_conversation`; see the reference) or flag it to the user, rather than forcing an invasive rewrite.

### 4. Verify

Instrumentation you cannot see is worthless, so confirm that traces actually arrive.

- If the app is runnable and credentials are present, run a minimal path (their quickstart, a smoke
  test, or a tiny script that exercises one turn) and confirm a trace shows up at the project URL.
  Both the Python and Node `weave.init()` print `View Weave data at
  https://wandb.ai/<entity>/<project>/weave` at startup, so watch for that line. (The env-var OTEL
  export prints nothing, so open the project URL there.)
- **The strongest check is the span *shape*, not the presence of code.** Where you can run a smoke
  path, capture the emitted spans with an in-memory OTel exporter (no credentials needed) and confirm
  the operations are what you intended: a `gen_ai.operation.name` of `invoke_agent` for turns and
  sub-agents, `chat` for model calls, and `execute_tool` for tools, with the turn nesting its LLM and
  tool spans. This is also how you confirm that an *auto* strategy emits agent shape rather than flat
  calls, since registry membership alone does not prove it.
- If you cannot run it (because of missing provider keys or heavy setup), give the user an exact
  copy-paste command to run themselves, and tell them what to look for: the `View Weave data at
  https://wandb.ai/.../weave` line that `weave.init()` prints, and a trace in the Agents or Calls tab.
- If nothing shows up, the usual causes are auth not actually set in the run's environment, the Python
  plain-`openai` default-mode gotcha, init placed after the work it should wrap, or (in Node ESM) the
  missing `--import=weave/instrument` preload. The OTEL reference lists these.

## Hygiene checklist

- The API key is never touched, read, printed, or committed.
- Behavior is unchanged: the same outputs, the same exceptions, and spans always closed.
- No double-instrumentation. Do not add Conversation SDK spans around calls a framework already
  auto-captures, or you will get duplicate traces.
- `weave.init()` appears once per entry point, ordered correctly relative to any user OTel setup.
- The version is pinned high enough for the APIs you used.
- The user knows the destination URL and how to verify.
