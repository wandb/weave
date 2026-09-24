// `openai` first, then `weave`, and the client wrapped right after init(), as
// examples/imageGeneration.ts does. init() should stay quiet here too.

const {OpenAI} = require('openai');
const weave = require('weave');

(async () => {
  await weave.init(process.env.WANDB_PROJECT);
  const client = weave.wrapOpenAI(new OpenAI({apiKey: 'unused'}));
  console.log(`create: ${client.chat.completions.create.name}`);
})();
