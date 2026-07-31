import {Api as TraceServerApi} from '../generated/traceServerApi';

test('encodes custom runtime names in request paths', async () => {
  let requestedUrl: string | undefined;
  const api = new TraceServerApi({
    baseUrl: 'https://trace.example',
    customFetch: async input => {
      requestedUrl = input.toString();
      return new Response('{}', {
        status: 200,
        headers: {'Content-Type': 'application/json'},
      });
    },
  });

  await api.v2.customRuntimeApplyV2EntityProjectRuntimesRuntimeNamePut(
    'entity',
    'project',
    'support/agent?canary',
    {
      base_url: 'https://runtime.example/v1',
      runtime_ids: [],
    }
  );

  expect(requestedUrl).toBe(
    'https://trace.example/v2/entity/project/runtimes/support%2Fagent%3Fcanary'
  );
});
