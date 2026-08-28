# Agent instructions for `weave` repository

## Core Rules

- When you learn something new about the codebase or introduce a new concept, update this file (`AGENTS.md`) to reflect the new knowledge. This is YOUR FILE! It should grow and evolve with you.
- If there is something that doesn't make sense architecturally, devex-wise, or product-wise, please update the `Requests to Humans` section below.
- Always follow the established coding patterns and conventions in the codebase.
- Document any significant architectural decisions or changes.
- Prefer no code comments; when needed, use one line for a non-obvious invariant.

## Python Import Rules

**IMPORTANT: Always place imports at the top of Python files.**

- All imports must be at the module level (top of the file), not inside functions or methods.
- The only exceptions are:
  - Circular import avoidance (must be documented with a comment explaining why)
  - Optional dependencies that may not be installed (must be wrapped in try/except)
  - TYPE_CHECKING imports for type hints only
- Note: Imports inside functions are not caught by linting. **Agents must self-enforce this rule.**

❌ **Never do this:**

```python
def my_function():
    import re  # BAD: import inside function
    return re.match(...)
```

✅ **Always do this:**

```python
import re  # GOOD: import at top of file

def my_function():
    return re.match(...)
```

## Development Setup

### Local Development (uv)

This project uses `uv` for dependency management. Dependencies are organized into **dependency-groups** (not extras) in `pyproject.toml`.

**Quick reference:**

- **Run tests**: `uv run --group test python -m pytest <path> -v`
- **Run linting**: `uvx ruff check <path>`
- **Run lint with auto-fix**: `uvx ruff check --fix <path>`

**Common pitfalls:**

- Do NOT use bare `python -m pytest` — the `python` on PATH may be from a uv cache, not the project `.venv`. Always use `uv run`.
- Do NOT use `--extra test` — `test` is a dependency-group, not an optional-dependency. Use `--group test`.
- `ruff` is not installed in any project dependency group. Use `uvx ruff` to run it.
- Ruff now enforces `PLW` rules. `PLW0602`, `PLW0603`, `PLW1641`, and `PLW3201` are handled with spot-level inline `# noqa` on specific lines (not global/per-file ignore). Prefer fixing code first; if intentional, suppress only the exact line.
- Be careful with `PLW1514` autofixes on serialization-sensitive code (`weave/type_handlers/Content/content.py`, `weave/type_handlers/Audio/audio.py`) and mocked file I/O (`weave/trace_server/costs/update_costs.py`): adding `encoding=` changed behavior/tests, so these files are explicitly ignored for that rule.

### PyPI release publishing

`uv build` resolves the unconstrained `hatchling` build requirement in an
isolated environment. Keep the pinned `pypa/gh-action-pypi-publish` action new
enough to validate the Core Metadata version emitted by current Hatchling; for
example, Hatchling 1.32 emits Metadata 2.5, which requires the action's Twine 7
and Packaging 26 stack rather than Twine 6.1 and Packaging 25.

### Codex Development (nox)

- Your machine should be setup for you automatically via `bin/codex_setup.sh`
- If you encounter any setup issues:
  1. Check the setup script for potential problems
  2. Update `bin/codex_setup.sh` with necessary fixes
  3. Document any manual steps required in this section

_Important:_ For OpenAI Codex agents (most likely you!), your environment does not have internet access. If you need something setup beforehand, this is where you need to do it.

## Codebase Structure

### Main Components

- `weave/` - Core implementation
  - `weave/` - Python package implementation
  - `weave/trace_server` - Backend server implementation

### Azure file storage authentication

The trace server preserves explicit Azure connection strings and account keys
for backward compatibility. When neither is configured, it uses
`DefaultAzureCredential`, including AKS workload identity. Read-only export
links use an account-key SAS for explicit credentials and a user-delegation SAS
for workload identity.

## Generated Files — Do Not Hand-Edit

`weave/trace_server/model_providers/model_providers.json` and `weave/trace_server/costs/cost_checkpoint.json` are generated. Never edit them by hand — regenerate with `make update_model_providers` / `make update_costs` (see `weave/Makefile`).

Generate implicit cost `created_at` values in UTC because insertion interprets naive checkpoint timestamps as UTC.

Note: the scripts read `modelsBegin.json`/`modelsFinal.json`, which are symlinks into wandb/core and only resolve when this repo is checked out as the submodule inside wandb/core (`services/weave-trace/weave-python/weave-public`).

`weave/vendor/weave_server_sdk/` is the generated Weave Trace API client, copied
in from wandb/core rather than depended on because it is not published to PyPI.
Never edit it by hand — regenerate it in core, then re-run
`scripts/vendor_weave_server_sdk.py` with `--sdk-output` and `--core`. See
`weave/vendor/README.md`. The Node SDK copy lives at
`sdks/node/src/vendor/weave-server-sdk/` and is refreshed the same way with
`scripts/vendor_node_weave_server_sdk.py`. See `sdks/node/src/vendor/README.md`.

