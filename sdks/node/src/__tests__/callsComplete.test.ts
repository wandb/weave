/**
 * Tests for the calls_complete ingest path: start/end pairing, the eager
 * (immediate v2 start/end) path for long-running ops, the legacy fallback,
 * and the automatic upgrade when a project is pinned to calls_complete mode.
 */
import {getGlobalClient} from '../clientApi';
import {markOpEager, op} from '../op';
import {initWithCustomTraceServer} from './clientMock';
import {InMemoryTraceServer} from './helpers/inMemoryTraceServer';

const projectId = 'test-entity/test-project';

function client() {
  const c = getGlobalClient();
  if (!c) {
    throw new Error('global client not initialized');
  }
  return c;
}

function pathsHit(spy: jest.SpyInstance): string[] {
  return spy.mock.calls.map(args => (args[0] as {path: string}).path);
}

describe('calls_complete pairing (default path)', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  test('a finished op is written once via calls/complete with merged start+end', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');
    const legacySpy = jest.spyOn(
      traceServer.call,
      'callStartBatchCallUpsertBatchPost'
    );

    const double = op(function double(x: number) {
      return x * 2;
    });
    const result = await double(21);
    await client().waitForBatchProcessing();

    expect(result).toBe(42);

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    const [call] = calls;
    // Start and end fields arrive together in a single row.
    expect(call.inputs.arg0).toBe(21);
    expect(call.output).toBe(42);
    expect(call.started_at).toBeDefined();
    expect(call.ended_at).toBeDefined();
    expect(call.exception ?? null).toBeNull();

    // Exactly one complete write, and nothing on the legacy path.
    expect(pathsHit(requestSpy)).toEqual([`/v2/${projectId}/calls/complete`]);
    expect(legacySpy).not.toHaveBeenCalled();
  });

  test('nested calls produce one complete per call with correct parentage', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');

    const inner = op(function inner(x: number) {
      return x + 1;
    });
    const outer = op(async function outer(x: number) {
      return (await inner(x)) + (await inner(x));
    });
    await outer(10);
    await client().waitForBatchProcessing();

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(3);
    const outerCall = calls.find(c => c.op_name.includes('outer'));
    const innerCalls = calls.filter(c => c.op_name.includes('inner'));
    expect(outerCall?.parent_id ?? null).toBeNull();
    expect(outerCall?.output).toBe(22);
    expect(innerCalls).toHaveLength(2);
    for (const ic of innerCalls) {
      expect(ic.parent_id).toBe(outerCall?.id);
      expect(ic.trace_id).toBe(outerCall?.trace_id);
    }
    // 3 completes (children pair and flush as they finish, parent last).
    expect(pathsHit(requestSpy).every(p => p.endsWith('/calls/complete'))).toBe(
      true
    );
  });

  test('a thrown op records the exception in the complete write', async () => {
    const boom = op(function boom() {
      throw new Error('kaboom');
    });
    await expect(boom()).rejects.toThrow('kaboom');
    await client().waitForBatchProcessing();

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].exception).toBe('kaboom');
    expect(calls[0].ended_at).toBeDefined();
  });

  test('out-of-order end-before-start still pairs into one complete', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');
    const c = client();
    const id = 'call-ooo';
    const trace = 'trace-ooo';

    c.saveCallEnd({
      project_id: projectId,
      id,
      trace_id: trace,
      ended_at: new Date().toISOString(),
      output: 'late',
      summary: {},
    });
    c.saveCallStart({
      project_id: projectId,
      id,
      trace_id: trace,
      op_name: 'weave:///x/op/o:1',
      started_at: new Date().toISOString(),
      attributes: {},
      inputs: {a: 1},
    });
    await c.waitForBatchProcessing();

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs.a).toBe(1);
    expect(calls[0].output).toBe('late');
    expect(pathsHit(requestSpy)).toEqual([`/v2/${projectId}/calls/complete`]);
  });

  test('an unfinished call is flushed via the eager start endpoint, not dropped', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');
    const c = client();
    c.saveCallStart({
      project_id: projectId,
      id: 'orphan',
      trace_id: 'trace-orphan',
      op_name: 'weave:///x/op/o:1',
      started_at: new Date().toISOString(),
      attributes: {},
      inputs: {},
    });
    // Nothing queued yet: the start is held pending its end.
    await c.waitForBatchProcessing();

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].id).toBe('orphan');
    expect(calls[0].ended_at).toBeUndefined();
    expect(pathsHit(requestSpy)).toEqual([`/v2/${projectId}/call/start`]);
  });

  test('a start without an id is sent via the eager endpoint, not dropped', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');
    const c = client();
    c.saveCallStart({
      project_id: projectId,
      op_name: 'weave:///x/op/o:1',
      started_at: new Date().toISOString(),
      attributes: {},
      inputs: {},
    });
    await c.waitForBatchProcessing();
    // Unpairable (no id): cannot become a complete, so it ships as a raw start.
    expect(pathsHit(requestSpy)).toEqual([`/v2/${projectId}/call/start`]);
  });
});

describe('calls_complete eager path', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  test('an eager op sends start and end via the v2 single endpoints', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');
    const longRunning = op(function longRunning(x: number) {
      return x;
    });
    markOpEager(longRunning);
    await longRunning(7);
    await client().waitForBatchProcessing();

    const paths = pathsHit(requestSpy).sort();
    expect(paths).toEqual([
      `/v2/${projectId}/call/end`,
      `/v2/${projectId}/call/start`,
    ]);
    // Never paired into a complete.
    expect(paths).not.toContain(`/v2/${projectId}/calls/complete`);

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].output).toBe(7);
    expect(calls[0].ended_at).toBeDefined();
  });
});

