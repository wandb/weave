/**
 * Global setup for the hostApps Jest project.
 *
 * Runs once before any hostApps test:
 *   1. Build the SDK (skippable via HOST_APPS_SKIP_BUILD=1).
 *   2. `npm pack` the SDK into a temp dir to produce `weave-X.Y.Z.tgz`.
 *   3. Auto-discover host apps: for every direct subdirectory of
 *      `hostApps/fixtures/` that has a `package.json`, install the
 *      tarball via `npm install <tgz> --no-save`. New host apps = new
 *      folders; no driver code change required.
 *   4. Spawn the Python Weave trace-server mock (`python -m
 *      trace_server_mock --port=0`) via `uv run`, parse the
 *      `READY=http://...` banner from stdout, then poll `/test/health`
 *      until it answers.
 *   5. Write a sentinel JSON file at `os.tmpdir()/weave-hostapps-state.json`
 *      containing the trace_server_mock URL, subprocess pid, and
 *      packDir. Tests (which may run in worker processes that don't
 *      inherit anything from globalSetup) and the teardown step read it.
 *
 * The trace-server mock listens on an ephemeral port chosen by
 * globalSetup; tests connect via `getTraceServerMockUrl()` resolved
 * through the sentinel. Per-test isolation comes from each test passing a
 * unique `project_id` to its launched app and querying
 * `/test/getCalls?project_id=X`.
 */

const {execSync, spawn} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const SDK_DIR = path.resolve(__dirname, '..', '..', '..');
const REPO_ROOT = path.resolve(SDK_DIR, '..', '..');
const TRACE_SERVER_MOCK_PROJECT_DIR = path.join(REPO_ROOT, 'trace_server_mock');
const FIXTURES_DIR = path.resolve(__dirname, 'fixtures');
const STATE_SENTINEL = path.join(os.tmpdir(), 'weave-hostapps-state.json');

const HEALTH_TIMEOUT_MS = 10_000;
const HEALTH_POLL_INTERVAL_MS = 50;

function log(msg) {
  console.log(`[hostApps:setup] ${msg}`);
}

function buildSdk() {
  if (process.env.HOST_APPS_SKIP_BUILD === '1') {
    log('HOST_APPS_SKIP_BUILD=1 — skipping `pnpm run build`');
    return;
  }
  log('building SDK (set HOST_APPS_SKIP_BUILD=1 to skip)');
  execSync('pnpm run build', {cwd: SDK_DIR, stdio: 'inherit'});
}

function packSdk(packDir) {
  log(`packing SDK into ${packDir}`);
  fs.mkdirSync(packDir, {recursive: true});
  const out = execSync(`npm pack --pack-destination "${packDir}" --json`, {
    cwd: SDK_DIR,
    encoding: 'utf8',
  });
  const parsed = JSON.parse(out);
  const filename = parsed[0]?.filename;
  if (!filename) {
    throw new Error(`npm pack produced no filename: ${out}`);
  }
  // pnpm-flavored npm sometimes returns a relative path; resolve it.
  const tarball = path.isAbsolute(filename)
    ? filename
    : path.join(packDir, path.basename(filename));
  if (!fs.existsSync(tarball)) {
    throw new Error(`npm pack reported ${tarball} but file is missing`);
  }
  return tarball;
}

function discoverFixtures() {
  if (!fs.existsSync(FIXTURES_DIR)) return [];
  return fs
    .readdirSync(FIXTURES_DIR, {withFileTypes: true})
    .filter(d => d.isDirectory())
    .map(d => path.join(FIXTURES_DIR, d.name))
    .filter(dir => fs.existsSync(path.join(dir, 'package.json')));
}

function installFixture(fixtureDir, tarball) {
  log(`installing tarball into ${path.basename(fixtureDir)}`);
  // --no-save: keep the committed package.json clean. node_modules is gitignored.
  // --no-package-lock: don't churn a lockfile per run.
  // --silent: suppress noisy npm WARN output.
  execSync(
    `npm install --no-save --no-package-lock --silent "${tarball}"`,
    {cwd: fixtureDir, stdio: ['ignore', 'inherit', 'inherit']}
  );
}

function spawnTraceServerMock() {
  log('spawning Python Weave trace-server mock');
  const child = spawn(
    'uv',
    [
      'run',
      '--project',
      TRACE_SERVER_MOCK_PROJECT_DIR,
      'python',
      '-m',
      'trace_server_mock',
      '--port=0',
    ],
    {stdio: ['ignore', 'pipe', 'pipe']}
  );
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', chunk =>
    process.stderr.write(`[trace_server_mock] ${chunk}`)
  );
  return child;
}

function awaitReadyBanner(child) {
  return new Promise((resolve, reject) => {
    let buffer = '';
    let done = false;
    const onData = chunk => {
      buffer += chunk;
      const m = buffer.match(/READY=(\S+)/);
      if (m) {
        done = true;
        child.stdout.off('data', onData);
        resolve(m[1]);
      }
    };
    child.stdout.on('data', onData);
    child.once('exit', code => {
      if (!done) {
        reject(
          new Error(
            `trace-server mock exited (code=${code}) before printing READY banner.\n` +
              `stdout so far:\n${buffer}`
          )
        );
      }
    });
  });
}

async function awaitHealth(url) {
  const start = Date.now();
  let lastErr;
  while (Date.now() - start < HEALTH_TIMEOUT_MS) {
    try {
      const res = await fetch(`${url}/test/health`);
      if (res.ok) {
        const body = await res.json();
        if (body && body.ok === true) return;
      }
      lastErr = new Error(`status=${res.status}`);
    } catch (e) {
      lastErr = e;
    }
    await new Promise(r => setTimeout(r, HEALTH_POLL_INTERVAL_MS));
  }
  throw new Error(
    `trace-server mock /test/health never returned ok=true within ${HEALTH_TIMEOUT_MS}ms; lastErr=${lastErr}`
  );
}

module.exports = async function globalSetup() {
  buildSdk();

  const packDir = fs.mkdtempSync(path.join(os.tmpdir(), 'weave-hostapps-'));
  const tarball = packSdk(packDir);

  const fixtures = discoverFixtures();
  if (fixtures.length === 0) {
    throw new Error(`no fixtures found under ${FIXTURES_DIR}`);
  }
  for (const dir of fixtures) {
    installFixture(dir, tarball);
  }

  const traceServerMock = spawnTraceServerMock();
  const traceServerMockUrl = await awaitReadyBanner(traceServerMock);
  await awaitHealth(traceServerMockUrl);
  log(
    `trace-server mock ready at ${traceServerMockUrl} (pid=${traceServerMock.pid})`
  );

  // Workers don't inherit env mutations or globalThis from globalSetup
  // (Jest 28+), so persist state to a fixed file path. Tests and teardown
  // both read from this sentinel.
  const state = {
    traceServerMockUrl,
    traceServerMockPid: traceServerMock.pid,
    packDir,
    tarball,
  };
  fs.writeFileSync(STATE_SENTINEL, JSON.stringify(state));

  // Don't keep the parent's event loop tied to the child; we kill it
  // explicitly in teardown.
  traceServerMock.unref();
};