Persisted `AgentDashboard` objects intentionally use a closed, discriminated
schema. Supported panel variants and their configuration fields must be added
to `builtin_object_classes/agent_dashboard.py`; do not replace panel settings
with an untyped dictionary. After changing the model, run
`make synchronize-base-object-schemas` from the repository root so the Python
schema and the dependent Core frontend types stay aligned.

### Trace Server API / Node SDK Schema

Custom Runtime registration is a desired-state facade over the existing
`Provider` and `ProviderModel` built-in objects. Keep `ProviderModel.provider`
as the Provider digest and preserve `custom::<provider>::<model>` selectors;
those representations are consumed by inference and the current UI.
Inference caches resolved custom-provider configuration per replica, so updates
may remain stale for up to 60 seconds.

When trace-server request/response models or route schemas change, regenerate
the TypeScript client in wandb/core and re-vendor it with
`scripts/vendor_node_weave_server_sdk.py`. See `sdks/node/src/vendor/README.md`.

Evaluation result rows merge agent span links from two sources: legacy
`weave.genai_span_ref` call attributes and OTel spans whose promoted
`eval_run_id` plus `eval_predict_and_score_call_id` columns identify the
trial. Keep the promoted-column hydration best-effort so eval results remain
available during rolling deploys.

`weave.invoking_span` (`{trace_id, span_id}`, hex) points the other way, from a
call to the OTel span that was current when it started — an agent's
`execute_tool` span in the case it is built for, but any ambient instrumentation
qualifies. `create_call` writes it on *every* call started inside that span, not
just the outermost one: skipping when the parent call already carries it marks
every other level, because the check reads the parent's recorded state and the
parent may itself have skipped. A reader must treat a missing key and a pair
that matches no span as normal — the write does not check that the span reaches
our backend. Spans opened by `trace_server.tracing` are the one exclusion, and
they are recognised through `WEAVE_SERVER_SPAN_KEY` on the context rather than
off the span object, which under the OTel→DD bridge is not an SDK span.

`WeaveClient.createCall` in the Node SDK writes the same key with the same
meaning, but sees fewer spans. That SDK registers no OTel context manager and
never calls `startActiveSpan`, so its own spans never become current and
`getActiveSpan` returns only instrumentation the user installed themselves.
Linking the `execute_tool` spans the `openai-agents` and `google_adk`
integrations emit has to read those integrations' own state instead — the
agents SDK keeps its current span in its own AsyncLocalStorage, and the ADK
plugin keeps a map of open tool spans.

If `sdks/node/node_modules` is missing, run `pnpm install --frozen-lockfile` in `sdks/node` first. Do not use `npm install`; this SDK is pinned to pnpm.

## Python Testing Guidelines

### Test Framework

- Testing is managed by `nox` with multiple shards for different Python versions
- Each shard represents specific package configurations

### Server fixtures (do NOT hand-roll fake servers)

- **Never create a `_FakeServer`, stub, or mock `TraceServerInterface`** to test
  server-side logic. Use the existing `client` fixture (gives `client.server` +
  `client.project_id`) or the `trace_server` fixture, which run against a real
  ClickHouse backend. Build inputs with the real APIs
  (`obj_create`, `table_create`, etc.). Mock only external services we don't own.

### Assert on the complete payload (no substring / membership checks)

Assert on the **full value**, not that a fragment appears somewhere inside a
stringified payload. Substring (`in`) and membership checks pass on accidental
matches and let the rest of the payload drift undetected, so prefer them only
when membership in a collection is genuinely the contract under test.

❌ **Never do this:**

```python
assert "short memo" in msg                 # substring of a serialized blob
assert "error" in str(response)
assert "note" in feedback.payload          # key-presence instead of value
```

✅ **Always do this:**

```python
assert feedback.payload == {"note": "short memo", "emoji": "👍"}  # whole object
assert feedback.payload["note"] == "short memo"                   # exact field
```

If you only care about one field, pin that field with `==`; if you care about
the shape, compare the whole dict/object. The same rule applies to SQL: assert
the complete query string, never `assert "WHERE x" in sql`.

### VCR + ClickHouse isolation (integration tests)

- Integration tests replay provider traffic from VCR cassettes while the weave
  client concurrently talks to ClickHouse over localhost HTTP. vcrpy is not
  safe for that concurrency out of the box: its urllib3 passthrough wraps real
  sends in `force_reset()`, which briefly unpatches httpx/httpcore globally and
  lets provider calls escape an active cassette to the live API (seen as real
  OpenAI 429s in CI). `tests/integrations/conftest.py` carries two autouse
  fixtures that prevent this — read their docstrings before touching VCR
  config, and keep `tests/integrations/langchain/test_vcr_isolation.py` green.
- Corollary: a real provider 4xx during a `record_mode="none"` cassette means
  VCR's patches were absent at request time (an isolation bug), not that the
  cassette failed to match — matching failures raise
  `CannotOverwriteExistingCassetteException` instead.

### Key Test Shards

Focus on these primary test shards:

- `tests-3.12(shard='trace')` - Core tracing functionality
- `tests-3.12(shard='flow')` - Higher level work"flow" objects
- `tests-3.12(shard='trace_server')` - Server implementation
- `tests-3.12(shard='trace_server_bindings')` - Server bindings

