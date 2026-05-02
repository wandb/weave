// CJS smoke fixture: load the published `weave` package via require(),
// initialize against the Weave trace-server mock, run a trivial op,
// flush, exit.
//
// Configuration comes entirely from env vars set by the test driver:
//   WF_TRACE_SERVER_URL — points at the spawned Python trace-server mock
//   WANDB_API_KEY       — dummy; the trace-server mock accepts any auth
//   WANDB_PROJECT       — `entity/project`, chosen per-test for isolation

const weave = require('weave');

(async () => {
  const client = await weave.init(process.env.WANDB_PROJECT);
  const myOp = weave.op(function myOp(x) {
    return x + 1;
  });
  await myOp(41);
  await client.waitForBatchProcessing();
})().catch(err => {
  console.error(err);
  process.exit(1);
});
