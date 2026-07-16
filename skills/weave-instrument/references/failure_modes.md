# Observed instrumentation failure modes

Use this catalog when repairing existing tracing or verifying a new integration. Match conditions,
not framework names. Each item came from a runnable service integration that passed its unit tests
while exporting misleading or policy-violating telemetry.

## Consent gate removed while tracing was re-enabled

**Failure signature** — A data-sharing field or tracing-enabled context was deleted with old tracing,
then new Conversation SDK wrappers were added unconditionally. Deployed workers had a project and API key,
so every prompt, response, tool argument, and tool result became eligible for export.

**Correction** — Trace the application's policy decision into the process that executes the turn.
Gate the complete turn tree at its outer boundary:

```python
async def execute_turn(request):
    ...  # all business logic lives here

if request.sharing_allowed:
    with trace_turn(request):
        result = await execute_turn(request)
else:
    result = await execute_turn(request)
```

Keep the business operation independent of tracing. If policy permits a metadata-only trace, Python
supports `weave.start_conversation(..., include_content=False)`, which strips messages, system
instructions, tool arguments/results, and other content at span export. Metadata-only is not
equivalent to no trace; choose from the actual policy.

Missing credentials, a missing `weave.init()`, or a disabled integration patcher is not a policy
gate. Python Conversation spans use the global OTel provider and can still reach an application-owned
exporter. Node initialization is process-wide, so it cannot represent a later per-turn denial.

**Proof** — Run allowed and denied versions of the same turn against an in-memory exporter. Compare
the complete exported payload. Denied must mean zero spans when policy forbids any trace; metadata-only
must retain the expected operation/identity attributes and contain no content fields.

## Model call logged as a disconnected root

**Failure signature** — A Conversation SDK Turn is active, but the model is instrumented only with generic
`weave.integrations.patch_openai()`. The model request appears in Weave's calls store with input,
output, and usage, yet the agent trace contains no child `chat` span. The call has no parent and a
different trace id.

**Cause** — A legacy Calls-tab patch and an OTel Session span do not establish a parent-child
relationship merely because they execute in the same lexical block. Likewise, setting
`implicitly_patch_integrations=False` and then calling only `patch_openai()` does not restore the
OpenAI Agents SDK's native OTel processor.

**Correction** — For custom code, keep a Session `LLM` span open across the real model request or
stream. For a supported agent framework, keep implicit integrations enabled or call the exact native
OTel patcher. The explicit Python patchers live in `weave.integrations.patch`, for example:

```python
from weave.integrations.patch import patch_openai_agents_otel

patch_openai_agents_otel()
```

Do not combine generic and native patches unless an emitted-span probe proves there is neither a
duplicate nor a detached call.

**Proof** — Assert exactly one `invoke_agent` turn and the intended `chat` children. For every child,
assert `child.parent.span_id == turn.context.span_id` and identical trace ids. Pin complete input,
output, response identity, usage, and error fields.

## Tool span reconstructed after execution

**Failure signature** — The agent finishes, returns a list of tool invocation/result entries, and a
logger loops over that list to create Tool spans. A tool that ran for 50 ms exports a sub-millisecond
span because the span measured only JSON assignment. Exceptions, timeouts, and cancellation from the
real execution are absent.

**Correction** — Open the Tool span at the actual dispatch boundary and keep it open across the call:

```python
with turn.start_tool(
    name=tool_call.name,
    arguments=tool_call.arguments,
    tool_call_id=tool_call.id,
) as tool_span:
    result = await environment.execute(tool_call)
    tool_span.result = result
```

`Tool.__enter__` records the real start time. `Tool.__exit__` records a raised exception and ends the
span, and `Tool.end()` derives duration from `started_at` and `ended_at`. Preserve the original return
value and exception.

Use Python `log_turn` / `log_conversation` only when the live boundary is genuinely unavailable, such as
importing a transcript. Batch objects can carry supplied logical timestamps and results; they cannot
recover runtime exceptions or timing that was never captured.

**Proof** — Execute one sleeping tool and one raising tool. Assert the successful duration covers the
sleep, the failure exports error status and the exact exception, both have the intended turn parent,
and the original exception still reaches the caller.

