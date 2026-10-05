// Library first, and the app exits right after init(), before the timer that
// normally runs the check. The exit listener must still warn.

require('openai');
const weave = require('weave');

(async () => {
  await weave.init(process.env.WANDB_PROJECT);
  process.exit(0);
})();