The Claude Agent SDK shard combines ClickHouse-backed calls tests with
no-server OTel tests. PR CI runs `tests-3.10(shard='claude_agent_sdk')` once
without a marker filter so both tracing paths contribute coverage.
Calls-based tests must include the integration's intentional text and thinking
child calls in exact operation-set assertions.

Every other shard, `flow` included, is run by CI with `-m "trace_server"`, and
that filter comes from the workflow rather than from `noxfile.py`. A test that
uses no server fixture therefore never runs in CI unless it carries
`@pytest.mark.trace_server` itself.

### Running Tests

**IMPORTANT**: Any test depending on the `client` fixture runs against ClickHouse, the only trace-server backend. Locally, the test fixtures auto-start a ClickHouse Docker container if one isn't already running, so Docker must be available. Pass `--clickhouse-process=true` to use a local `clickhouse-server` binary instead of Docker.

#### Basic Test Commands

1. Run all tests in a specific shard: `nox --no-install -e "tests-3.12(shard='trace')"`
2. Run a specific test by appending `-- [test]` like so: `nox --no-install -e "tests-3.12(shard='trace')" -- tests/trace/test_client_trace.py::test_simple_op`
3. Run linting: `nox --no-install -e lint` (Note: This will modify files)

_Important:_ Since you don't have internet access, you must run `nox` with `--no-install`. We have pre-installed the requirements on the above shards.

#### Critical Path Information

**Test paths must be relative to the repository root**, not the `tests/` directory.

Examples:

- ✅ CORRECT: `-- tests/trace/test_dataset.py::test_basic_dataset_lifecycle`
- ❌ WRONG: `-- trace/test_dataset.py::test_basic_dataset_lifecycle`

#### Backend Selection

The `--trace-server` flag selects the backend: `clickhouse` (default) or
`fake` (in-memory).

**Fake / in-memory (Fastest for Development):**

```bash
nox --no-install -e "tests-3.12(shard='trace')" -- tests/trace/test_client_trace.py::test_simple_op --trace-server=fake
```

The fake backend (`weave/trace_server/in_memory_trace_server.py`,
`InMemoryTraceServer`) is a pure-Python, dict-backed drop-in replacement that
lives parallel to the ClickHouse implementation. It replicates **ClickHouse**
(the production backend) at the interface level: JSON_VALUE string typing for
dynamic fields, `to*OrNull` cast rules, NULLS-LAST ordering, DateTime64
comparisons, and computed summary fields. Tests that assert ClickHouse
*internals* (SQL, table routing/residence, insert batching, bucket file
storage) are gated with `client_is_clickhouse` and skip on the fake. No
files, no SQL, no Docker.

**ClickHouse (the real backend):**

```bash
nox --no-install -e "tests-3.12(shard='trace')" -- tests/trace/test_client_trace.py::test_simple_op
```

ClickHouse is the only trace-server backend (`--trace-server` defaults to
`clickhouse`):

```bash
nox --no-install -e "tests-3.12(shard='trace')" -- tests/trace/test_client_trace.py::test_simple_op
```

**Note:** ClickHouse tests require Docker to be running (the fixtures start a
container automatically), or a local `clickhouse-server` binary with
`--clickhouse-process=true`. When neither is available, use the in-memory
fake with `--trace-server=fake`.

#### Remote HTTP Trace Server Implementation Selection

The `--remote-http-trace-server` flag controls which **remote HTTP trace server implementation** is used for testing trace server bindings:

**RemoteHTTPTraceServer (Default):**

```bash
nox --no-install -e "tests-3.12(shard='trace_server_bindings')" -- tests/trace_server_bindings/test_trace_server_bindings.py --remote-http-trace-server=remote
```

**StainlessRemoteHTTPTraceServer:**

```bash
nox --no-install -e "tests-3.12(shard='trace_server_bindings')" -- tests/trace_server_bindings/test_trace_server_bindings.py --remote-http-trace-server=stainless
```

**Important Notes:**

- The `--remote-http-trace-server` flag is for **trace server binding implementation** (RemoteHTTPTraceServer vs StainlessRemoteHTTPTraceServer)
- Both implementations share the same test file; the flag determines which server class is used

#### Environment Issues

**Color Flag Conflicts:**
If you encounter an error like `Can not specify both --no-color and --force-color`, this is due to conflicting environment variables. Unset them before running nox:

```bash
unset NO_COLOR FORCE_COLOR && nox --no-install -e "tests-3.12(shard='trace')" -- tests/trace/test_dataset.py::test_basic_dataset_lifecycle
```

**Prek stashing behavior:**
`nox --no-install -e lint` runs `prek`, and prek stashes unstaged changes before running hooks. If you need to validate a fix to one file (for example with `--mypy-only`), stage that file first or run the checker directly, otherwise hooks may run against older content.

**Markdown serialization and MTSAAS env:**
`weave/type_handlers/Markdown/markdown.py` only stores large markdown payloads in `markup.md` when `is_mtsaas()` is true. If local `WANDB_BASE_URL`/`WF_TRACE_SERVER_URL` differs from CI defaults, `test_serialization_correctness[markdown]` may fail locally with inline markup differences. For CI-like behavior, set:

