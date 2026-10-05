// Two CommonJS copies of weave, as when a dependency brings its own, both
// loaded before openai. Both hook require('openai'), so the client is wrapped
// before wrapOpenAI() from the second copy receives it. fetch is stubbed, so
// the app needs no network.

const path = require('path');

require('weave');
// A fresh evaluation of weave's files is a second copy of the SDK.
const weaveDir = `${path.sep}node_modules${path.sep}weave${path.sep}`;
for (const file of Object.keys(require.cache)) {
  if (file.includes(weaveDir)) {
    delete require.cache[file];
  }
}
const weave = require('weave');
const {OpenAI} = require('openai');

const reply = {
  id: 'chatcmpl-1',
  object: 'chat.completion',
  created: 1,
  model: 'gpt-4o-mini',
  choices: [
    {
      index: 0,
      message: {role: 'assistant', content: 'Paris', refusal: null},
      logprobs: null,
      finish_reason: 'stop',
    },
  ],
  usage: {prompt_tokens: 4, completion_tokens: 1, total_tokens: 5},
};

(async () => {
  const client = await weave.init(process.env.WANDB_PROJECT);
  const openai = weave.wrapOpenAI(
    new OpenAI({
      apiKey: 'unused',
      fetch: async () =>
        new Response(JSON.stringify(reply), {
          status: 200,
          headers: {'content-type': 'application/json'},
        }),
    })
  );
  const completion = await openai.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{role: 'user', content: 'Which city?'}],
  });
  console.log(`reply: ${completion.choices[0].message.content}`);
  await client.waitForBatchProcessing();
})();
