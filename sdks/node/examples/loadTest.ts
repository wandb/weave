import { init, op } from 'weave';
import { Op } from '../src/opType';
import { Settings } from '../src/settings';
import { WeaveClient } from '../src/weaveClient';

const func = op(async () => 1);
const myFunction = async (a: number = 1, b: string = 'hello', c: boolean = true) => {
  return { first: a, second: b, third: c };
};
const func2 = op(myFunction);
const func3 = op(async () => {
  throw new Error('hmm');
});
const myFunction2 = async ({ a, b = 'wuh' }: { a?: number; b?: string }) => {
  return { first: a, second: b };
};
const func4 = op(myFunction2, { parameterNames: 'useParam0Object' });

async function bench(func: Op<any>, calls: number, client: WeaveClient) {
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
  const client = await init({
    project: 'weavejsdev-loadtest2-k8s',
    settings: new Settings(true),
    // baseUrl: 'https://weave-test-1.wandb.ml',
    // traceBaseUrl: 'https://weave-test-1.wandb.ml/traces',
    // domain: 'weave-test-1.wandb.ml',

    baseUrl: 'https://api.wandb.ai',
    traceBaseUrl: 'https://weave-trace.wandb.ai',
    domain: 'wandb.ai',
  });
  // for (let x = 1; x <= 5; x++) {
  //   const calls = Math.pow(10, x);
  //   await bench(calls, client);
  // }
  await bench(func4, 1, client);
}

main();
