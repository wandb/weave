import 'source-map-support/register';
import * as weave from 'weave';

async function main() {
  await weave.init('examples');

  const ds = new weave.Dataset({
    id: 'My Dataset',
    description: 'This is a dataset',
    rows: [
      {firstName: 'Alice', yearsOld: 25},
      {firstName: 'Bob', yearsOld: 30},
      {firstName: 'Charlie', yearsOld: 34},
    ],
  });
  const evaluation = new weave.Evaluation({
    dataset: ds,
    scorers: [
      weave.op(({modelOutput, datasetRow}) => modelOutput == datasetRow.age, {
        name: 'isEqual',
      }),
    ],
    // Specify a column mapping to map the model inputs to dataset columns.
    // The order is always "model input": "dataset column".
    columnMapping: {
      name: 'firstName',
      age: 'yearsOld',
    },
  });

  const model = weave.op(async function myModel({datasetRow}) {
    return datasetRow.age >= 30;
  });

  const results = await evaluation.evaluate({model});
  console.log('Evaluation results:', JSON.stringify(results, null, 2));
}

main();
