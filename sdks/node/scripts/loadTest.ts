import * as weave from 'weave';

const func = weave.op(async () => 1);
const myFunction = async (a: number = 1, b: string = 'hello', c: boolean = true) => {
  return { first: a, second: b, third: c };
};
const func2 = weave.op(myFunction);
const func3 = weave.op(async () => {
  throw new Error('hmm');
});
const myFunction2 = async ({ a, b = 'wuh' }: { a?: number; b?: string }) => {
  return { first: a, second: b };
};
const func4 = weave.op(myFunction2, { parameterNames: 'useParam0Object' });

async function bench(func: weave.Op<any>, calls: number, client: weave.WeaveClient) {
  console.log(`Benchmarking with ${calls} calls...`);
  const startTime = Date.now();
  const promises = Array(calls)
    .fill(null)
    .map(() => func({ a: 3 }));
  await Promise.all(promises);
  await client.waitForBatchProcessing();

  const endTime = Date.now();
  const duration = (endTime - startTime) / 1000; // Convert to seconds
  console.log(`Completed ${calls} calls in ${duration.toFixed(2)} seconds`);
}

async function main() {
  const client = await weave.init('examples');
  // for (let x = 1; x <= 5; x++) {
  //   const calls = Math.pow(10, x);
  //   await bench(calls, client);
  // }
  await bench(func4, 1, client);
}

main();
