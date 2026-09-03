import {join} from 'node:path';
import {DefaultRequestMatcher, FileStorage, VCR} from 'vcr-test';
import type {HttpRequest} from 'vcr-test';

const vcr = new VCR(new FileStorage(join(__dirname, '..', '__cassettes__')));

vcr.requestMasker = req => {
  req.headers['authorization'] = 'masked';
};

// Stainless probes `fetch('data:,')` to detect the Response constructor
// while building multipart bodies. That is not an HTTP call.
vcr.requestPassThrough = req => req.url.startsWith('data:');

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
 * Replace the SDK version token in the `user-agent` header with a stable
 * placeholder, so cassette matching survives version bumps.
 */
function normalizeUserAgentVersion(req: HttpRequest): HttpRequest {
  const userAgent = req.headers['user-agent'];
  if (!userAgent) {
    return req;
  }

  return {
    ...req,
    headers: {
      ...req.headers,
      'user-agent': userAgent.replace(/(JS Client ).+$/, '$1<VERSION>'),
    },
  };
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

/** Filename and extra digest field differ from the old swagger client; they are not load-bearing for cassette identity. */
function normalizeMultipartFileParts(req: HttpRequest): HttpRequest {
  if (!req.headers['content-type']?.startsWith('multipart/form-data')) {
    return req;
  }
  let body = req.body ?? '';
  body = body.replace(/filename="[^"]*"/g, 'filename="<FILE>"');
  body = body.replace(/Content-Type: [^\r]*\r\n/g, '');
  body = body.replace(
    /--<BOUNDARY>\r\nContent-Disposition: form-data; name="expected_digest"[\s\S]*?(?=--<BOUNDARY>)/g,
    ''
  );
  return {...req, body};
}

const MATCHED_HEADERS = new Set([
  'authorization',
  'user-agent',
  'content-type',
  'x-weave-client-capabilities',
]);

function keepMatchedHeaders(req: HttpRequest): HttpRequest {
  const headers: Record<string, string> = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (MATCHED_HEADERS.has(key.toLowerCase())) {
      headers[key.toLowerCase()] = value;
    }
  }
  return {...req, headers};
}

function normalizeRequest(req: HttpRequest): HttpRequest {
  return [
    keepMatchedHeaders,
    normalizeMultipartBoundary,
    normalizeMultipartFileParts,
    normalizeVolatileBodyFields,
    normalizeUserAgentVersion,
  ].reduce((req, normalizer) => normalizer(req), req);
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