```bash
WF_TRACE_SERVER_URL=https://trace.wandb.ai nox --no-install -e "tests-3.12(shard='trace')" -- tests/trace/data_serialization/test_serialization_correctness.py::test_serialization_correctness[markdown]
```

#### Reinstalling Dependencies

If you encounter import errors or missing modules, reinstall the test shard environment:

```bash
nox --install-only -e "tests-3.12(shard='trace')"
```

Then run your tests with `--no-install` as usual.

### LangChain Integration Tests

The langchain integration tests work fully on macOS including chromadb/vector store tests.

**Running LangChain Tests:**

```bash
nox --no-install -e "tests-3.12(shard='langchain')" -- tests/integrations/langchain/
```

## Typescript Testing Guidelines

The Node SDK (`sdks/node`) is a **pnpm** project — it ships a `pnpm-lock.yaml`
and pins `"packageManager": "pnpm@10.8.1"` in `package.json`. Do **not** run
`npm i`: npm's resolver crashes trying to dedupe pnpm's symlink `node_modules`
(`TypeError: Cannot read properties of null (reading 'matches')`).

```
cd sdks/node
pnpm install
pnpm test
```

To run an example (e.g. the Claude Agent SDK demo), `dist/` must be built first
(`import 'weave'` self-resolves via the package `exports` to `dist/index.mjs`);
`pnpm install` builds it via the `prepare` script. Then:

```
pnpm exec tsx examples/claudeAgents.ts
```

Pure ESM auto-instrumentation requires the `weave/instrument` loader. For
one-off `tsx` live validation scripts where that loader is not installed, call
`wrapClaudeAgentSdk()` and consume the returned module view so tracing is
deterministic.

### TypeScript integration metadata

- `sdks/node/src/integrations/integrationMetadata.ts` remains shared:
  `asAttributes()` supplies nested provenance to Weave-call integrations, while
  `asOtelAttributes()` supplies canonical `weave.integration.name` and
  `weave.integration.version` identity to OTel integrations and preserves
  flattened `weave.integration.meta.*` provenance. OTel scalar metadata stays
  typed; non-scalar values are stringified.

### TypeScript Anthropic message batches

- A batch result is a discriminated union and only its `succeeded` variant
  carries a `message`; a batch ends when every request has succeeded, errored,
  been canceled or expired. Read `message` without checking the discriminator
  and the reducer stores `undefined`, which the usage summarizer then throws on,
  out of the stream iterator's `finally`.
- `patchAnthropicMessagesCreate` wraps `Messages.prototype.create` in a `Proxy`,
  so property reads still reach the mock behind it and a test can reconfigure it
  through the patched prototype. `patchBatchApi` assigns `op()`'s plain wrapper
  to `Batches` `create`, `retrieve` and `results` instead, so for those a test
  reconfigures the mock it captured before patching, or reaches it through
  `__wrappedFunction`.

### TypeScript Anthropic token accounting

- Anthropic reports `input_tokens` as fresh, uncached prompt only and bills the
  rest through `cache_read_input_tokens` and `cache_creation_input_tokens`.
  Weave's cost math subtracts those two from the prompt total, so the usage
  summary has to carry an inclusive `input_tokens`. `totalInputTokens()` in
  `integrations/anthropicUsage.ts` is where that sum lives, for this integration
  and for the Claude Agent SDK OTel tracer; it mirrors the Python
  `total_input_tokens()`.
- Only the summary is normalized. The provider's own `usage` object stays
  untouched, so the response the caller receives keeps Anthropic's own numbers.
- Streaming `message_delta` usage is cumulative, and every field except
  `output_tokens` is nullable. Skip the null ones, as the vendor's own client
  does, and overwrite rather than add — a delta carries the running total, not
  an increment.

### TypeScript custom type round trip

- `client.get()` rebuilds a `WeaveImage` from a `PIL.Image.Image` payload and a
  `WeaveAudio` from a `wave.Wave_read` one, downloading the stored file from
  `ref.projectId`, not the client's project.
- It also rebuilds a `Date` from a `datetime.datetime` payload, which stores no
  file: Python writes the ISO string inline into the record's `val`. A `Date`
  is a UTC instant with millisecond resolution, so the round trip keeps the
  moment but loses the original offset and truncates Python's microseconds. It
  reads whole-minute offsets only, so a timestamp from before its zone adopted
  one comes back as an `Invalid Date` (`Africa/Monrovia` ran on `-00:44:30`
  until 1972).
- `wave.Wave_read` is what this SDK writes, and what Python wrote until May
  2025. Both store one `audio.wav` and no metadata file.
- Python now records every `Audio` and `wave.Wave_read` object as
  `weave.type_handlers.Audio.audio.Audio` with an extra `_metadata.json`,
  because `register()` in `weave/type_handlers/Audio/audio.py` puts the `Audio`
  serializer first and its `is_audio_instance` predicate also accepts
  `wave.Wave_read`.

