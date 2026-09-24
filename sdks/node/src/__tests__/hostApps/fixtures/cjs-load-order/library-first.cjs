// The unsupported CJS order: the library is required before `weave`, so the
// require hook is installed too late to patch it. init() should say so.
//
// Configuration comes from env vars set by the test driver, as in cjs-basic.

require('openai');
const weave = require('weave');

(async () => {
  await weave.init(process.env.WANDB_PROJECT);
})();
