import {withAttributes, op} from 'weave';

import {initWithCustomTraceServer} from './clientMock';
import {InMemoryTraceServer} from '../inMemoryTraceServer';
import {Settings} from '../settings';

describe('attributes context', () => {
  const projectId = 'test-project';
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  const getCalls = async () => {
    await traceServer.waitForPendingOperations();
    const result = await traceServer.calls.callsStreamQueryPost({
      project_id: projectId,
    });
    return result.calls;
  };

  test('propagates attributes to parent and child calls', async () => {
    const childOp = op(async function childOp() {
      return 'child';
    });

    const parentOp = op(async function parentOp() {
      await childOp();
      return 'parent';
    });

    await withAttributes({requestId: 'req-123'}, async () => {
      await parentOp();
    });

    const calls = await getCalls();
    const parentCall = calls.find(c => c.op_name?.includes('parentOp'));
    const childCall = calls.find(c => c.op_name?.includes('childOp'));

    expect(parentCall?.attributes?.requestId).toBe('req-123');
    expect(childCall?.attributes?.requestId).toBe('req-123');
  });

  test('merges nested attributes with overrides', async () => {
    const leafOp = op(async function leafOp() {
      return 'leaf';
    });

    const parentOp = op(async function parentOp() {
      await withAttributes({scope: 'inner', merged: 'child'}, async () => {
        await leafOp();
      });
    });

    await withAttributes({scope: 'outer', merged: 'parent'}, async () => {
      await parentOp();
    });

    const calls = await getCalls();
    const parentCall = calls.find(c => c.op_name?.includes('parentOp'));
    const childCall = calls.find(c => c.op_name?.includes('leafOp'));

    expect(parentCall?.attributes?.scope).toBe('outer');
    expect(parentCall?.attributes?.merged).toBe('parent');
    expect(childCall?.attributes?.scope).toBe('inner');
    expect(childCall?.attributes?.merged).toBe('child');
  });

  test('applies global attributes from init settings', async () => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(
      projectId,
      traceServer,
      new Settings(true, {tenant: 'acme', base: 'global'})
    );

    const leafOp = op(async function leafOp() {
      return 'leaf';
    });

    await withAttributes({base: 'local'}, async () => {
      await leafOp();
    });

    await traceServer.waitForPendingOperations();
    const result = await traceServer.calls.callsStreamQueryPost({
      project_id: projectId,
    });
    const leafCall = result.calls.find(c => c.op_name?.includes('leafOp'));
    expect(leafCall?.attributes?.tenant).toBe('acme');
    expect(leafCall?.attributes?.base).toBe('local'); // local overrides global
  });
});
