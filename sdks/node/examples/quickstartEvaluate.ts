import {OpenAI} from 'openai';
import 'source-map-support/register';
import * as weave from 'weave';

const sentences = [
  'There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.',
  'Pounits are a bright green color and are more savory than sweet.',
  'Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.',
];
const labels = [
  {fruit: 'neoskizzles', color: 'purple', flavor: 'candy'},
  {fruit: 'pounits', color: 'bright green', flavor: 'savory'},
  {fruit: 'glowls', color: 'pale orange', flavor: 'sour and bitter'},
];
const examples = [
  {id: '0', sentence: sentences[0], target: labels[0]},
  {id: '1', sentence: sentences[1], target: labels[1]},
  {id: '2', sentence: sentences[2], target: labels[2]},
  {id: '3', sentence: sentences[0], target: labels[0]},
  {id: '4', sentence: sentences[1], target: labels[1]},
  {id: '5', sentence: sentences[2], target: labels[2]},
  {id: '6', sentence: sentences[0], target: labels[0]},
  {id: '7', sentence: sentences[1], target: labels[1]},
  {id: '8', sentence: sentences[2], target: labels[2]},
  {id: '9', sentence: sentences[0], target: labels[0]},
  {id: '10', sentence: sentences[1], target: labels[1]},
  {id: '11', sentence: sentences[2], target: labels[2]},
];

const openaiClient = weave.wrapOpenAI(new OpenAI());

const model = weave.op(async function myModel(input) {
  const prompt = `Extract fields ("fruit": <str>, "color": <str>, "flavor") from the following text, as json: ${input.sentence}`;
  const response = await openaiClient.chat.completions.create({
    model: 'gpt-3.5-turbo',
    messages: [{role: 'user', content: prompt}],
    response_format: {type: 'json_object'},
  });
  const result = response.choices[0].message.content;
  if (result == null) {
    throw new Error('No response from model');
  }
  return JSON.parse(result);
});

async function main() {
  await weave.init('examples');
  const ds = new weave.Dataset({
    id: 'Fruit Dataset',
    rows: examples,
  });
  const evaluation = new weave.Evaluation({
    dataset: ds,
    scorers: [
      weave.op(function fruitEqual({modelOutput, datasetRow}) {
        return {
          correct: modelOutput.fruit == datasetRow.target.fruit,
        };
      }),
    ],
  });

  const results = await evaluation.evaluate({model});
  console.log(JSON.stringify(results, null, 2));
}

main();
