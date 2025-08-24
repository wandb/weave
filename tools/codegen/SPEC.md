## Trace Server Bindings Codegen Spec (Stainless)

### Goals
- **Generate bindings** for the trace server from OpenAPI using Stainless.
- **Simple CLI** to fetch the OpenAPI spec and generate bindings.
- **Separate bindings repo** per language; start with Python at `weave_server_sdk`.
- **Keep bindings in sync** with the trace server API; provide utilities to push/publish from this repo.

### Scope (Phase 1)
- **Language**: Python only (`weave_server_sdk`).
- **OpenAPI Source**: Generated from the local reference server in this repository.
- **Stainless**: Use a pre-configured Stainless project and config in `tools/codegen/openapi.stainless.yml`.

### Repositories
- **Source of truth**: This repo (trace server + OpenAPI generator + codegen CLI).
- **Generated SDK repo (Python)**: `weave_server_sdk` (cloned locally; path supplied via config/CLI).

### OpenAPI Generation
- Serve the reference FastAPI app locally and GET `/openapi.json`.
- Save spec to `tools/codegen/openapi.json` (or path overridden by CLI).
- Existing command: `get_openapi_spec` in `tools/codegen/generate.py`.

### Stainless Configuration
- Config lives at `tools/codegen/openapi.stainless.yml`.
- Targets (Phase 1): Python only (`package_name: weave_server_sdk`).
- Authentication: HTTP Basic (configured in Stainless client settings).
- Resources and transformations defined in the YAML are the single source of config.

### CLI Design
- Single entrypoint with subcommands (Typer-based): `tools/codegen/generate.py`.
- Provide Makefile alias: `make generate-bindings ARGS="<subcommand and flags>"`.

#### Commands
- `get_openapi_spec [-o OUTPUT]`
  - Starts a temp server (`uvicorn weave.trace_server.reference.server:app --port 6345`), fetches OpenAPI, writes to OUTPUT (default: `tools/codegen/openapi.json`).
- `generate_code --python-path=/abs/path/to/weave_server_sdk [--node-path=...] [--typescript-path=...]`
  - Invokes Stainless build with `openapi.stainless.yml` and the saved OAS.
  - Requires env vars: `STAINLESS_API_KEY`, `GITHUB_TOKEN`.
- `merge_generated_code PYTHON_OUTPUT PACKAGE_NAME`
  - Operates inside the local `weave_server_sdk` repo (PYTHON_OUTPUT):
    - Ensures local branch `main` has generated code (post-Stainless run).
    - Creates a branch `weave/<current-trace-repo-branch>` off `origin/main`.
    - Checks out the generated code from local `main` into that branch.
    - Commits and pushes the branch to `origin`.
    - Updates this repo's `pyproject.toml` `[project.optional-dependencies.stainless]` entry for `PACKAGE_NAME` to `git+<remote_url>@<sha>`.
- `update_pyproject PYTHON_OUTPUT PACKAGE_NAME [--release]`
  - Alternative to `merge_generated_code` when not auto-merging. Updates `pyproject.toml` to either a published version (`--release`) or a git SHA ref.
- `all [--config tools/codegen/generate_config.yaml] [--python-output <path>] [--package-name weave_server_sdk] [--openapi-output <path>] [--release] [--auto-merge/--no-auto-merge]`
  - End-to-end: get OpenAPI → generate with Stainless → push/update dependency (merge branch or update SHA).

### Configuration
- Default config file: `tools/codegen/generate_config.yaml` (user-local; ignored by git).
- Template: `tools/codegen/generate_config.yaml.template`.
- Required:
  - `python_output`: absolute path to a local clone of `weave_server_sdk`.
  - `package_name`: `weave_server_sdk`.
- Optional:
  - `openapi_output`, `node_output`, `typescript_output`, `release`.

### Sync Strategy
- Bindings are regenerated from the current branch of this repo.
- For each trace repo branch, `merge_generated_code` creates/pushes `weave/<branch>` in `weave_server_sdk` with the generated content.
- This provides a deterministic mapping between trace server changes and SDK branches.
- This repo’s `pyproject.toml` is updated to consume that exact SHA (or version during release).

### Release & Publish (Python)
- Phase 1: No automatic PyPI publish from this repo.
- Workflow:
  1. Run `all --release` to fetch OpenAPI, generate, and update dependency to a published version, or
  2. Run `all` with `--auto-merge` to push a branch to `weave_server_sdk` and then publish from that repo’s CI.
- Future (Phase 2): add optional `publish` subcommand to tag and create a GitHub Release in `weave_server_sdk` (and optionally trigger PyPI publish), using GH CLI or API.

### CI Recommendations
- Add a presubmit job in this repo that runs `make generate-bindings ARGS="all --no-auto-merge --python-output <tmp_path> --package-name weave_server_sdk"` to verify codegen works with the current OpenAPI.
- Add a nightly job that runs `--auto-merge` to refresh the `weave/<main>` branch in `weave_server_sdk` to keep SDK fresh.

### Permissions & Secrets
- Environment variables required locally/CI:
  - `STAINLESS_API_KEY` (Stainless builds)
  - `GITHUB_TOKEN` (Stainless pulls, future PR operations)
- For pushing to `weave_server_sdk`, the local clone must be configured with `origin` remote and authenticated.

### Error Handling (CLI)
- Timeouts and process failures print actionable messages and exit non-zero.
- Port conflicts for the temp server are auto-resolved by killing existing listeners on the chosen port.
- Missing env vars or non-existent repo paths fail early with descriptive errors.

### Example Usage
- Local end-to-end (uses config file):
```bash
make generate-bindings ARGS="all"
```

- Ad-hoc run without config file:
```bash
uv run tools/codegen/generate.py all \
  --python-output /abs/path/to/weave_server_sdk \
  --package-name weave_server_sdk \
  --openapi-output tools/codegen/openapi.json \
  --no-auto-merge
```

- Push generated code to branch in `weave_server_sdk` and update `pyproject.toml` to that SHA:
```bash
uv run tools/codegen/generate.py all \
  --python-output /abs/path/to/weave_server_sdk \
  --package-name weave_server_sdk \
  --auto-merge
```

### Future Enhancements (Phase 2+)
- Add `publish` subcommand to create tags/releases in `weave_server_sdk` and optionally publish to PyPI.
- Add `open-pr` subcommand to automate PR creation in `weave_server_sdk` after branch push.
- Expand targets to Node/TypeScript and wire up equivalent repos.
- Cache OpenAPI and Stainless artifacts; incremental generation.
- Add grouping of heavy/experimental endpoints behind config flags.