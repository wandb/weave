/**
 * Global teardown for the hostApps Jest project.
 *
 * Sends SIGTERM to the Python Weave trace-server mock subprocess started
 * in globalSetup, then SIGKILL after a short grace period, then removes
 * the temp pack dir. The host-app `node_modules/` dirs are left in place
 * so iterative reruns can skip the install step (gitignored, harmless
 * across runs).
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const KILL_GRACE_MS = 2000;
const STATE_SENTINEL = path.join(os.tmpdir(), 'weave-hostapps-state.json');

function log(msg) {
  console.log(`[hostApps:teardown] ${msg}`);
}

function killWithGrace(pid) {
  if (!pid) return Promise.resolve();
  try {
    process.kill(pid, 'SIGTERM');
  } catch {
    // Already gone — nothing to do.
    return Promise.resolve();
  }
  return new Promise(resolve => {
    const deadline = Date.now() + KILL_GRACE_MS;
    const tick = () => {
      try {
        // Signal 0 is a probe — throws if the process is gone.
        process.kill(pid, 0);
      } catch {
        return resolve();
      }
      if (Date.now() >= deadline) {
        try {
          process.kill(pid, 'SIGKILL');
        } catch {
          /* already gone */
        }
        return resolve();
      }
      setTimeout(tick, 50);
    };
    tick();
  });
}

module.exports = async function globalTeardown() {
  if (!fs.existsSync(STATE_SENTINEL)) return;
  const state = JSON.parse(fs.readFileSync(STATE_SENTINEL, 'utf8'));
  log(`killing trace-server mock pid=${state.traceServerMockPid}`);
  await killWithGrace(state.traceServerMockPid);
  if (state.packDir) {
    try {
      fs.rmSync(state.packDir, {recursive: true, force: true});
    } catch (e) {
      log(`failed to remove ${state.packDir}: ${e.message}`);
    }
  }
  fs.rmSync(STATE_SENTINEL, {force: true});
};
