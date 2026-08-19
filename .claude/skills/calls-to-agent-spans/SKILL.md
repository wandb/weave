---
name: calls-to-agent-spans
description: Convert a Weave project's classic calls into agent spans, so a project traced before the agents product existed renders in the agents workspace. Use when someone asks to backfill, replay, or migrate old traces/calls into agent tracing.
---

# Convert classic calls to agent spans

The agents workspace reads the `spans` table. A project that only ever logged calls renders as
nothing there. This converts one window of calls into agent spans using two HTTP endpoints, so it
needs nothing but an API key with read access to the source and write access to the target.

| | |
| --- | --- |
| Read | `POST /calls/stream_query` |
| Write | `POST /agents/otel/v1/traces` (OTLP, protobuf only) |
| Verify | `POST /agents/spans/query`, `/agents/conversations/chat`, `/agents/query` |

Base URL is `https://trace.wandb.ai` for SaaS. Never write to the source project.

The converter needs `requests` and `opentelemetry-proto`. It splits into `payload_paths.py`
(which field holds what), `span_builder.py` (a call becomes a span), `otlp_export.py` (the wire
encoding), and `calls_client.py` (fetching), behind the `convert_calls_to_agent_spans.py` CLI.

## Run it

Always dry-run first. It prints the field mapping it inferred and the first few spans, and writes
nothing:

```bash
export WANDB_API_KEY=...
python scripts/convert_calls_to_agent_spans.py \
  --source-project entity/old-project \
  --target-project entity/new-project \
  --started-after 2026-08-01T00:00:00Z \
  --started-before 2026-08-02T00:00:00Z \
  --dry-run
```

Check the `mapping` block against what you know about the project, then drop `--dry-run`. Convert
one day at a time: it keeps each run small enough to inspect and to redo.

If the mapping is wrong or the run exits saying it could not find the user or assistant text, name
the paths yourself with `--conversation-path`, `--user-path`, `--assistant-path`. The error lists
the payload keys it actually saw.

## How a call becomes a span

A turn **is** a trace. There is no turn id: one root call becomes one turn, and its descendants
become the child spans of that turn.

| Classic call | Agent span |
| --- | --- |
| `trace_id` (a uuid) | `trace_id`, the same uuid as 32 hex characters |
| `id` | `span_id`, the first 8 bytes of that uuid as 16 hex characters |
| root call | the turn, `operation_name = invoke_agent` |
| call naming a model | `operation_name = chat`, `span_kind = CLIENT` |
| childless call naming no model | `operation_name = execute_tool` |
| session key on the root | `conversation_id` on every span except the tool spans |
| `output.usage` on a model call | the `weave.usage.*` token counts |

Ids carry over rather than being rehashed, so a span always joins back to the call it came from:
`trace_id == call.trace_id.replace("-", "")`.

Attributes use the `weave.*` keys in
`weave/trace_server/agents/semconv.py`, which is the source of truth for every attribute the
server extracts into a column. Each has a `gen_ai.*` alias that is also accepted; the `weave.*` key
wins when both are present.

## What bites

**`conversation_id` belongs on the model spans too.** Only tool spans go without one. Tokens live
on the `chat` spans, so leaving the conversation off them makes every turn cost read zero while
everything still looks populated.

**`span_name` must be `"<operation> <subject>"`.** The server parses it: it strips the
`invoke_agent ` prefix to get the agent label and the `execute_tool ` prefix to recover a tool name.
A bare name silently degrades the chat view.

**Column selection has two sharp edges.** Asking for a field and its sub-fields returns only the
sub-fields. Sub-selecting a field whose value is a scalar replaces the scalar with an object of
nulls. So a field you need whole wins and its sub-columns get dropped, which is what
`select_columns` in `payload_paths.py` does.

**Never fetch full rows in bulk.** A root call can carry the whole conversation history in
`inputs`. On a real project that is ~86KB per row against ~1.4KB for the columns actually needed.
Only the 25-row mapping sample fetches full payloads.

**Count tokens only on calls that name a model.** A wrapper op repeats the usage of the model calls
beneath it, so summing every op that carries a `usage` block multiplies the trace's real tokens.

**Classify per op name, not per call.** A per-call "is it a leaf" test makes the same op a tool in
one trace and an internal step in the next.

**Healthy spans are `UNSET`, not `OK`.** The enum allows `OK` but no emitter produces it.

**Cost is derived, not stored.** There is no cost column: the product computes it from the token
counts and the model name. If cost reads zero but tokens are present, the target environment has no
price row for that model.

## Verify

Read it back through the same public API. Expect the conversation count to match the number of
distinct session keys, and the agent list to hold the ops that actually drive model calls:

```bash
python - <<'PY'
import os, requests
s = requests.Session(); s.auth = ("api", os.environ["WANDB_API_KEY"])
B, P = "https://trace.wandb.ai", "entity/new-project"
w = {"project_id": P, "started_after": "2026-08-01T00:00:00Z"}
print(s.post(f"{B}/agents/query", json={**w, "limit": 20}, timeout=90).json())
print(s.post(f"{B}/agents/spans/query",
             json={**w, "group_by": [{"source": "column", "key": "conversation_id"}], "limit": 5},
             timeout=90).json()["total_count"])
PY
```

Then open one conversation with `/agents/conversations/chat` and confirm the turns carry a user
message, an assistant reply, and a non-null `total_cost_usd` wherever the source logged usage.

If you need a project to test against, `scripts/log_test_fixture.py` logs classic calls in five
different shapes, which is what `reference/payload-shapes.md` documents.
