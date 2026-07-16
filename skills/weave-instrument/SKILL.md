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

This skill works for any agent, whatever libraries it uses or none at all. Establish three things
before choosing an approach:

- the data policy that decides whether a trace, or its content, may leave the process;
- the telemetry *shape* the user wants;
- the *structure* of their code.

The data policy gates whether instrumentation may run. Shape and structure choose the mechanism.
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
- `references/session_sdk_python.md` covers the Python Conversation SDK: the classes, the context-manager
  pattern, the batch path, and the data types. Read it when instrumenting Python with the Conversation SDK.
- `references/session_sdk_typescript.md` covers the TypeScript Conversation SDK: the `start*` functions, the
  try/finally pattern, async init, and concurrency. Read it when instrumenting TypeScript or Node.
- `references/otel_auto.md` covers the OTEL auto path: what `weave.init()` captures on its own, the
  default-mode gotchas, and the framework caveats. Read it when OTEL auto is the chosen strategy.
- `references/otel_endpoint.md` covers exporting OTEL directly to Weave's endpoint (the raw-OTEL
  path): the environment-variable config, and how to add Weave's exporter to an app's own
  `TracerProvider`. Read it when the app already emits OTel spans or owns its OTel setup.
- `references/failure_modes.md` is the observed-failure catalog: consent bypass, inert deployment
  config, disconnected or hollow model calls, post-hoc tool spans, missing semantic outcomes,
  credential/endpoint drift, lost feedback/ref correlation, and tests that prove only wiring. Read it
  when repairing existing instrumentation and during verification.

## Workflow

Work through these steps in order. Steps 1 and 4 always run. Use your judgement for steps 2 and 3.

### 1. Establish the connection (always; confirm before editing widely)

A usable Weave connection needs four things:

1. the package installed;
2. the application's policy permits the intended export;
3. project, endpoint, and the appropriate credentials reach the running process; and
4. `weave.init()` or the exporter consumes those exact settings.

Before editing instrumentation, identify the application's data-sharing policy. There is no point
instrumenting code that cannot authenticate, and it is unsafe to export content that the application
would not otherwise share.

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
- **Keep tracing identity isolated.** A service may already use `WANDB_API_KEY` for a different W&B
  or proxy identity. Wire a dedicated tracing setting from its secret store and scope any temporary
  `WANDB_API_KEY` override to Weave initialization, restoring the process environment afterward. Do
  not replace a process-wide credential merely because `weave.init()` reads it.
- **Trace configuration end to end.** For a deployed service, follow the project, tracing credential,
  base URL, and trace-server URL from values/secrets through the rendered manifest, process
  environment, application accessor, and initialization call. A new accessor with an empty default
  is an explicit disabled mode until deployment sets it; its presence is not runtime wiring. If the
  application uses prefixed setting names, bridge them to the exact SDK inputs only around
  initialization and restore the previous environment afterward.
- **Get the project name.** Ask for it as `entity/project`, or as just `project` to use their default
  entity. Show them the URL their traces will land at up front,
  `https://wandb.ai/<entity>/<project>/weave`, so there are no surprises about where the data goes.
- **Establish the data boundary.** Find per-request consent, tenant policy, content-capture flags,
  redaction, and existing tracing enable/disable checks. When policy denies tracing, skip creating
  the turn and all descendants. When metadata-only tracing is allowed, omit prompts, outputs, tool
  arguments, and tool results (Python conversations support `include_content=False`) and verify the
  exported payload. Missing auth or missing `weave.init()` is not a consent mechanism. In Python,
  Conversation SDK spans can still reach an application-owned OTel provider; in Node, initialization is
  process-wide, so it cannot express a later per-turn denial.
- **Add `weave.init("entity/project")` once** at each real entry point: the `main()` function, the
  server startup, or the top of a script. Do not put it inside a hot loop. In Python:
  `import weave; weave.init("entity/project")`. In Node: `await weave.init('entity/project')`. It is
  async, so you must await it before any traced work. In Python, if the app installs its own global
  `TracerProvider`, `weave.init()` backs off and will not add a Weave exporter; add Weave's exporter
  to that provider instead (see `references/otel_endpoint.md`). Instrumentation must preserve
  program behavior, but do not rely on absent init/auth to suppress spans or protect content.

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
- **The real lifecycle boundaries.** Locate the actual awaited model request and actual tool/function
  execution, not only the aggregated result returned later. Find streaming consumption, retries,
  timeouts, exceptions, cancellation, and the representation of returned terminal states.
- **The data policy and auth owners.** Trace the consent/content decision into the worker that runs
  the turn. Identify which component owns each W&B credential and whether the process already has a
  distinct W&B identity.
- **Downstream trace contracts.** Search for persisted call/turn refs, deep links, feedback routes,
  and retroactive recovery. Emitting a new span is not a complete migration if the application can no
  longer find that span afterward.
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
  trace root. Apply the policy gate outside this boundary, then wrap the loop body, not the whole
  program.
