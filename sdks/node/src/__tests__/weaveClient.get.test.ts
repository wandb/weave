import {Api as TraceServerApi} from '../generated/traceServerApi';
import {type ImageType} from '../media';
import {WeaveClient} from '../weaveClient';
import {ObjectRef} from '../weaveObject';

// Not valid UTF-8, so a fix that routes the body through a string fails here.
const IMAGE_BYTES = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x00, 0xff, 0xfe]);
const IMAGE_DIGEST = 'test-digest';
const REF = new ObjectRef('other-entity/other-project', 'my-image', 'v1');
const REF_URI = 'weave:///other-entity/other-project/object/my-image:v1';

function objReadBody(files: Record<string, string> | null) {
  return JSON.stringify({
    obj: {
      val: {
        _type: 'CustomWeaveType',
        weave_type: {type: 'PIL.Image.Image'},
        files,
        load_op: 'NO_LOAD_OP',
      },
    },
  });
}

// The endpoint sends the file with no content type, so neither does this.
const respondWithImageBytes = async () => new Response(IMAGE_BYTES);

function clientServingFileContent(
  fileContent: () => Promise<Response>,
  files: Record<string, string> | null = {'image.png': IMAGE_DIGEST}
) {
  const fileRequests: unknown[] = [];
  const traceServerApi = new TraceServerApi({
    baseUrl: 'https://trace.example',
    customFetch: async (input, init) => {
      const url = input.toString();
      if (url.endsWith('/obj/read')) {
        return new Response(objReadBody(files), {
          headers: {'content-type': 'application/json'},
        });
      }
      if (url.endsWith('/file/content')) {
        fileRequests.push(JSON.parse(init!.body as string));
        return fileContent();
      }
      throw new Error(`Unexpected request to ${url}`);
    },
  });
  const client = new WeaveClient({
    traceServerApi,
    projectId: 'this-entity/this-project',
  });
  return {client, fileRequests};
}

describe('WeaveClient.get on a published image', () => {
  it('returns a WeaveImage carrying the stored bytes', async () => {
    const {client, fileRequests} = clientServingFileContent(
      respondWithImageBytes
    );

    expect(await client.get(REF)).toEqual({
      _weaveType: 'Image',
      data: IMAGE_BYTES,
      imageType: 'png',
    });
    expect(fileRequests).toEqual([
      {project_id: 'other-entity/other-project', digest: IMAGE_DIGEST},
    ]);
  });

  // The Python SDK stores the image under its own format's extension; an
  // extension we do not know keeps the png default.
  const formatCases: Array<[string, ImageType]> = [
    ['image.jpg', 'jpeg'],
    ['image.webp', 'webp'],
    ['image.gif', 'png'],
  ];
  it.each(formatCases)('reads %s back as %s', async (fileName, imageType) => {
    const {client} = clientServingFileContent(respondWithImageBytes, {
      [fileName]: IMAGE_DIGEST,
    });

    expect(await client.get(REF)).toEqual({
      _weaveType: 'Image',
      data: IMAGE_BYTES,
      imageType,
    });
  });

  it('rejects when the file request fails', async () => {
    const {client} = clientServingFileContent(
      async () => new Response('not found', {status: 404})
    );

    await expect(client.get(REF)).rejects.toMatchObject({
      status: 404,
      data: null,
    });
  });

  it('rejects when the file body cannot be read', async () => {
    const {client} = clientServingFileContent(async () => {
      const truncated = new ReadableStream({
        start: controller => controller.error(new Error('terminated')),
      });
      return new Response(truncated);
    });

    await expect(client.get(REF)).rejects.toThrow(
      `Unable to download file for ref uri: ${REF_URI}`
    );
  });

  it('rejects when the object stores no image file', async () => {
    const {client} = clientServingFileContent(respondWithImageBytes, null);

    await expect(client.get(REF)).rejects.toThrow(
      `No image file stored for ref uri: ${REF_URI}`
    );
  });
});
