import {APIError, type APIPromise} from './vendor/weave-server-sdk';
import type {HTTPValidationError, HttpResponse} from './traceServerTypes';

function isHttpApiError(
  err: unknown
): err is APIError & {status: number; error: unknown} {
  return err instanceof APIError && typeof err.status === 'number';
}

/**
 * Map a Stainless HTTP `APIError` onto the swagger-shaped object the
 * public methods used to throw. Connection errors and plain `Error`s
 * pass through unchanged.
 */
export function throwAsHttpResponse(err: unknown): never {
  if (isHttpApiError(err)) {
    throw Object.assign(new Response(null, {status: err.status}), {
      data: null,
      error: err.error ?? null,
    });
  }
  throw err;
}

/**
 * Adapt a Stainless `APIPromise<T>` (resolves to payload `T`) into the
 * swagger `{data, error}` `Response` the public methods still return.
 */
export async function asHttpResponse<T = any>(
  p: APIPromise<any>
): Promise<HttpResponse<T, HTTPValidationError>> {
  try {
    const {data, response} = await p.withResponse();
    return Object.assign(response, {
      data,
      error: null,
    }) as unknown as HttpResponse<T, HTTPValidationError>;
  } catch (err) {
    throwAsHttpResponse(err);
  }
}
