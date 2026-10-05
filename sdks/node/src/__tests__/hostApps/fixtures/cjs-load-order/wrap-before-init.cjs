// The quickstart order: `openai` first, then `weave`, and the client wrapped
// with wrapOpenAI() before init(). Tracing does not need the require hook here,
// so init() should stay quiet.

const {OpenAI} = require('openai');
const weave = require('weave');

const client = weave.wrapOpenAI(new OpenAI({apiKey: 'unused'}));

(async () => {
  console.log(`create: ${client.chat.completions.create.name}`);
  await weave.init(process.env.WANDB_PROJECT);
})();
