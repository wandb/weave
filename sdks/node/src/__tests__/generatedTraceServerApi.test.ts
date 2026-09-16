import {createTraceServerClient} from '../traceServerClient';
import {WeaveClient} from '../weaveClient';

test('encodes custom runtime names in request paths', async () => {
  let requestedUrl: string | undefined;
  const traceServerApi = createTraceServerClient({
    apiKey: 'test-key',
    baseURL: 'https://trace.example',
    fetch: async input => {
      requestedUrl = input.toString();
      return new Response('{}', {
        status: 200,
        headers: {'Content-Type': 'application/json'},
      });
    },
  });
  const client = new WeaveClient({
    traceServerApi,
    projectId: 'entity/project',
  });

  await client.registerCustomRuntime({
    name: 'support/agent?canary',
    baseUrl: 'https://runtime.example/v1',
    runtimeIds: [],
  });

  expect(requestedUrl).toBe(
    'https://trace.example/v2/entity/project/runtimes/support%2Fagent%3Fcanary'
  );
});
