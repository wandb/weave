---
name: integration-updater
description: Check whether a Weave integration's upstream library (e.g. openai, anthropic, langchain) has a newer PyPI release than we support, decide whether our integration code needs updating, and implement it locally for review. Use when asked to update/upgrade/bump an integration, check for a new SDK version, or investigate whether an integration still works against the latest library.
---

# Integration Updater

Given a Weave integration, find out whether its upstream library has published a
newer release than we support, decide whether **our** integration code needs to
change, and — if it does — implement the change locally and leave it for review.

This **complements Dependabot**, it does not duplicate it. Dependabot already
opens weekly PRs that bump minor/patch pins per integration, but it **ignores
major versions** and **never touches integration code**. This skill's value is
exactly those two gaps: major-version jumps, and code that must adapt to an
upstream API change.

## Arguments

`$ARGUMENTS` = one or more integration names (e.g. `openai`, `anthropic mistral`).
Empty = scan every integration and report (no edits).

## Step 1 — Detect (deterministic; do NOT hand-roll this)

Run the sensor script. It parses the current pin from `pyproject.toml`, resolves
the distribution name from the integration's `library_integration(...)` call,
queries PyPI for the latest release, and statically extracts our patch targets:

```bash
uv run scripts/check_integration_updates.py <name> --json
```

To also **live-resolve our patch targets against the latest upstream version**
(the check that catches a silently-broken monkey-patch), install that version
into the run — this needs no change to the project env:

```bash
# Use the distribution + latest_version the first run reported:
uv run --with '<distribution>==<latest_version>' scripts/check_integration_updates.py <name> --json
```

Read the per-integration `status` (highest-signal first):

- **`broken_symbols`** — one or more `SymbolPatcher` targets do not resolve
  against the installed library. Tracing is **silently off** for those calls
  right now. Fix this regardless of the version flags — it can be true even when
  the pin already allows the latest version.
- **`major_update`** — latest crosses a major boundary we've never validated.
  Dependabot will not raise this for you.
- **`capped`** — latest exceeds an intentional upper cap. **Read the cap's
  comment in `pyproject.toml` first** — a cap usually documents a known breakage.
- **`minor_update`** — newer release within our range. Usually Dependabot's job;
  your only duty is to confirm targets still resolve and tests still pass.
- **`up_to_date`** — nothing to do.
- **`unknown`** — PyPI fetch failed (check `notes`; likely offline).

Also read `symbols.dynamic` (targets the script **cannot** check statically,
e.g. `lambda: adk_tracing` — you must reason about these by hand), the `broken`
list (module/attribute/reason), `extra_requirements`, and `notes`.

## Step 2 — Decide whether our code must change

Weave has two integration styles; the check differs:

- **SymbolPatcher style** (openai, anthropic, mistral, groq, cohere, …): the
  fragile surface is the dotted `importlib.import_module("MOD")` + `"Class.method"`
  pairs in `weave/integrations/<name>/*_sdk.py`. `broken_symbols` means one of
  these moved or was removed upstream.
- **Callback/tracer style** (langchain, llamaindex): the script reports **0
  patch targets**. Breakage instead lives in the vendor's callback/tracer
  protocol or pydantic model schema (e.g. a `model_dump` v1/v2 change), which the
  script can't see — inspect the vendor base class the integration subclasses.

Decision guide:

1. **`broken_symbols`** → yes, code must change. For each broken target, find
   where the symbol went in the new library. Inspect the installed package
   (`uv run --with '<dist>==<latest>' python -c "import <mod>; print(<mod>.__file__)"`
   then read it) and consult the library's changelog / migration guide (fetch the
   PyPI project page or the GitHub release notes for the version range). Then
   either **repoint** the `import_module(...)`/`"Class.method"` to the new
   location, or **delete the patcher** if the API was removed for good.
2. **`major_update`** with no live symbol check yet → install the new major and
   re-run the live check (the `--with` form above). If targets still resolve
   *and* the test shard passes under the new version, the only change may be
   raising the pin. If they break, treat as `broken_symbols`.
3. **Signature/shape drift** — a target can still *resolve* while its arguments
   or return shape changed (e.g. streaming-chunk fields the accumulator merges).
   The static check won't catch this; the **test shard** will. Always run it
   (Step 4) against the new version before concluding "no change needed".
4. **`capped`** → open `pyproject.toml`, read the cap's comment, and verify the
   documented reason no longer applies before raising it.

If nothing is broken and it's a plain in-range minor/patch, the correct action
is often **to do nothing and let Dependabot bump the pin** — say so rather than
manufacturing a change.

## Step 3 — Implement (only what Step 2 justified)

- **Patch targets:** edit `weave/integrations/<name>/*_sdk.py`. Keep the change
  minimal; match the surrounding `SymbolPatcher(...)` style.
- **Version pin:** update the entry in `pyproject.toml`
  `[project.optional-dependencies]`. Respect existing caps and their explanatory
  comments — if you raise or remove a cap, update or delete the comment to match
  reality. Don't touch unrelated packages in a multi-package extra (e.g.
  langchain).
- **Tests:** live in `tests/integrations/<name>/`. VCR cassettes at
  `tests/integrations/<name>/cassettes/<test_module>/<test_function>.yaml` bake
  the SDK version into request headers, so a version bump often needs the
  affected cassettes **re-recorded** — which requires a live provider API key.
  You almost certainly cannot do this yourself: **flag which cassettes are stale
  and ask the user to re-record** (`pytest ... --record-mode=rewrite`) rather
  than editing cassette YAML by hand.
- Do **not** edit generated files (`model_providers.json`, `cost_checkpoint.json`).

## Step 4 — Verify

Run the integration's test shard and lint (see AGENTS.md for shard aliases such
as `autogen`→`autogen_tests`, `verifiers`→`verifiers_test`):

```bash
nox --no-install -e "tests-3.12(shard='<name>')" -- tests/integrations/<name>/
uvx ruff check weave/integrations/<name>/ scripts/check_integration_updates.py
```

If ClickHouse/Docker is unavailable, add `--trace-server=fake`. Re-run the
detector's live check to confirm `broken` is now empty.

## Guardrails

- **Never push, open a PR, or post to GitHub.** Implement locally, run tests +
  lint, then hand back a summary of what changed, the evidence, and any stale
  cassettes for the user to review. (Repo rule: pushing needs an explicit ask.)
- **Smallest change that fixes the finding.** Don't upgrade unrelated pins or
  refactor beyond the drift you're fixing.
- **`broken_symbols` outranks everything** — a target that no longer resolves is
  a live tracing outage, even if the pin already permits the version.
- Dynamic targets (`symbols.dynamic`) are invisible to the sensor; reason about
  them manually and note that you did.

## Requirements

- Network access (PyPI + `uv` fetching the upstream package for the live check).
- Run from the repository root.
