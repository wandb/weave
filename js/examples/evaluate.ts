import 'source-map-support/register';
import { init, wrapOpenAI, op, DatasetFake, Evaluation } from 'weave';

async function main() {
    const client = await init('weavejsdev-eval1');
    const ds = new DatasetFake({
        id: "My Dataset",
        description: "This is a dataset",
        rows: [
            { name: "Alice", age: 25 },
            { name: "Bob", age: 30 },
            { name: "Charlie", age: 34 }
        ]
    });
    const evaluation = new Evaluation({
        dataset: ds,
        scorers: [
            op((modelOutput: any, datasetItem: any) =>
                modelOutput == datasetItem.age, { name: 'isEqual' }),
        ]
    })

    const model = op(async function myModel(input) {
        return input.age
    })

    const results = await evaluation.evaluate(model)
    console.log(results)


}

main();

