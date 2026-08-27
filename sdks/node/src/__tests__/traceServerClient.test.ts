import {CLIENT_CAPABILITIES, CLIENT_CAPABILITIES_HEADER} from '../constants';
import {
  TRACE_SERVER_TIMEOUT_MS,
  createTraceServerClient,
} from '../traceServerClient';
import {setGlobalClient} from '../clientApi';
import {op} from '../op';
import {WeaveClient} from '../weaveClient';

describe('createTraceServerClient', () => {
  it('sends Basic auth as api:<key> even when WANDB_USERNAME is set', async () => {
    const previous = process.env.WANDB_USERNAME;
    process.env.WANDB_USERNAME = 'not-the-basic-user';
    const auths: string[] = [];
    try {
      const client = createTraceServerClient({
        apiKey: 'secret-key',
        baseURL: 'https://trace.example',
        fetch: async (_input, init) => {
          auths.push(new Headers(init?.headers).get('authorization') ?? '');
          return new Response('{}', {
            status: 200,
            headers: {'content-type': 'application/json'},
          });
        },
      });
      await client.services.healthCheck();
      expect(auths).toEqual([
        `Basic ${Buffer.from('api:secret-key').toString('base64')}`,
      ]);
    } finally {
      if (previous === undefined) {
        delete process.env.WANDB_USERNAME;
      } else {
        process.env.WANDB_USERNAME = previous;
      }
    }
  });

  it('does not add Stainless retries on top of the SDK wrapper', async () => {
    let calls = 0;
    const client = createTraceServerClient({
      apiKey: 'secret-key',
      baseURL: 'https://trace.example',
      fetch: async () => {
        calls += 1;
        return new Response('nope', {status: 500});
      },
    });
    await expect(client.services.healthCheck()).rejects.toMatchObject({
      status: 500,
    });
    expect(calls).toBe(1);
  });

  it('uses a 5 minute Stainless timeout', () => {
    expect(TRACE_SERVER_TIMEOUT_MS).toBe(5 * 60 * 1000);
    const client = createTraceServerClient({
      apiKey: 'secret-key',
      baseURL: 'https://trace.example',
      fetch: async () => new Response('{}'),
    });
    expect(client.timeout).toBe(TRACE_SERVER_TIMEOUT_MS);
  });

  it('sends the client-capability header when provided', async () => {
    const headers: string[] = [];
    const client = createTraceServerClient({
      apiKey: 'mock-api-key',
      baseURL: 'https://trace.example',
      fetch: async (_input, init) => {
        headers.push(
          new Headers(init?.headers).get(CLIENT_CAPABILITIES_HEADER) ?? ''
        );
        return new Response('{}', {
          status: 200,
          headers: {'content-type': 'application/json'},
        });
      },
      defaultHeaders: {
        [CLIENT_CAPABILITIES_HEADER]: CLIENT_CAPABILITIES,
      },
    });
    await client.services.healthCheck();
    expect(headers).toEqual([CLIENT_CAPABILITIES]);
  });
});

describe('v2Calls.complete argument order', () => {
  afterEach(() => {
    setGlobalClient(null as any);
  });

  it('puts entity then project in the path', async () => {
    const urls: string[] = [];
    const traceServerApi = createTraceServerClient({
      apiKey: 'key',
      baseURL: 'https://trace.example',
      fetch: async input => {
        urls.push(String(input));
        return new Response('{}', {
          status: 200,
          headers: {'content-type': 'application/json'},
        });
      },
    });
    const client = new WeaveClient({
      traceServerApi,
      projectId: 'my-entity/my-project',
    });
    setGlobalClient(client);
    const addOne = op(function addOne(x: number) {
      return x + 1;
    });
    await addOne(1);
    await client.waitForBatchProcessing();
    expect(
      urls.some(u => u.includes('/v2/my-entity/my-project/calls/complete'))
    ).toBe(true);
    expect(urls.some(u => u.includes('/v2/my-project/my-entity/'))).toBe(false);
  });
});
