import {createTraceServerClient} from '../traceServerClient';
import {WeaveClient} from '../weaveClient';

describe('file upload', () => {
  it('puts a named file part in the multipart body', async () => {
    const parts: Array<{name: string; filename?: string}> = [];
    const traceServerApi = createTraceServerClient({
      apiKey: 'key',
      baseURL: 'https://trace.example',
      fetch: async (_input, init) => {
        const body = init?.body as FormData;
        expect(body).toBeInstanceOf(FormData);
        for (const [name, value] of body.entries()) {
          if (typeof value === 'string') {
            parts.push({name});
          } else {
            parts.push({name, filename: value.name});
          }
        }
        return new Response(JSON.stringify({digest: 'abc'}), {
          status: 200,
          headers: {'content-type': 'application/json'},
        });
      },
    });
    const client = new WeaveClient({
      traceServerApi,
      projectId: 'entity/project',
    });
    const bytes = Buffer.from('hello-image');
    const blob = new Blob([bytes], {type: 'image/png'});
    await (client as any).serializedFileBlob(
      'PIL.Image.Image',
      'image.png',
      blob
    );
    expect(
      parts.some(p => p.name === 'file' && p.filename === 'image.png')
    ).toBe(true);
    expect(parts.some(p => p.name === 'project_id')).toBe(true);
    expect(parts.some(p => p.name === 'expected_digest')).toBe(true);
  });
});
