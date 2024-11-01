import 'source-map-support/register';
import * as weave from 'weave';

async function main() {
  await weave.init('examples');

  const ds = new weave.Dataset({
    id: 'My Dataset',
    description: 'This is a dataset',
    rows: [
      {name: 'Alice', age: 25},
      {name: 'Bob', age: 30},
      {name: 'Charlie', age: 34},
    ],
  });
  const evaluation = new weave.Evaluation({
    dataset: ds,
    scorers: [
      weave.op(({modelOutput, datasetRow}) => modelOutput == datasetRow.age, {
        name: 'isEqual',
      }),
    ],
  });

  const model = weave.op(async function myModel({datasetRow}) {
    return datasetRow.age >= 30;
  });

  const results = await evaluation.evaluate({model});
  console.log('Evaluation results:', JSON.stringify(results, null, 2));
}

main();
