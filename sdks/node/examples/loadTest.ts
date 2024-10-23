import { init, op } from 'weave';
import { Settings } from '../src/settings';
import { WeaveClient } from '../src/weaveClient';

const func = op(async () => 1);

async function bench(calls: number, client: WeaveClient) {
  console.log(`Benchmarking with ${calls} calls...`);
  const startTime = Date.now();
  const promises = Array(calls)
    .fill(null)
    .map(() => func());
  await Promise.all(promises);
  await client.waitForBatchProcessing();

  const endTime = Date.now();
  const duration = (endTime - startTime) / 1000; // Convert to seconds
  console.log(`Completed ${calls} calls in ${duration.toFixed(2)} seconds`);
}

async function main() {
  const client = await init({ project: 'weavejsdev-loadtest2', settings: new Settings(false) });
  for (let x = 1; x <= 6; x++) {
    const calls = Math.pow(10, x);
    await bench(calls, client);
  }
}

main();
