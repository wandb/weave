# Host-app integration tests (`pnpm run test:hostApps`)

A separate Jest project (`hostApps`) exercises the **packaged** SDK end-to-end
through detached host applications that consume it as a real installed
dependency — exercising Node's actual module-loading behavior across CJS
`require()`, ESM `import`, and the package's subpath exports. Unlike the
default suite — which tests source files directly via `ts-jest` — these
tests:

1. Build the SDK with `tsc-multi` (both `dist/index.js` and `dist/index.mjs`).
2. `npm pack` the result into a tarball.
3. Auto-discover every directory under `src/__tests__/hostApps/fixtures/`
   that has a `package.json` and `npm install` the tarball into it
   (committed scaffold projects, `node_modules/` gitignored).
4. Spawn `python -m in_memory_trace_server` (the in-memory mock trace
   server at the repo root in `in_memory_trace_server/`) on an ephemeral
   port.
5. Launch each host app via `launchAppFrom({path, projectId})`, which runs
   `npm run start` (the script declared by the host app's own `package.json`
   — e.g. `node main.cjs` for CJS, `node --import=weave/instrument main.mjs`
   for ESM). `WF_TRACE_SERVER_URL` is pointed at the mock; each test gets
   a unique `project_id` for isolation.
6. Query the mock's `GET /test/getCalls?project_id=X` to assert on captured
   traces.

## Adding a new host app

Drop a directory under `src/__tests__/hostApps/fixtures/` with:

- `package.json` declaring `"scripts": {"start": "..."}`. The start script
  is whatever node invocation that scenario needs — the test driver knows
  nothing about it.
- An entry script (`main.cjs`, `main.mjs`, whatever the start script
  references).

(`node_modules/` and `package-lock.json` are gitignored at the `fixtures/`
level, so new host apps don't need their own `.gitignore`.)

Then add a `*.test.ts` calling
`launchAppFrom({path: fixturePath('your-folder'), projectId})`. No driver
code change required — the host app is auto-installed at test start.

## Prerequisites

- Node 18+ (uses global `fetch`).
- Python 3.10+ and `uv` on `PATH` — the mock server is a `uv`-managed Python
  package.

## Run

```sh
pnpm run test:hostApps
```

For fast iteration when you've already built once:

```sh
HOST_APPS_SKIP_BUILD=1 pnpm run test:hostApps
```

## Manual debugging of a host app

The host apps are real, runnable projects. To debug outside Jest:

```sh
# in one shell, start the mock on a known port:
cd in_memory_trace_server
uv run python -m in_memory_trace_server --port=6346

# in another shell, install the tarball and run a host app by hand:
cd sdks/node
pnpm run build
npm pack --pack-destination /tmp/weave-pack
cd src/__tests__/hostApps/fixtures/cjs-basic
npm install --no-save /tmp/weave-pack/weave-*.tgz
WF_TRACE_SERVER_URL=http://127.0.0.1:6346 \
  WANDB_API_KEY=dummy \
  WANDB_PROJECT=hostapps/local \
  npm run start

# then inspect what the mock captured:
curl 'http://127.0.0.1:6346/test/getCalls?project_id=hostapps/local' | jq
```

The ESM host app runs identically — `npm run start` invokes its own
`node --import=weave/instrument main.mjs` declared in its `package.json`.
