import "source-map-support/register";
import { OpenAI } from "openai";
import { init, wrapOpenAI, op, Dataset, Evaluation, weaveImage } from "weave";

const sentences = [
  "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
  "Pounits are a bright green color and are more savory than sweet.",
  "Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.",
  "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
];
const labels = [
  { fruit: "neoskizzles", color: "purple", flavor: "candy" },
  { fruit: "pounits", color: "bright green", flavor: "savory" },
  { fruit: "glowls", color: "pale orange", flavor: "sour and bitter" },
];
const examples = [
  { id: "0", sentence: sentences[0], target: labels[0] },
  { id: "1", sentence: sentences[1], target: labels[1] },
  { id: "2", sentence: sentences[2], target: labels[2] },
];

const openaiClient = wrapOpenAI(new OpenAI());

const model = op(async function myModel({ datasetRow }) {
  const prompt = `Extract fields ("fruit": <str>, "color": <str>, "flavor") from the following text, as json: ${datasetRow.sentence}`;
  const response = await openaiClient.chat.completions.create({
    model: "gpt-3.5-turbo",
    messages: [{ role: "user", content: prompt }],
    response_format: { type: "json_object" },
  });
  const result = response.choices[0].message.content;
  if (result == null) {
    throw new Error("No response from model");
  }
  if (datasetRow.id == "3") {
    throw new Error("This is an error");
  }
  return JSON.parse(result);
});

async function main() {
  await init("weavejsdev-evalwithimage");
  const ds = new Dataset({
    id: "Fruit Dataset",
    rows: examples,
  });
  const evaluation = new Evaluation({
    dataset: ds,
    scorers: [
      op(function fruitEqual({ modelOutput, datasetRow }) {
        return {
          correct: modelOutput.fruit == datasetRow.target.fruit,
        };
      }),
      op(async function genImage({ modelOutput, datasetRow }) {
        const result = await openaiClient.images.generate({
          prompt: `A fruit that's ${modelOutput.color} and ${modelOutput.flavor}`,
          n: 1,
          size: "256x256",
          response_format: "b64_json",
        });
        return result.data[0];
        // console.log('RESULT', result)
        // const buffer = Buffer.from(result.data[0].b64_json!, 'base64')
        // return weaveImage({ data: buffer, imageType: 'png' })
      }),
    ],
  });

  const results = await evaluation.evaluate({ model });
  console.log(JSON.stringify(results, null, 2));
}

main();
