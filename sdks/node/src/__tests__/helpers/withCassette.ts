import {join} from 'node:path';
import {DefaultRequestMatcher, FileStorage, VCR} from 'vcr-test';
import type {HttpRequest} from 'vcr-test';

const vcr = new VCR(new FileStorage(join(__dirname, '..', '__cassettes__')));

vcr.requestMasker = req => {
  req.headers['authorization'] = 'masked';
};

const UUID_V7 =
  /[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}/g;

const ISO8601 = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z/g;

/**
 * Replace per-run volatile fields (UUIDv7s, ISO timestamps, SDK
 * `client_version`) in a JSON-ish body with stable placeholders, so cassette
 * matching survives across runs.
 */
function normalizeVolatileBodyFields(req: HttpRequest): HttpRequest {
  const body = req.body
    .replace(UUID_V7, '<UUID>')
    .replace(ISO8601, '<TS>')
    .replace(/"client_version":"[^"]+"/g, '"client_version":"<VERSION>"');

  return {...req, body: body};
}

/**
 * Replace per-request multipart boundary with a stable placeholder
 * in both the `content-type` header and the body, so cassette matching works
 * across runs. Non-multipart requests pass through untouched.
 */
function normalizeMultipartBoundary(req: HttpRequest): HttpRequest {
  const contentType = req.headers['content-type'];
  if (!contentType?.startsWith('multipart/form-data')) {
    return req;
  }
  const match = contentType.match(/boundary=(.+)$/);
  if (!match) {
    return req;
  }
  const boundary = match[1];

  return {
    ...req,
    headers: {...req.headers, 'content-type': 'multipart/form-data'},
    body: req.body?.split(boundary).join('<BOUNDARY>'),
  };
}

function normalizeRequest(req: HttpRequest): HttpRequest {
  return [normalizeMultipartBoundary, normalizeVolatileBodyFields].reduce(
    (req, normalizer) => normalizer(req),
    req
  );
}

class Matcher extends DefaultRequestMatcher {
  override bodiesEqual(recorded: HttpRequest, request: HttpRequest): boolean {
    return super.bodiesEqual(
      normalizeRequest(recorded),
      normalizeRequest(request)
    );
  }
  override headersEqual(recorded: HttpRequest, request: HttpRequest): boolean {
    return super.headersEqual(
      normalizeRequest(recorded),
      normalizeRequest(request)
    );
  }
}

vcr.matcher = new Matcher();

export function withCassette(fn: () => Promise<void>) {
  const testName = expect.getState().currentTestName!;
  const cassetteName = testName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');

  return vcr.useCassette(cassetteName, fn);
}