- **`LLM`** is one model API call. Keep the span open across the real request/stream, and record input
  messages, output, usage, response identity, and errors. A generic Calls-tab patch is not proof of
  a child `chat` span; assert parent and trace ids.
- **`Tool`** is one tool or function execution. Keep the span open across the real dispatch so its
  duration, exception, timeout, and cancellation are truthful. Replaying completed tool entries into
  new spans records serialization time, not execution time.
- **`SubAgent`** is a delegated or nested agent invocation. Wrap the sub-call.
- **`Outcome`** closes the semantic turn. Before the turn span ends, record non-exception terminal
  states such as completed, errored, cancelled, or permission-required with stable attributes. A
  context manager records raised exceptions, but it cannot infer an error returned as data.

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

Open `references/failure_modes.md` when repairing existing instrumentation. Its probes are mandatory
for any matching condition.

- **Probe startup configuration.** Run the real entry point with synthetic marker configuration. For a
  deployed service, assemble or render that environment from the same values, manifests, and secret
  references used in deployment. Capture the project, destination, and credential *source* consumed by
  initialization without printing a key. Assert that enabled startup cannot silently no-op or inherit
  ambient auth/endpoint state, that disabled startup is intentional, and that temporary SDK aliases
  are restored even when initialization fails.
- If the app is runnable and credentials are present, run a minimal path (their quickstart, a smoke
  test, or a tiny script that exercises one turn) and confirm a trace shows up at the project URL.
  Both the Python and Node `weave.init()` print `View Weave data at
  https://wandb.ai/<entity>/<project>/weave` at startup, so watch for that line. (The env-var OTEL
  export prints nothing, so open the project URL there.)
- **The strongest check is the span *shape*, not the presence of code.** Where you can run a smoke
  path, capture the emitted spans with an in-memory OTel exporter (no credentials needed) and confirm
  the operations are what you intended: a `gen_ai.operation.name` of `invoke_agent` for turns and
  sub-agents, `chat` for model calls, and `execute_tool` for tools, with the turn nesting its LLM and
  tool spans. Assert exact parent span ids and trace ids, plus complete content/usage fields that are
  part of the contract. For streaming adapters, make a local transport emit a tool-selecting
  completion and a final completion, then assert exact input/output messages, structured tool calls,
  response id/model, usage, and finish reasons. A correctly nested span containing only output text is
  still broken. This is also how you confirm that an *auto* strategy emits agent shape rather than
  flat calls, since registry membership alone does not prove it.
- **Run negative controls.** A policy-denied turn must emit zero spans. A sleeping tool must have a
  span covering the sleep; a raising tool must export error status without changing the exception. A
  returned errored/cancelled result must carry its outcome before the turn closes. Preserve
  orthogonal result facts too: a nominally completed result that asks questions or requests
  permission must export those fields rather than collapsing them into the terminal enum. A model
  request inside a turn must not appear only as a separate root call. Tests that merely assert
  `weave.init()` or a patcher was called do not verify instrumentation.
- If the old integration returned or persisted a trace reference, exercise its real consumer: save
  the new reference, build the deep link, attach feedback, and simulate the recovery path after an
  initial write failure.
- If you cannot run it (because of missing provider keys or heavy setup), give the user an exact
  copy-paste command to run themselves, and tell them what to look for: the `View Weave data at
  https://wandb.ai/.../weave` line that `weave.init()` prints, and a trace in the Agents or Calls tab.
- If nothing shows up, the usual causes are auth not actually set in the run's environment, the Python
  plain-`openai` default-mode gotcha, init placed after the work it should wrap, or (in Node ESM) the
  missing `--import=weave/instrument` preload. The OTEL reference lists these.

## Hygiene checklist

- The API key is never touched, read, printed, or committed.
- The tracing credential does not overwrite another process-wide W&B identity.
- Deployment-like startup supplies the intended project, credential source, and endpoint to the SDK;
  enabled tracing cannot silently default to a no-op or ambient configuration.
- The application policy gates the complete turn tree; metadata-only mode contains no prompt,
  response, tool argument, or tool result content.
- Behavior is unchanged: the same outputs, the same exceptions, and spans always closed.
- No double-instrumentation. Do not add Conversation SDK spans around calls a framework already
  auto-captures, or you will get duplicate traces.
- Every LLM and tool span is a child of the intended turn, not a disconnected Calls-tab root.
- Every LLM span contains the complete request and completion contract, including structured tool
  calls, response identity/model, usage, and finish reasons when the provider supplies them.
- Live spans cover the actual work; batch/post-hoc spans are used only when live boundaries are truly
  unavailable and do not claim real execution latency or exception capture.
- Returned terminal states, errors, questions, and permission requests are observable before the turn
  span closes, including valid combinations that are not represented by one enum value.
- Persisted trace references, deep links, feedback, and recovery flows still work when they were part
  of the previous integration contract.
- `weave.init()` appears once per entry point, ordered correctly relative to any user OTel setup.
- The version is pinned high enough for the APIs you used.
- Verification includes a policy-denied negative control and exact topology/lifecycle assertions.
- The user knows the destination URL and how to verify.
