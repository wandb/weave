// ESM smoke fixture: import the published `weave` package, initialize
// against the Weave trace-server mock, run a trivial op, flush, exit.
// Launched via `node --import=weave/instrument main.mjs` (declared in
// this fixture's package.json `scripts.start`) so the ESM loader hook is
// in place — same invocation pattern real ESM consumers use.
//
// Configuration comes entirely from env vars set by the test driver:
//   WF_TRACE_SERVER_URL — points at the spawned Python trace-server mock
//   WANDB_API_KEY       — dummy; the trace-server mock accepts any auth
//   WANDB_PROJECT       — `entity/project`, chosen per-test for isolation

import * as weave from 'weave';

const client = await weave.init(process.env.WANDB_PROJECT);
const myOp = weave.op(function myOp(x) {
  return x + 1;
});
await myOp(41);
await client.waitForBatchProcessing();
