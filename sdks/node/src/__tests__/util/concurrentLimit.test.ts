import {ConcurrencyLimiter} from '../../utils/concurrencyLimit';

describe('concurrency limiting', () => {
  test('it works', async () => {
    const limit = 2;
    const numJobs = 10;

    const limiter = new ConcurrencyLimiter(limit);
    let currentlyRunning = 0;
    let maxConcurrent = 0;

    const mockJob = jest.fn(async () => {
      currentlyRunning++;
      expect(currentlyRunning).toBe(limiter.active);
      maxConcurrent = Math.max(maxConcurrent, currentlyRunning);
      await new Promise(resolve => setTimeout(resolve, 100));
      currentlyRunning--;
    });

    const limitedJob = limiter.limitFunction(mockJob);

    const promises = [];
    for (let i = 0; i < numJobs; i++) {
      promises.push(limitedJob());
    }
    await Promise.all(promises);

    expect(maxConcurrent).toBeLessThanOrEqual(limit);
  });
});
