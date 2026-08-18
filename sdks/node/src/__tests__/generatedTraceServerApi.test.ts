import {readFileSync} from 'node:fs';
import {createServer} from 'node:http';
import {resolve} from 'node:path';

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

test('sends feedback accepted by the minimum supported server', async () => {
  const compatibility = JSON.parse(
    readFileSync(
      resolve(__dirname, '../../../../client_server_compatibility.json'),
      'utf8'
    )
  );
  const contract = compatibility.feedback_create_batch;
  let server: ReturnType<typeof createServer> | undefined;
  let baseUrl = process.env.WEAVE_MIN_SERVER_URL;

  if (baseUrl == null) {
    const allowedFields = new Set(contract.request_fields);
    server = createServer((request, response) => {
      const chunks: Buffer[] = [];
      request.on('data', chunk => chunks.push(chunk));
      request.on('end', () => {
        const payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        const extraFields = payload.batch.flatMap(
          (item: Record<string, unknown>) =>
            Object.keys(item).filter(field => !allowedFields.has(field))
        );
        const accepted =
          request.url === contract.path && extraFields.length === 0;
        response.writeHead(accepted ? 200 : 422, {
          'Content-Type': 'application/json',
        });
        response.end(
          JSON.stringify(
            accepted
              ? {res: []}
              : {
                  detail: extraFields.map((field: string) => ({
                    type: 'extra_forbidden',
                    field,
                  })),
                }
          )
        );
      });
    });
    await new Promise<void>(resolveListen =>
      server?.listen(0, '127.0.0.1', resolveListen)
    );
    const address = server.address();
    if (address == null || typeof address === 'string') {
      throw new Error('Compatibility server did not bind to a TCP port');
    }
    baseUrl = `http://127.0.0.1:${address.port}`;
  }

  try {
    const api = new TraceServerApi({baseUrl});
    const response =
      await api.feedback.feedbackCreateBatchFeedbackBatchCreatePost({
        batch: [
          {
            project_id: 'entity/project',
            weave_ref: 'weave:///entity/project/call/call-id',
            feedback_type: 'custom',
            payload: {value: 1},
          },
        ],
      });

    expect(response.status).toBe(200);
    expect(response.data).toEqual({res: []});
  } finally {
    if (server != null) {
      await new Promise<void>((resolveClose, reject) =>
        server?.close(error => (error ? reject(error) : resolveClose()))
      );
    }
  }
});
