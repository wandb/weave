---
name: calls-to-agent-spans
description: Convert a Weave project's classic Calls-tab history into agent spans so it renders in the Agents tab. Use when someone asks to backfill, replay, or migrate old traces or @weave.op calls into agent tracing, without editing the app.
---

# Convert classic calls to agent spans

The Agents tab reads agent spans. A project that only ever logged `@weave.op` calls is empty there. This skill converts one time window of those calls into agent spans through two public endpoints, using only an API key (read on the source, write on the target).

| | |
| --- | --- |
| Read | `POST /calls/stream_query` |
| Write | `POST /agents/otel/v1/traces` (OTLP protobuf) |
| Verify | open the target project in the Agents tab |

Base URL is `https://trace.wandb.ai` for SaaS. Always write to a **new** project. Never write to the source, and never mix converted spans with live agent traces.

The CLI is `scripts/convert_calls_to_agent_spans.py`. It needs `requests` and `opentelemetry-proto`. For the span shape the Agents tab reads, open `references/conventions.md`. For classic payload shapes this converter already handles, open `references/payload-shapes.md`.

## Run it

Always dry-run first. It prints the inferred field mapping, per-op coverage, and a few sample spans, and writes nothing.

```bash
export WANDB_API_KEY=...
python scripts/convert_calls_to_agent_spans.py \
  --source-project entity/old-project \
  --target-project entity/new-project \
  --started-after 2026-08-01T00:00:00Z \
  --started-before 2026-08-02T00:00:00Z \
  --dry-run
```

Read `coverage`. If any root op is listed under `missing_user` or `missing_assistant`, pass `--user-path` / `--assistant-path` / `--conversation-path` (dotted, with optional `[i]`) or add that path to the candidate list in `scripts/payload_paths.py` and dry-run again. Convert one day at a time.

Drop `--dry-run` only after coverage is clean. The CLI refuses a target that already has agent spans unless you pass `--allow-existing` for a window you know is disjoint.

## What a call becomes

A turn is a trace: the root call is `invoke_agent`, descendants are `chat` (names a model) or `execute_tool` (always a leaf, never a model). Conversation id is copied onto the turn and every model call, not onto tools. Messages live only on the turn root. Token counts come only from calls that name a model.

Ids carry over, so a span joins back to its call: `trace_id` is the call `trace_id` without dashes.

## Verify

Open the target project in the Agents tab. Pick one conversation and check:

- turn count matches the source session
- each turn has a user message and an assistant reply
- tools sit on the turns that called them
- cost is non-empty wherever the source logged usage and the target has a price for that model

`scripts/log_test_fixture.py` can seed a throwaway project with the shapes in `references/payload-shapes.md`.
