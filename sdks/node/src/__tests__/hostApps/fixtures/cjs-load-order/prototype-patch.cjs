// A library whose hook patches prototypes, required before weave. With
// --require-again it is required again after weave: the hook then patches the
// prototypes, which reaches the client created first, and init() should stay
// quiet. Without it, the client stays unpatched and init() should warn.

const fs = require('fs');
const path = require('path');

// A stand-in for @anthropic-ai/sdk with only what the hook patches. It must be a
// real directory under node_modules: the hook does not recognize a symlink.
const dir = path.join(__dirname, 'node_modules', '@anthropic-ai', 'sdk');
fs.mkdirSync(dir, {recursive: true});
fs.writeFileSync(
  path.join(dir, 'package.json'),
  JSON.stringify({
    name: '@anthropic-ai/sdk',
    version: '0.60.0',
    main: 'index.js',
  })
);
fs.writeFileSync(
  path.join(dir, 'index.js'),
  `class Batches { create() {} retrieve() {} results() {} }
class Messages { create() {} stream() {} }
Messages.Batches = Batches;
class Anthropic { constructor() { this.messages = new Messages(); } }
Anthropic.Messages = Messages;
module.exports = {Anthropic};
`
);

const {Anthropic} = require('@anthropic-ai/sdk');
const client = new Anthropic();
const originalCreate = client.messages.create;
const weave = require('weave');
if (process.argv.includes('--require-again')) {
  require('@anthropic-ai/sdk');
}

(async () => {
  console.log(`patched: ${client.messages.create !== originalCreate}`);
  await weave.init(process.env.WANDB_PROJECT);
})();
