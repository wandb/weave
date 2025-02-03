import {op} from '../op';

describe('op streaming', () => {
  it('maintains isolated state for concurrent streams', async () => {
    // Simple stream that emits numbers with some delay to ensure interleaving
    async function* numberStream(id: string, nums: number[]) {
      const startTime = Date.now();
      for (const n of nums) {
        const sleepTime = Math.floor(Math.random() * 40) + 10;
        await new Promise(resolve => setTimeout(resolve, sleepTime));
        yield {id, value: n, time: Date.now() - startTime};
      }
    }

    // Create an op with a summing stream reducer
    const streamReducer = {
      initialStateFn: () => ({sum: 0, id: ''}),
      reduceFn: (state: any, chunk: any) => ({
        sum: state.sum + chunk.value,
        id: chunk.id,
      }),
    };
    const streamOp = op(numberStream, {streamReducer});

    // Define a few streams to run concurrently
    const testCases = [
      {id: 'a', numbers: [1, 2, 3, 4, 5], expectedSum: 15},
      {id: 'b', numbers: [10, 20, 30, 40, 50], expectedSum: 150},
      {id: 'c', numbers: [100, 200, 300, 400, 500], expectedSum: 1500},
      {id: 'd', numbers: [1000, 2000, 3000, 4000, 5000], expectedSum: 15000},
      {id: 'e', numbers: [2, 4, 6, 8, 10], expectedSum: 30},
    ];

    // Store chunks and states for each stream
    const results = testCases.map(() => ({
      times: [] as number[],
      chunks: [] as any[],
      finalState: streamReducer.initialStateFn(),
    }));

    // Run all streams concurrently
    const startTime = Date.now();
    await Promise.all(
      testCases.map(async (testCase, index) => {
        const stream = await streamOp(testCase.id, testCase.numbers);
        for await (const chunk of stream) {
          results[index].times.push(Date.now() - startTime);
          results[index].chunks.push(chunk);
        }
      })
    );

    // Verify concurrency by checking that we received chunks from different streams
    // within a small time window
    const allTimes = results
      .flatMap((result, idx) =>
        result.times.map(time => ({time, streamIndex: idx}))
      )
      .sort((a, b) => a.time - b.time);

    // Check that within the first N chunks, we see at least 3 different streams
    const firstNChunks = allTimes.slice(0, 5);
    const uniqueStreamsEarly = new Set(firstNChunks.map(x => x.streamIndex))
      .size;
    expect(uniqueStreamsEarly).toBeGreaterThanOrEqual(3);

    // Verify results for each stream
    testCases.forEach((testCase, index) => {
      // Collect just the chunk data (don't need the time)
      const chunksWithoutTime = results[index].chunks.map(({id, value}) => ({
        id,
        value,
      }));
      expect(chunksWithoutTime).toEqual(
        testCase.numbers.map(value => ({
          id: testCase.id,
          value,
        }))
      );

      // Reduce chunks and confirm final state is as we expect
      results[index].chunks.forEach(chunk => {
        results[index].finalState = streamReducer.reduceFn(
          results[index].finalState,
          chunk
        );
      });
      expect(results[index].finalState).toEqual({
        sum: testCase.expectedSum,
        id: testCase.id,
      });
    });
  });
});
