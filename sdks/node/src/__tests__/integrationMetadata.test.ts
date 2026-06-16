import {op} from 'weave';

import {initWithCustomTraceServer} from './clientMock';
import {InMemoryTraceServer} from './helpers/inMemoryTraceServer';
import {
  type IntegrationMetadata,
  asAttributes,
  asOtelAttributes,
  libraryIntegration,
} from '../integrations/integrationMetadata';
import {packageVersion} from '../utils/packageVersion';

describe('integration metadata builders', () => {
  test('libraryIntegration records package name and SDK version', () => {
    const m = libraryIntegration('openai');
    expect(m.name).toBe('openai');
    expect(m.version).toBe(packageVersion);
    expect(m.meta).toEqual({package_name: 'openai'});
  });

  test('libraryIntegration accepts a distinct package name and version', () => {
    const m = libraryIntegration('anthropic', {
      packageName: '@anthropic-ai/sdk',
      packageVersion: '1.2.3',
    });
    expect(m.meta).toEqual({
      package_name: '@anthropic-ai/sdk',
      package_version: '1.2.3',
    });
  });

  test('asAttributes renders the nested shape', () => {
    const m: IntegrationMetadata = {name: 'x', version: '1', meta: {k: 'v'}};
    expect(asAttributes(m)).toEqual({
      integration: {name: 'x', version: '1', meta: {k: 'v'}},
    });
  });

  test('asAttributes returns fresh copies', () => {
    const m = libraryIntegration('x');
    const first = asAttributes(m);
    first.integration.meta.package_name = 'mutated';
    expect(asAttributes(m).integration.meta.package_name).toBe('x');
  });

  test('asOtelAttributes flattens to dotted keys', () => {
    const m: IntegrationMetadata = {
      name: 'openai_agents',
      version: '1',
      meta: {package_name: 'p', package_version: '2'},
    };
    expect(asOtelAttributes(m)).toEqual({
      'integration.name': 'openai_agents',
      'integration.version': '1',
      'integration.meta.package_name': 'p',
      'integration.meta.package_version': '2',
    });
  });
});

describe('op-level attributes', () => {
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

  test('op attributes stamp integration provenance on the call', async () => {
    const tracedOp = op(
      async function tracedOp() {
        return 'ok';
      },
      {attributes: asAttributes(libraryIntegration('demo'))}
    );

    await tracedOp();

    const calls = await getCalls();
    const call = calls.find(c => c.op_name?.includes('tracedOp'));
    expect(call?.attributes?.integration?.name).toBe('demo');
    expect(call?.attributes?.integration?.version).toBe(packageVersion);
    expect(call?.attributes?.integration?.meta?.package_name).toBe('demo');
  });

  test('op kind takes precedence over op attributes on collision', async () => {
    const tracedOp = op(
      async function kindOp() {
        return 'ok';
      },
      {opKind: 'llm', attributes: {kind: 'should-be-overridden'}}
    );

    await tracedOp();

    const calls = await getCalls();
    const call = calls.find(c => c.op_name?.includes('kindOp'));
    expect(call?.attributes?.kind).toBe('llm');
  });
});