### TypeScript GenAI Turn output

- The existing `Turn.record({messages: [...]})` path records input messages;
  Turn stores these separately from terminal `outputMessages`.
- Record a terminal agent result with
  `Turn.record({outputMessages: [...]})`; `Turn.end()` serializes it onto the
  `invoke_agent` span as `gen_ai.output.messages`.

### TypeScript GenAI span handles

- `Conversation`, `Turn`, `LLM`, `Tool`, and `SubAgent` emit canonical
  `invoke_agent`, `chat`, and `execute_tool` spans through
  `/agents/otel/v1/traces`.
- These spans go through the `BasicTracerProvider` that `genai/provider.ts`
  builds, never the OTel global registry. A processor that must see them belongs
  in that provider's `spanProcessors`, which is built lazily on the first span
  and rebuilt on a project switch — registering once from `init()` misses both.
- At a span's attribute limit OTel JS drops the *incoming* attribute, where
  Python's `BoundedAttributes` evicts the oldest, so the two SDKs keep different
  halves of an overflowing set. The eval linker writes the pair eval results
  match on before its display-only attributes for that reason, and the op linker
  sits after it in the Node provider's array for the same reason. Registering the
  two linkers in opposite order is how both SDKs end up keeping the same half.
- For callback or generator integrations, create `Conversation`, `Turn`, and
  `LLM` in short `runIsolated()` scopes, then retain and pass explicit handles.
  `Tool` and `SubAgent` do not use ambient state.
- Keep response models on child `chat` spans; use `setAttributes()` for fields
  without typed `record()` methods.
- Every TypeScript GenAI span handle supports
  `recordError(error)` to mark a failure without ending the span; terminal
  failures can use `end({error})`. The SDK derives `error.type` from
  `error.name`. After `recordError()`, close with `end()` without passing the
  same error again.
- `Turn` and `SubAgent` are logical in-process `invoke_agent` spans: emit
  `SpanKind.INTERNAL` and do not set `gen_ai.provider.name`; provider identity
  belongs on child model spans.
- Record `invoke_agent` inputs and outputs through `Turn.record()` or
  `SubAgent.record()`. Keep `gen_ai.tool.*` attributes on `execute_tool` spans,
  not agent spans.
- The Claude Agent SDK integration keeps each `Tool` open until its matching
  `tool_result`.
- `Tool` accepts JSON-compatible arguments and results. It records strings
  as-is and serializes structured values for OTel attributes. Prefer
  `Tool.end({result, error})`; mutable `Tool.result` remains only for
  backward compatibility.
- Agent span list queries omit heavy message, tool-payload, and raw-span fields;
  use an `AgentSpansQueryReq` with `include_details=True` when validating stored
  span details.
- Parallel/background Claude Agent SDK `Agent` calls can emit an
  `async_launched` or `remote_launched` tool result before forwarded child
  messages, then finish via a `task_notification`. Keep one `SubAgent` keyed by
  tool-use ID across turn boundaries until that notification arrives.
- Record every background `task_notification` status on its `SubAgent` as
  `claude_agent_sdk.task.status` so `completed`, `failed`, and `stopped` remain
  distinguishable independently of standard `error.type` metadata.
- Route a forwarded assistant message to an already-open `SubAgent` before
  creating a `Turn`; background messages can arrive after the root result and
  must not create an empty root turn or consume the next pending input.
- For synchronous `Agent`/`Task` completion, read terminal output from the
  structured `SDKUserMessage.tool_use_result.content`; use the model-facing
  `tool_result` block content only as a compatibility fallback. Background
  completion output continues to come from `task_notification.summary`.
- Read a subagent's lifetime from the launch request (`run_in_background`, or
  `isolation: 'remote'`, which is always backgrounded) rather than inferring it
  from the result status — an unrecognized status must not downgrade it.
- Surviving a turn boundary is transitive: a background `SubAgent`'s open
  `Tool`s and nested `SubAgent`s survive with it. Closing a descendant early
  also drops it from the open map, so the next forwarded message re-creates it
  under the wrong `Turn`.
- Buffer a subagent's terminal state (and the timestamp it was observed) instead
  of ending the span on the spot: `SpanBase` only records an error through
  `end()`, and the span must close after its children. Pass the timestamp as
  `endTime` so the deferral doesn't inflate the duration.
- For streamed sessions, queue observed user inputs in FIFO order and close one
  `Turn` for each matching SDK `result`.
- Treat `Agent` and legacy `Task` tool calls as subagents keyed by tool-call ID,
  and preserve the caller's `forwardSubagentText` option.

### Claude Agent SDK streamed images

- Tap `AsyncIterable<SDKUserMessage>` prompts without consuming or cloning
  them; map text and base64/URL images to GenAI text, blob, and URI parts.
- Each user-to-result cycle is one root turn. Resumed queries share
  `session_id`, and long-lived streamed inputs queue turns in FIFO order.
- Treat `blob.content` as media/ref data exposed through `content_refs`, not
  prose.