## Returned error or cancellation exported as success

**Failure signature** — The runner represents completion, error, cancellation, timeout, or a
permission request in a result object. The tracing wrapper records only final text and tools. No
exception crosses the Turn context manager, so the exported turn looks successful and carries no
terminal outcome.

**Cause** — Session context managers automatically record raised exceptions. They cannot infer an
error encoded as ordinary return data.

**Correction** — Before the Turn closes, map every terminal variant to stable attributes. When the
installed Python version supports it, use `turn.set_attributes({...})` while the span is recording.
Keep the application's existing outcome vocabulary rather than inventing a second state machine. If
the required OTel error status cannot be expressed through the installed Conversation SDK, state that
limitation and use the app's OTel span surface or request the missing SDK capability; do not silently
mark a returned failure successful.

**Proof** — Exercise every terminal enum/variant and compare exact exported attributes. Include a
raised exception separately to prove the context manager records exception status while preserving
the throw.

## Tracing secret replaces the process W&B identity

**Failure signature** — Deployment injects an internal tracing secret directly as process-wide
`WANDB_API_KEY`, even though another client or proxy in the same service already owns that variable.
Tracing works, but unrelated W&B operations authenticate as the tracing service account.

**Correction** — Store tracing auth in a dedicated application setting. Scope any temporary
`WANDB_API_KEY`, `WANDB_BASE_URL`, or trace-server URL override to `weave.init()` and restore the
environment afterward. For a raw OTel exporter, construct its Authorization header directly from the
dedicated setting. Never print either credential.

**Proof** — Capture only presence/identity labels, never secret values. Initialize Weave, then prove
the unrelated client still uses its original configuration and temporary tracing overrides are gone.

## Trace emission restored but application correlation is lost

**Failure signature** — A migration removes the stored call/turn reference along with the old logger,
then restores span emission without replacing that reference. Traces appear in Weave, but feedback
routes, deep links, and retroactive recovery can no longer locate the record for an application turn.

**Correction** — Treat the persisted reference and its consumers as part of the integration contract.
Return or derive a stable reference from the new trace, persist it with the application turn, update
feedback/link consumers deliberately, and preserve recovery after an initial trace-write or
reference-write failure. Do not drop the old field until every consumer has a replacement.

**Proof** — Complete a turn, persist its new reference, build the expected deep link, and attach both
positive and negative feedback through the real application route. Then simulate an initial missing
reference or write failure and prove the existing recovery path repairs it.

## Existing Python TracerProvider silently owns the export path

**Failure signature** — A Python application installs an SDK `TracerProvider` before `weave.init()`.
Conversation spans exist locally, but nothing arrives in the chosen Weave project, or they flow only
to a different telemetry backend.

**Correction** — Add Weave's OTLP exporter/span processor to the existing provider and preserve its
current processors. Follow `otel_endpoint.md`. Do not replace the provider.

**Proof** — Use the real application provider in the smoke test. Assert its original exporter still
receives spans and a recorder at the Weave export boundary receives the same agent trace.

## Wiring-only tests pass while telemetry is broken

**Failure signature** — Tests mock `weave.init`, patchers, or Session constructors and assert call
counts. They never execute a model request, tool, error, policy-denied turn, or exporter. The suite is
green while the model call is detached and tool duration is fabricated.

**Correction** — Keep small wiring tests only as supplements. Add an integration test using a real
SDK call with a local transport plus an in-memory OTel exporter or a real trace-server fixture. Assert
complete payload values; do not use substring checks for serialized messages or errors.

**Minimum regression matrix**

1. Allowed turn with model and tool: one exact `turn -> LLM/tool` tree.
2. Denied turn: zero spans, or exact metadata-only payload if that is the policy.
3. Sleeping and raising tools: truthful duration and error behavior.
4. Returned completed, errored, cancelled, timed-out, and permission-required outcomes.
5. Streaming model completion and any retry behavior the application exposes.
6. Existing-provider and dedicated-credential configurations.
7. Persisted trace reference, feedback/deep-link, and recovery flows when the application exposes
   them.
