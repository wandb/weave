import "source-map-support/register";
import { init, op, Dataset, Evaluation } from "weave";

async function main() {
  await init("weavejsdev-eval6");
  const ds = new Dataset({
    id: "My Dataset",
    description: "This is a dataset",
    rows: [
      { name: "Alice", age: 25 },
      { name: "Bob", age: 30 },
      { name: "Charlie", age: 34 },
    ],
  });
  const evaluation = new Evaluation({
    dataset: ds,
    scorers: [
      op(({ modelOutput, datasetItem }) => modelOutput == datasetItem.age, {
        name: "isEqual",
      }),
    ],
  });

  const model = op(async function myModel(input) {
    return input.age;
  });

  const results = await evaluation.evaluate({ model });
  console.log(JSON.stringify(results, null, 2));
}

main();