- Run the example from `sdks/node`, use repository-relative fixtures, keep text
  and image sessions separate, and set both `tools` and `allowedTools`.

## Code Review & PR Guidelines

### PR Requirements

- Title format: `<type>(<scope>): <description>`, where `<type>` is one of
  `chore`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `security`,
  `test`. A scope is **required** (`requireScope: true`) and CI validates it
  (`.github/workflows/pr.yaml`).
- **Pick the scope by which SDK/area the change touches:**
  - `weave_ts` — **required for ALL TypeScript / Node SDK changes** (anything
    under `sdks/node/`). Any PR that modifies the TS SDK must be marked
    `(weave_ts)`, e.g. `fix(weave_ts): ...`, `feat(weave_ts): ...`,
    `chore(weave_ts): ...`.
  - `weave` — the Python SDK and trace server (the default for `weave/…`
    changes), e.g. `fix(weave): ...`, `feat(weave): ...`, `chore(weave): ...`.
  - Other valid scopes (see `pr.yaml` for the authoritative list): `ui`, `app`,
    `dev`, `deps`, `inference`.
- If a single PR spans both the Python and TS SDKs, prefer splitting it; if that
  isn't practical, scope it to the SDK that carries the primary change and call
  out the other in the PR body.
- Provide detailed PR summaries including:
  - Purpose of changes
  - Testing performed
  - Any breaking changes
  - Related issues/PRs

### Pre-commit Checklist

1. Run lint
2. Ensure all tests pass
3. Update documentation if needed
4. Check for any breaking changes

### GitHub Actions Authentication

- Prefer native `${{ secrets.GITHUB_TOKEN }}` for repository-local workflow operations that only need the current repo.
- Use `actions/create-github-app-token@v3` with `vars.WANDBOT_3000_APP_ID` and `secrets.WANDBOT_3000_PRIVATE_KEY` for cross-repository access or bot pushes that must behave like app-authenticated writes.
- Do not introduce new GitHub PAT secrets in workflows unless there is no viable `GITHUB_TOKEN` or GitHub App alternative.

## Common Development Patterns

### Code Organization

- Python code follows standard module organization
- TypeScript/React components are organized by feature
- Shared utilities should be placed in appropriate common directories

### Error Handling

- Use appropriate error types from `weave.errors`
- Include meaningful error messages
- Add error handling tests

### LLM Completion Routing

- Built-in and API-key-authenticated custom providers use LiteLLM.
- Custom runtimes without an API key use the OpenAI client directly so configured
  headers and unauthenticated endpoints do not receive a bearer header.
- OpenAI Responses and Chat Completions report `cache_write_tokens` under
  `usage.input_tokens_details` and `usage.prompt_tokens_details`, respectively.
  Normalize either field when present instead of parsing model names. The
  standard cost registry supplies each model's
  `cache_creation_input_token_cost`. Because `input_tokens` and `prompt_tokens`
  include `cached_tokens` and `cache_write_tokens`, an unmapped
  `cache_write_tokens` value is billed at the Input rate instead of the rate for
  cache writes.
- The OpenAI CI shard runs with `-m trace_server`; usage-normalization coverage
  must therefore come from client-backed pricing cases, not only standalone
  unit tests in `tests/integrations/openai/test_openai_sdk.py`.

### Integration Testing

- Since autopatching was removed from `weave.init()`, integration tests must explicitly patch their integrations
- Add a fixture with `autouse=True` at the top of each integration test file to enable patching
- Example pattern:
  ```python
  @pytest.fixture(autouse=True)
  def patch_integration() -> Generator[None, None, None]:
      patcher = get_integration_patcher()
      patcher.attempt_patch()
      yield
      patcher.undo_patch()
  ```
- Some integrations (like instructor) may need to patch multiple libraries

### Python Conversation Turn messages

- `Turn.messages` stores input messages, while `Turn.output_messages` stores
  the terminal agent response. `Turn.record(messages=..., output_messages=...)`
  replaces the two lists independently.
- `SubAgent` owns its input/output messages and originating tool-call
  arguments/result. Integrations populate them through `SubAgent.record()` so
  `_build_attrs()` applies `include_content` and PII redaction; do not write
  those content attributes directly with `set_attributes()`.
- `Tool`, `LLM`, `SubAgent`, and `Turn` expose `record_error(error)` to mark a
  failure without ending the span. It derives `error.type` from the exception;
  call `end()` separately. Context managers do both for escaping exceptions.
- Mypy requires explicit `return None` paths in functions annotated with
  `T | None`; bare `return` and implicit fallthrough trigger return-value
  errors.
- Python `Turn` spans are same-process `invoke_agent` operations and use OTel's
  default `SpanKind.INTERNAL`. Do not set `gen_ai.provider.name` on a `Turn`;
  set it on child `LLM`/`chat` spans, because one turn can use multiple
  providers.
- Keep streaming and batch paths aligned: `Turn._build_attrs()` must apply
  content gating and PII redaction to both lists before passing them to
  `invoke_agent_attributes()`, and `log_turn()` must accept both fields.
- The Python Claude Agent SDK integration taps async prompt iterables, queues
  user inputs in FIFO order, and closes one `Turn` for each `ResultMessage`.
