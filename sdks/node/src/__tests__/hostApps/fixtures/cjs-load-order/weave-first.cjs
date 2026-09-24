// The supported CJS order, and the control for library-first.cjs: `weave` is
// required first, the hook patches `openai`, and init() stays quiet.

const weave = require('weave');
require('openai');

(async () => {
  await weave.init(process.env.WANDB_PROJECT);
})();
