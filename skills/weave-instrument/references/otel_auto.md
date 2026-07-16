# OTEL auto-instrumentation

`weave.init()` registers import hooks that auto-patch supported libraries, with no per-call code. This
file covers the *gotchas*: the conditions that make auto-capture silently emit nothing, or the wrong
shape.

## Gotcha lookup (match the detected condition)

| Condition | Fix |
|---|---|
| Python, plain `openai`, default `use_otel_v2=True` | `patch_openai()` after init, or `WEAVE_USE_OTEL_V2=false`, or Session SDK `LLM` spans |
| Python, `import google.adk` *after* `weave.init()` | import ADK before init, or call `patch_google_adk()` |
| Python, a global `TracerProvider` already installed | init backs off, so add Weave's exporter to their provider (`otel_endpoint.md`), or use the Session SDK |
| Node, ESM, relying on auto-patch | launch with `node --import=weave/instrument` |
| An auto agent framework, but agents are unnamed or share one generic name | `weave.conversation.agent_name_override(...)` |
| Auto already emits agent shape | do not also wrap it with the Conversation SDK, or it double-logs |

## Python: plain `openai` is not auto-patched (the most common "no traces")

Under the default `use_otel_v2=True`, the import hook deliberately skips `openai`:

```python
import weave, openai
weave.init("entity/project")
openai.chat.completions.create(...)   # NOT traced by default
```

The fix depends on intent. For the **Calls tab**, call `weave.integrations.patch_openai()` after init
(or set `WEAVE_USE_OTEL_V2=false`). For the **Agents tab**, use Session SDK `LLM` spans. This is
Python-only; Node auto-captures plain `openai`.

## Python: Google ADK import order

The hook in `weave.init()` matches *root* modules, so `import google.adk` (root `google`) does not
trigger after init. Import ADK *before* init, or call `patch_google_adk()`. ADK emits its own agent
spans and suppresses lower-level `google.genai` patching to avoid double-logging, and this is
intentional.

## Python: init does NOT attach to an existing TracerProvider

If a global OTel `TracerProvider` already exists, `weave.init()` **backs off**. It adds no Weave
exporter, so spans silently never reach Weave. There are two fixes. **(a)** Add Weave's exporter as a
span processor on their provider; this is the right move when the app owns its OTel (the recipe is in
`otel_endpoint.md`). **(b)** Use the **Session SDK**, whose spans go through Weave's own tracer. (There
is no `WEAVE_ATTACH_OTEL_TO_EXISTING_PROVIDER` setting, so do not reference one.)

## Node: ESM needs a preload flag

CommonJS auto-activates on `import 'weave'`. **ESM must launch with
`node --import=weave/instrument your-entry.mjs`**, or plain `openai`, `@anthropic-ai/sdk`, and
`@google/genai` will not auto-trace. Add the flag to the start command (the `scripts` in package.json,
a Dockerfile, or a Procfile). `init()` and the Conversation SDK work either way.

## Agents tab vs Calls tab

An agent-shaped span tree lands in the **Agents tab** (the OpenAI Agents SDK, the Claude Agent SDK,
Google ADK, and anything via the Conversation SDK). Flat call traces land in the **Calls tab** (plain
model-SDK auto-patching). If you want agent shape from a Calls-tab library, use the Conversation SDK.

## Python: naming auto-instrumented agents

Auto-instrumentation names each `invoke_agent` span from `gen_ai.agent.name`. Some SDKs supply a real
name (the OpenAI Agents SDK uses `Agent(name=...)`), while `claude_agent_sdk` falls back to the literal
string `"claude_agent_sdk"`. `weave.conversation.agent_name_override` (Python only) renames those
spans for a block:

```python
from weave.conversation import agent_name_override
with agent_name_override("research_agent"):
    async for message in query(prompt="...", options=options):
        ...
```

It relabels the `gen_ai.agent.name` (and the span name) of the integration's `invoke_agent` span
inside the block. It creates no span itself; that is `start_turn(agent_name=...)`. The precedence is
override first, then the native name, then the default. It resolves per span, so concurrent async runs
can differ, and nested blocks restore the previous name on exit.

## Verify

Run a real call, watch for the `View Weave data at https://wandb.ai/<entity>/<project>/weave` line that
`weave.init()` prints, and check the expected tab. If the tab is empty, walk the lookup table above.
Auth not set in the run's environment, the plain-`openai` gotcha, init placed after the work it should
wrap, or the missing ESM preload account for nearly all cases.
