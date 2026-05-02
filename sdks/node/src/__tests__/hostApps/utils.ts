/**
 * Per-test helpers for the hostApps Jest project. Tests resolve the
 * Weave trace-server-mock URL from a sentinel JSON file written by
 * `jest.global-setup.cjs` (parallel workers don't inherit globalThis or
 * env mutations from globalSetup). They generate a fresh project_id per
 * test, launch a host application via `launchAppFrom()`, then query the
 * trace-server mock to assert on captured traces.
 *
 * `launchAppFrom({path, projectId})` runs `npm run <scriptName>` (default
 * `start`) inside any directory that has a `package.json`. Each host app
 * defines its own launch command — `node main.cjs` for CJS,
 * `node --import=weave/instrument main.mjs` for ESM, etc. — keeping
 * runtime invocation co-located with the app, matching how a real
 * consumer would launch the same app.
 */

import {randomUUID} from 'crypto';
import {spawn} from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

type HostAppsState = {
  traceServerMockUrl: string;
};

const STATE_SENTINEL = path.join(os.tmpdir(), 'weave-hostapps-state.json');

let cachedState: HostAppsState | null = null;

function getState(): HostAppsState {
  if (cachedState) return cachedState;
  if (!fs.existsSync(STATE_SENTINEL)) {
    throw new Error(
      `hostApps state sentinel ${STATE_SENTINEL} not found — globalSetup likely did not run.`
    );
  }
  cachedState = JSON.parse(
    fs.readFileSync(STATE_SENTINEL, 'utf8')
  ) as HostAppsState;
  return cachedState;
}

export function getTraceServerMockUrl(): string {
  return getState().traceServerMockUrl;
}

export function genProjectId(): string {
  // entity/project form, so init() skips the wandb defaultEntityName lookup.
  return `hostapps/${randomUUID()}`;
}

/** Resolve a host app name to its absolute path under `hostApps/fixtures/`. */
export function fixturePath(name: string): string {
  return path.resolve(__dirname, 'fixtures', name);
}

export interface LaunchResult {
  exitCode: number | null;
  stdout: string;
  stderr: string;
}

/**
 * Run `npm run <scriptName>` inside the given fixture directory and
 * resolve when the child exits.
 *
 * The fixture's `package.json` declares its own launch command (e.g.
 * `node main.cjs` for CJS, `node --import=weave/instrument main.mjs` for
 * ESM). The driver knows nothing about the runtime invocation — that's
 * the fixture's responsibility, mirroring how a real consumer would run
 * the same app.
 *
 * Spawned with `detached: true` so the child becomes its own process
 * group leader; SIGTERM/SIGKILL on timeout uses `process.kill(-pid)` to
 * tear down the npm wrapper plus the underlying Node process together.
 */
export function launchAppFrom(opts: {
  path: string;
  projectId: string;
  scriptName?: string;
  extraEnv?: NodeJS.ProcessEnv;
  timeoutMs?: number;
}): Promise<LaunchResult> {
  const state = getState();
  const scriptName = opts.scriptName ?? 'start';
  const cwd = opts.path;

  return new Promise((resolve, reject) => {
    const child = spawn('npm', ['run', '--silent', scriptName], {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: true,
      env: {
        ...process.env,
        WF_TRACE_SERVER_URL: state.traceServerMockUrl,
        WANDB_API_KEY: 'dummy-hostapps-key',
        WANDB_BASE_URL: 'http://localhost:0',
        WANDB_PROJECT: opts.projectId,
        ...opts.extraEnv,
      },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', d => (stdout += d.toString()));
    child.stderr.on('data', d => (stderr += d.toString()));

    let timedOut = false;
    const timeout = setTimeout(
      () => {
        timedOut = true;
        // Kill the whole process group so npm + node both die.
        try {
          if (child.pid) process.kill(-child.pid, 'SIGKILL');
        } catch {
          /* already gone — fine */
        }
      },
      opts.timeoutMs ?? 30_000
    );

    child.on('exit', code => {
      clearTimeout(timeout);
      if (timedOut) {
        reject(
          new Error(
            `app at ${cwd} timed out\nstdout:\n${stdout}\nstderr:\n${stderr}`
          )
        );
        return;
      }
      resolve({exitCode: code, stdout, stderr});
    });
    child.on('error', err => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}

interface CallRecord {
  op_name?: string;
  project_id?: string;
  id?: string;
  trace_id?: string;
  [k: string]: unknown;
}

export async function getCalls(projectId: string): Promise<CallRecord[]> {
  const url = `${getTraceServerMockUrl()}/test/getCalls?project_id=${encodeURIComponent(projectId)}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`getCalls(${projectId}) returned ${res.status}`);
  }
  const body = (await res.json()) as {calls: CallRecord[]};
  return body.calls;
}

export async function resetCalls(projectId?: string): Promise<void> {
  const url = projectId
    ? `${getTraceServerMockUrl()}/test/reset?project_id=${encodeURIComponent(projectId)}`
    : `${getTraceServerMockUrl()}/test/reset`;
  const res = await fetch(url, {method: 'POST'});
  if (!res.ok) {
    throw new Error(`reset returned ${res.status}`);
  }
}