- Keep its output adapters split by SDK contract: string `query()` and each
  `ClaudeSDKClient.receive_response()` use the linear single-turn tracer, while
  only standalone `query(AsyncIterable)` uses multi-result queue/lookahead logic.
- Standalone async-iterable queries can emit bootstrap `system/init` before the
  first prompt is consumed. Defer only that init for trace attribution; forward
  other output received without a pending query-triggering input without
  attaching it to the next turn, especially late background-task notifications.
  Correctly completing background subagents across results requires separate
  conversation-scoped task ownership.
- Name the corresponding test cases "string prompt" and "async-iterable
  prompt" rather than sync/async: both SDK entry points are asynchronous. Keep
  one-input success and pre/post-result failure assertions paired across them.
- SDK output can fail before the first message or between completed turns. Keep
  the submitted/pending input observable by ending its `Turn` through the
  exception path so the span records the error before the exception propagates.
- The Agents conversation tree renders recognized GenAI operations. Generic
  OTel spans with an empty `gen_ai.operation.name` remain stored and queryable
  through `agent_spans_query`, but are omitted from that visual tree; use a
  semantic marker span when a UI-visible trace regression is required.
- For spans with `ERROR` status, missing `error_type` and `status_message`
  fall back to the latest OTel `exception` event. Explicit `error.type` and
  status-message values take precedence, and handled exception events on
  non-error spans remain raw-only.
- Content spans with `ERROR` status emit a chat message even without text or
  reasoning so the conversation timeline retains the failure. Successful empty
  tool-calling steps remain omitted.
- Use the Trace tree view for parentage comparisons. The default flamegraph
  collapses overlapping siblings into synthetic groups, which can make flat
  and nested traces look deceptively similar; give live-example spans realistic
  duration and verify their stored parent IDs with `agent_spans_query`.

### Claude Agent SDK token accounting

- Anthropic reports Claude Agent SDK `input_tokens` as fresh, uncached input
  only. Weave usage requires an inclusive prompt total, with
  `cache_read_input_tokens` and `cache_creation_input_tokens` represented as
  subsets of `input_tokens`, because cost and cache-hit-rate rollups use that
  convention.
- Both Python tracing paths must normalize aggregate result usage through
  `weave/integrations/claude_agent_sdk/usage.py`. Keep the SDK's yielded
  `ResultMessage` and the calls-based root output unchanged; normalize the
  calls-based usage summary and the OTel span attributes consumed by Weave
  rollups.
- Regression coverage must exercise both the calls-based and OTel integrations
  with nonzero cache-read and cache-creation counts.
- The OTel-selected Claude Agent SDK path composes the Python GenAI
  `Conversation`, `Turn`, `LLM`, `Tool`, and `SubAgent` handles; it must not
  create raw OTel spans or call the low-level GenAI attribute builders itself.
  Use `set_attributes()` only for semantic fields the typed handles do not
  expose. The legacy calls-based path remains separate.
- Tap Python `AsyncIterable[dict]` prompts without consuming or cloning them.
  Map Claude text and base64/URL image blocks to GenAI text, blob, and URI
  parts; media payloads remain data for `content_refs`, not chat prose.
- Treat `Agent` and legacy `Task` tool calls as subagents keyed by tool-use ID.
  Route nested assistant messages and tools through `parent_tool_use_id`.
  Synchronous calls close on their matching tool result; background launch
  acknowledgements stay open until `task_notification`. Dispatch task events
  through `SystemMessage.subtype` and `data`, map `task_id` to tool-use ID from
  `task_started` / `task_progress`, and do not import typed task messages that
  are absent from older supported Claude Agent SDK versions.
- Start those subagents with `SubAgent.start(set_current=False)`, never
  `__enter__`. Parallel delegations close in completion order, and `end()`
  detaches through `ContextVar.reset`, so an out-of-LIFO close leaves the
  ambient OTel context pointing at an ended span — user code running between
  streamed messages would nest under it. Children nest either way, because
  `start_llm` / `start_tool` / `start_subagent` thread an explicit parent.
- Stream adapters can create child handles when work starts, then enter them
  with a normal `with` when the completion message arrives. Preserve logical
  timing with `LLM.started_at` and an explicit `Tool.started_at` instead of
  keeping contexts open with `ExitStack`.

### PII redaction primitives

- `SensitiveDataPolicy` is a closed `off` or `pii-v1` enum. Unknown values
  fail instead of falling back to a policy.
- `redact_pii_value` walks supported trace values copy-on-write, combines
  credential-key replacement with PII replacement, and never scans dictionary
  keys. Clean subtrees retain their identity.
- Complete Weave refs, valid base64 data URLs, and valid standalone base64
  payloads pass through unchanged. Malformed lookalikes remain eligible for
  scanning.

### Credential-shaped fields in client-authored call columns

- The three call converters in `clickhouse/schema_converters.py` run
  `redact_sensitive_keys` over `inputs` and `attributes` before extracting refs,
  so a field whose name matches the policy in
  `weave/trace_server/credential_redaction.py` is stored with its string value
  replaced. `in_memory_trace_server.py` applies the same function, so both
  backends read back the same thing.
