// Two CommonJS copies of `weave` in one process, as when a dependency brings
// its own: the first copy's hook patches `openai`, then the second copy loads.
// init() should stay quiet, because the first copy's hook did patch it.

const path = require('path');

require('weave');
const {OpenAI} = require('openai');

// A fresh evaluation of weave's files shares process-wide state with the first.
const weaveDir = `${path.sep}node_modules${path.sep}weave${path.sep}`;
for (const file of Object.keys(require.cache)) {
  if (file.includes(weaveDir)) {
    delete require.cache[file];
  }
}
const weave = require('weave');

(async () => {
  const create = new OpenAI({apiKey: 'unused'}).chat.completions.create;
  console.log(`create: ${create.name}`);
  await weave.init(process.env.WANDB_PROJECT);
})();