describe('legacy path (useCallsComplete=false)', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer, {
      useCallsComplete: false,
    });
  });

  test('finished op goes through call/upsert_batch and never the v2 endpoints', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');
    const legacySpy = jest.spyOn(
      traceServer.call,
      'callStartBatchCallUpsertBatchPost'
    );

    const triple = op(function triple(x: number) {
      return x * 3;
    });
    await triple(3);
    await client().waitForBatchProcessing();

    expect(legacySpy).toHaveBeenCalled();
    expect(requestSpy).not.toHaveBeenCalled();

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].output).toBe(9);
  });
});

describe('automatic upgrade to calls_complete', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer, {
      useCallsComplete: false,
    });
  });

  test('CALLS_COMPLETE_MODE_REQUIRED on the legacy path re-pairs via calls/complete', async () => {
    const requestSpy = jest.spyOn(traceServer, 'request');
    // The first (and only) legacy attempt is rejected by a pinned project.
    jest
      .spyOn(traceServer.call, 'callStartBatchCallUpsertBatchPost')
      .mockRejectedValueOnce({
        status: 400,
        error: {error_code: 'CALLS_COMPLETE_MODE_REQUIRED'},
      });

    const adder = op(function adder(x: number) {
      return x + 100;
    });
    await adder(1);
    await client().waitForBatchProcessing();

    // Upgraded: the call lands via the complete endpoint with full data.
    expect(pathsHit(requestSpy)).toContain(`/v2/${projectId}/calls/complete`);
    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs.arg0).toBe(1);
    expect(calls[0].output).toBe(101);
  });
});

describe('send error handling', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  test('a non-retryable 4xx drops the batch instead of retrying forever', async () => {
    const requestSpy = jest
      .spyOn(traceServer, 'request')
      .mockRejectedValue({status: 400, error: {detail: 'invalid uuid'}});

    const bad = op(function bad(x: number) {
      return x;
    });
    await bad(1);
    await client().waitForBatchProcessing();

    // One attempt, then dropped: no requeue storm, no process.exit.
    expect(requestSpy).toHaveBeenCalledTimes(1);
  });

  test('a retryable 5xx requeues and the call eventually lands', async () => {
    const real = traceServer.request.bind(traceServer);
    let attempts = 0;
    jest.spyOn(traceServer, 'request').mockImplementation(async params => {
      attempts++;
      if (attempts === 1) {
        throw {status: 503};
      }
      return real(params);
    });

    const flaky = op(function flaky(x: number) {
      return x * 2;
    });
    await flaky(5);
    await client().waitForBatchProcessing();

    expect(attempts).toBeGreaterThanOrEqual(2);
    const calls = await traceServer.getCalls(projectId);
    expect(calls.find(c => c.op_name.includes('flaky'))?.output).toBe(10);
  });

  test('gives up gracefully after sustained errors without killing the process', async () => {
    jest.spyOn(traceServer, 'request').mockRejectedValue({status: 503});
    const c = client();
    (c as unknown as {BATCH_INTERVAL: number}).BATCH_INTERVAL = 1;

    const doomed = op(function doomed(x: number) {
      return x;
    });
    await doomed(1);
    await c.waitForBatchProcessing();

    // Tracing disabled (not process.exit); the test process is still running.
    expect((c as unknown as {tracingDisabled: boolean}).tracingDisabled).toBe(
      true
    );
    // Further calls are no-ops rather than growing the queue unbounded.
    const queue = c as unknown as {callQueue: unknown[]};
    const before = queue.callQueue.length;
    c.saveCallStart({
      project_id: projectId,
      id: 'after-disable',
      trace_id: 'trace-after',
      op_name: 'weave:///x/op/o:1',
      started_at: new Date().toISOString(),
      attributes: {},
      inputs: {},
    });
    expect(queue.callQueue.length).toBe(before);
  });

  test('sustained errors on the eager path also trip the breaker', async () => {
    // Eager start/end go via the v2 single endpoints and requeue in place
    // (they never throw out of sendBatch), so their failures must still feed
    // the give-up counter or a down server would requeue forever and hang.
    jest.spyOn(traceServer, 'request').mockRejectedValue({status: 503});
    const c = client();
    (c as unknown as {BATCH_INTERVAL: number}).BATCH_INTERVAL = 1;

    const doomedEager = op(function doomedEager(x: number) {
      return x;
    });
    markOpEager(doomedEager);
    await doomedEager(1);
    await c.waitForBatchProcessing();

    expect((c as unknown as {tracingDisabled: boolean}).tracingDisabled).toBe(
      true
    );
  });
});

describe('flush + pendingCallCount (clean-shutdown surface)', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  test('pendingCallCount tracks buffered work and flush drains + delivers it', async () => {
    const c = client();
    expect(c.pendingCallCount()).toBe(0);

    // A held start (its end has not arrived) is buffered, so it counts.
    c.saveCallStart({
      project_id: projectId,
      id: 'pending-1',
      trace_id: 'trace-1',
      op_name: 'weave:///x/op/o:1',
      started_at: new Date().toISOString(),
      attributes: {},
      inputs: {},
    });
    expect(c.pendingCallCount()).toBeGreaterThan(0);

    await c.flush();

    // Drained to zero and the buffered call actually reached the server.
    expect(c.pendingCallCount()).toBe(0);
    const calls = await traceServer.getCalls(projectId);
    expect(calls.map(call => call.id)).toContain('pending-1');
  });
});