- The same converters redact `otel_dump`. It is a raw copy of the client's span,
  so it carries the attribute values that `attributes_dump` holds a second time,
  and it is a public field on the insert schemas, so the OTel route is not its
  only producer.
- The walk is copy-on-write and replaces only non-empty strings. Both properties
  are load-bearing — see the module docstring — so keep them if you touch it.

### Agent PII policy

- `GenAIOTelExportReq.sensitive_data_policy` is an internal, omittable,
  non-nullable field. Omission resolves to `off`.
- An authorized server route may set `pii-v1` from the owning organization's
  policy. Never populate the field from caller-controlled OTLP content or a
  process environment fallback.
- Agent OTel ingest parses and redacts every span (each shared resource once)
  before credential redaction, blob stripping, derived-column extraction, or
  insertion starts for any of them. A redaction failure rejects the whole
  request before any Content file write or insert; a value nested too deeply
  to scan is rejected as `RequestTooLarge` (HTTP 413).
- PII redaction covers span and event names, all four attribute containers,
  and the status message. Names feed the `span_name`, `operation_name`, and
  `agent_name` grouping columns, so a PII-bearing name changes grouping and
  agent identity; redaction wins that trade-off. IDs, trace state, and
  timestamps are structural and remain unchanged.
- `pii-v1` scans strings and never decodes payloads: non-string leaves,
  including raw bytes (stored base64-encoded in dumps), pass through
  unchanged, like the preserved data URLs and standalone base64.

### Credential-shaped fields in agent span columns
- The agents OTel ingest calls `redact_credentials_from_span` before
  `strip_inline_blobs_from_span`, and outside the file-storage guard around it.
  Both are load-bearing — see that function's docstring — so keep the order and
  the placement if you touch it.
- It redacts all four attribute containers a span carries: its own, its resource,
  its events and its links. The output columns derive from those too, so on this
  path a credential-shaped name inside a structured output is replaced as well.
- The completions path builds a span row without a parsed OTel span, so it never
  reaches that hook. `build_completion_span` redacts the request once and every
  column that can carry a client string reads that copy; the provider response is
  left as the provider sent it, because a response is generated content.

### Documentation

- Update relevant docstrings for Python code
- Add JSDoc comments for TypeScript code
- Update this file when introducing new patterns or concepts

---

## Integration Patching

### Automatic Implicit Patching

Weave provides automatic implicit patching for all supported integrations using an import hook mechanism:

- **Automatic Patching**: Libraries are automatically patched regardless of when they are imported
- **Import Hook**: An import hook intercepts library imports and applies patches automatically
- **Explicit Patching**: Optional manual patching is still available for fine-grained control

Example:

```python
# Automatic patching - works regardless of import order!

# Option 1: Import before weave.init()
import openai
import weave
weave.init('my-project')  # OpenAI is automatically patched!

# Option 2: Import after weave.init()
import weave
weave.init('my-project')
import anthropic  # Automatically patched via import hook!

# Option 3: Explicit patching (optional)
import weave
weave.init('my-project')
weave.patch_openai()  # Manually patch if needed
```

### Available Patch Functions

All integrations have corresponding patch functions for explicit control: `patch_openai()`, `patch_anthropic()`, `patch_mistral()`, etc.

### Technical Implementation

The import hook uses Python's `sys.meta_path` to intercept imports and automatically apply patches when supported libraries are imported. This ensures seamless integration tracking without requiring users to manage import order or make explicit patch calls.

### Disabling Implicit Patching

If you prefer explicit control over which integrations are patched, you can disable implicit patching:

```python
# Via settings parameter
weave.init('my-project', settings={'implicitly_patch_integrations': False})

# Via environment variable
export WEAVE_IMPLICITLY_PATCH_INTEGRATIONS=false
```

When disabled, you must explicitly call patch functions like `weave.patch_openai()` to enable tracing for integrations.

# Requests to Humans

This section contains a list of questions, clarifications, or tasks that LLM agents wish to have humans complete.
If there is something that doesn't make sense architecturally, devex-wise, or product-wise, please update this file and the humans will take care of it.
Think of this as the reverse-task assignment - a place where you can communicate back to us.

- [ ] Add TypeScript testing guidelines
- [ ] Add `output_messages` to Python `Turn.record()` for parity with
      TypeScript `Turn.record({outputMessages: ...})`; the lower-level Python
      `invoke_agent_attributes()` builder already supports agent output.
- [ ] Repair the existing `pnpm run typecheck:examples` failures caused by
      OpenAI type drift in `examples/agent.ts`, `classesWithOps.ts`,
      `imageGeneration.ts`, `quickstart*.ts`, and `streamFunctionCalls.ts`.
- [ ] Isolate Node GenAI test exit hooks: a full in-band Jest run can register
      more than ten `beforeExit` listeners and flush queued test calls to the
      real trace server after teardown when developer W&B credentials are
      present, turning an otherwise-green run into a post-test failure.
- [ ] ...
