# Agent instructions for `weave` repository

## Rules

- When you learn something new about the codebase or introduce a new concept, update this file (`AGENTS.md`) to reflect the new knowledge. This is YOUR FILE! It should grow and evolve with you.
- If there is something that doesn't make sense architecturally, devix-wise, or product-wise, please update the `Requests to Humans` section below.

## Dev Setup
- Your machine should be setup for you automatically. However, it is possible that something breaks over time. If you have any issues, please update `bin/codex_setup.sh` accordingly which will run before your next task.

## Directory Structure
- `weave/` - contains the implementation of the `weave` python package as well as the backend server implementation (`weave/trace_server`)
- `docs/` - contains the docs wedbsite
- `weave_query` - DO NOT EDIT - contains a legacy codebase that needs to be refactored out
- `weave-js` - contains the frontend code AND some company-specific common components. Very oddly, the webapp entry point is `weave-js/src/components/PagePanelComponents/Home/Browse3.tsx` (`Browse3` component).
    * Note: as of this writing, you will not be able to run the webapp since it is hosted and mounted in a proprietry location. Do not try.

## Testing
* Testing is managed by `nox`. We have multiple shards representing differnt python versions and package configurations.
* You can let CI run most tests. For simplicity, focus on:
    * `tests-3.12(shard='trace')`
    * `tests-3.12(shard='flow')`
    * `tests-3.12(shard='trace_server')`
    * `tests-3.12(shard='trace_server_bindings')`

## PR Submissions
* Make sure to run `nox -e lint` before committing (this will MODIFY files - be aware)
* PR titles must start with `chore(weave):`, `feat(weave):`, or `fix(weave):`
* Please make PR summaries detailed.

---

# Requests to Humans

This section contains a list of questions, clarifications, or tasks that LLM agents wish to have humans complete.
If there is something that doesn't make sense architecturally, devix-wise, or product-wise, please update this file and the humans will take care of it.
Think of this as the reverse-task assignment - a place where you can communicate back to us.

- [ ] ...