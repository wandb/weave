/**
 * Thenable that matches Stainless `APIPromise`: `await p` yields payload T,
 * `p.withResponse()` yields `{data, response}`, `p.asResponse()` yields
 * the raw Response.
 *
 * `data` may be a Promise so callers that need to await work can still
 * attach `withResponse` onto the same object `asHttpResponse` receives.
 */
export function stainlessPromise<T>(
  data: T | Promise<T>,
  response: Response = new Response(null, {status: 200})
) {
  const dataPromise = Promise.resolve(data);
  const p = dataPromise as Promise<T> & {
    withResponse: () => Promise<{data: T; response: Response}>;
    asResponse: () => Promise<Response>;
  };
  p.withResponse = async () => ({data: await dataPromise, response});
  p.asResponse = async () => response;
  return p;
}

/** Rejected Stainless thenable. The outer rejection is swallowed so Jest does not see an unhandled rejection; `withResponse` still rejects. */
export function stainlessReject(err: unknown) {
  const rejected = Promise.reject(err);
  rejected.catch(() => {});
  const p = rejected as Promise<never> & {
    withResponse: () => Promise<never>;
    asResponse: () => Promise<never>;
  };
  p.withResponse = () => Promise.reject(err);
  p.asResponse = () => Promise.reject(err);
  return p;
}
